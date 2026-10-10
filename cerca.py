"""Cerca siti di PMI vecchi o poco moderni in una zona e produce un report con i contatti migliori.

Esempi:
    python cerca.py --zona PD                  # provincia di Padova (sigla)
    python cerca.py --zona "comune:Abano Terme"
    python cerca.py --dalla-coda               # prossima provincia di coda_province.txt
"""

import argparse
import datetime as dt
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from leadfinder import bisogni, controlli, fonti, report, valutazione_ai
from leadfinder.db import Archivio

RADICE = Path(__file__).parent
ARCHIVIO = RADICE / "dati" / "archivio.sqlite"
REPORT = RADICE / "report"
CODA = RADICE / "coda_province.txt"
SOGLIA_REPORT = 40
PRIORITA_PROPOSTE = 55


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def relativo(percorso: str | None) -> str | None:
    """I percorsi nell'archivio sono relativi alla cartella del progetto, così funzionano ovunque."""
    return Path(percorso).resolve().relative_to(RADICE.resolve()).as_posix() if percorso else None


def calcola_priorita(solo_social: bool, raggiungibile: bool, tecnico: int, ai: dict | None, telefono: str,
                     recensioni: int = 0) -> int:
    if solo_social:
        base = 70
    elif not raggiungibile:
        base = 45  # da verificare a mano: può essere un blocco verso i server di GitHub
    elif ai:
        design = (10 - ai["voto_design"]) * 11  # voto 1 -> 99, voto 10 -> 0
        base = round(0.4 * tecnico + 0.6 * design)
        if ai.get("da_contattare") is False:
            base = min(base, 30)
    else:
        base = round(0.8 * tecnico)
    # Tante recensioni Google = attività viva e con clienti: vale di più (fino a +10 da 200 recensioni).
    return min(100, base + (5 if telefono else 0) + min(10, (recensioni or 0) // 20))


def prossima_zona(archivio: Archivio, saltare: set[str]) -> str | None:
    fatte = archivio.zone_completate() | saltare
    for riga in CODA.read_text(encoding="utf-8").splitlines():
        zona = riga.split("#")[0].strip()
        if zona and zona not in fatte:
            return zona
    return None


def raccogli(archivio: Archivio, zona: str, max_google: int = 0, scopri: bool = False, lato: int = 2) -> int:
    log(f"Scarico da OpenStreetMap le attività con sito web in: {zona}")
    try:
        elementi = fonti.scarica_osm(zona)
    except RuntimeError as e:
        # Overpass ogni tanto è giù: se la zona ha già siti in coda, si analizzano quelli invece di fermarsi
        if not archivio.restanti(zona):
            raise
        log(f"⚠️  {e}: oggi si analizzano i siti già in archivio")
        return archivio.aggiorna_conteggio(zona)
    attivita = fonti.estrai_attivita(elementi)
    nuove = archivio.aggiungi_attivita(zona, attivita)
    log(f"Trovate {len(attivita)} PMI con sito ({nuove} nuove, {len(elementi)} elementi OSM grezzi)")
    if attivita and scopri:
        usa_google_maps(archivio, zona, attivita, max_google, solo_migliori=False, lato=lato)
    return archivio.aggiorna_conteggio(zona)


def usa_google_maps(archivio: Archivio, zona: str, attivita: list[dict], massimo: int,
                    solo_migliori: bool = True, lato: int = 2) -> int:
    """1) verifica su Google Maps sito e stato delle attività; 2) cerca quelle che mancano.
    Google costa (~35 $ ogni 1.000 chiamate): di norma si verificano solo i contatti migliori, già analizzati,
    e la ricerca delle attività mancanti si fa solo su richiesta (--scopri-google). Restituisce i siti cambiati."""
    from leadfinder import google_maps as gmaps

    if not gmaps.GoogleMaps.disponibile() or massimo <= 0:
        return 0
    gm = gmaps.GoogleMaps(massimo)
    esclusi = fonti.DOMINI_SOCIAL + fonti.DOMINI_ESCLUSI
    verificate = cambiati = chiuse = scoperte = 0
    try:
        righe = archivio.da_verificare_google(zona, PRIORITA_PROPOSTE if solo_migliori else None)
        log(f"Google Maps: verifico {len(righe)} attività (tetto {massimo} chiamate)…")
        for r in righe:
            if gm.finite():
                break
            g = gmaps.verifica(gm, r["nome"], r["comune"], zona)
            if not g:
                archivio.segna_verificato(r["dominio"])
                continue
            verificate += 1
            if g["stato"] == "CLOSED_PERMANENTLY":
                archivio.segna_chiusa(r["dominio"])
                chiuse += 1
                continue
            dominio = r["dominio"]
            if g["sito"]:
                url = fonti.normalizza_url(g["sito"])
                nuovo = fonti.dominio(url)
                if (nuovo and nuovo != fonti.dominio(r["url"]) and not any(x in nuovo for x in esclusi)
                        and gmaps.sito_plausibile(fonti.dominio(r["url"]), nuovo, bool(r["solo_social"]))):
                    esito = archivio.cambia_sito(dominio, nuovo, url)
                    cambiati += 1
                    log(f"  sito cambiato: {r['nome']}: {r['url']} → {url}")
                    if esito == "doppione":
                        continue
                    dominio = nuovo
                    if r["solo_social"]:
                        archivio.aggiorna(dominio, solo_social=0)
            archivio.salva_google(dominio, g)
            if solo_migliori and dominio == r["dominio"] and r["priorita"] is not None:
                # Già analizzato: aggiunge ora il bonus delle recensioni alla priorità.
                bonus = min(10, (g["recensioni"] or 0) // 20)
                archivio.aggiorna(dominio, priorita=min(100, r["priorita"] + bonus))

        if not solo_migliori:
            # Ricerca per categoria su una griglia sopra la zona (Google dà al massimo 60 risultati a ricerca).
            # Il riquadro di tutta la zona da Google; le attività OSM servono solo se Google non risponde.
            riquadro = gmaps.riquadro_zona(gm, zona)
            if not riquadro:
                lat = [a["lat"] for a in attivita if a.get("lat")]
                lon = [a["lon"] for a in attivita if a.get("lon")]
                riquadro = (min(lat), max(lat), min(lon), max(lon)) if len(lat) >= 20 else None
            if riquadro and (riquadro[1] - riquadro[0]) * (riquadro[3] - riquadro[2]) < 0.004:
                riquadro = None  # troppo piccolo per essere una provincia: dati sbagliati, non si spreca Google
            if not riquadro:
                log("⚠️  Non so quanto è grande la zona: salto la ricerca delle attività mancanti")
            celle = gmaps.griglia(*riquadro, lato=lato) if riquadro else []
            log(f"Google Maps: cerco le attività mancanti su una griglia {lato}×{lato}…")
            trovate: dict[str, list[dict]] = {}
            try:
                for categoria in gmaps.CATEGORIE:
                    for n, cella in enumerate(celle):
                        codice = lato * 100 + n  # griglie diverse non si confondono tra loro
                        if gm.finite() or archivio.ricerca_fatta(zona, categoria, codice):
                            continue
                        for luogo in gm.cerca(categoria, cella, pagine=3):
                            d = gmaps.dati_utili(luogo)
                            a = gmaps.come_attivita(d) if gmaps.nella_zona(d["indirizzo"], zona) else None
                            if a:
                                trovate.setdefault(a["dominio"], []).append(a)
                        if not gm.finite():  # ricerca interrotta dal tetto: la si rifà al prossimo giro
                            archivio.segna_ricerca(zona, categoria, codice)
            except RuntimeError as ex:  # quota finita a metà: si salvano comunque le attività già trovate
                log(f"⚠️  {ex}")
            gia = archivio.domini()
            # Lo stesso sito su 3 o più sedi è una catena, non una PMI.
            # Lo stesso dominio principale su 3 o più sedi (anche con sottodomini diversi) è una catena.
            sedi: dict[str, set] = {}
            for k, v in trovate.items():
                if not v[0]["solo_social"] and not any(k.endswith(h) for h in fonti.HOSTING):
                    sedi.setdefault(".".join(k.split(".")[-2:]), set()).update(x["google"]["google_id"] for x in v)
            catene = {b for b, ids in sedi.items() if len(ids) >= 3}
            nuove = [v[0] for k, v in trovate.items() if k not in gia and len({x["google"]["google_id"] for x in v}) < 3
                     and (v[0]["solo_social"] or ".".join(k.split(".")[-2:]) not in catene)]
            scoperte = archivio.aggiungi_da_google(zona, nuove)
    except RuntimeError as ex:  # chiave sbagliata, quota finita…: il giro continua con quello che ha
        log(f"⚠️  {ex}")
    log(f"Google Maps: {verificate} verificate, {cambiati} siti cambiati, {chiuse} attività chiuse, "
        f"{scoperte} nuove attività trovate ({gm.chiamate} chiamate)")
    return cambiati


def analizza(archivio: Archivio, zona: str, max_siti: int, max_ai: int, lavoratori: int, cartella: Path,
             scadenza: float) -> dict:
    righe = archivio.da_analizzare(zona, max_siti)
    log(f"Controlli tecnici su {len(righe)} siti…")

    def controlla(riga):
        if riga["solo_social"]:
            return riga, {"raggiungibile": True, "problemi": {}, "punteggio": 0}
        return riga, controlli.controlla(riga["url"])

    with ThreadPoolExecutor(lavoratori) as pool:
        esiti = list(pool.map(controlla, righe))

    analizzati = 0

    def salva(r, e, s: dict, ai: dict | None) -> None:
        """Salva subito ogni sito: se il giro si interrompe, il lavoro fatto non va perso."""
        nonlocal analizzati
        priorita = calcola_priorita(bool(r["solo_social"]), e["raggiungibile"], e["punteggio"], ai, r["telefono"],
                                    r["recensioni"])
        tenere_foto = priorita >= SOGLIA_REPORT
        if s.get("desktop") and not tenere_foto:
            shutil.rmtree(Path(s["desktop"]).parent, ignore_errors=True)
        archivio.aggiorna(
            r["dominio"],
            stato="analizzato",
            raggiungibile=int(e["raggiungibile"]),
            punteggio_tecnico=e["punteggio"],
            problemi=controlli.descrivi(e["problemi"]) + ([f"Errore: {e['errore']}"] if e.get("errore") else []),
            voto_design=ai["voto_design"] if ai else None,
            valutazione_ai=ai,
            priorita=priorita,
            email=r["email"] or ", ".join(e.get("email_sito") or []),
            linkedin=(e.get("social") or {}).get("linkedin", ""),
            social=e.get("social") or {},
            canali=e.get("canali"),
            screenshot_desktop=relativo(s.get("desktop")) if tenere_foto else None,
            screenshot_mobile=relativo(s.get("mobile")) if tenere_foto else None,
            analizzato_il=dt.date.today().isoformat(),
        )
        bisogni.aggiorna(archivio, r["dominio"])
        analizzati += 1

    # Solo social e siti irraggiungibili non hanno bisogno di screenshot.
    for r, e in esiti:
        if r["solo_social"] or not e["raggiungibile"]:
            salva(r, e, {}, None)

    # Siti raggiungibili: screenshot + AI, dai peggiori ai migliori secondo i controlli tecnici.
    da_fotografare = sorted(
        [(r, e) for r, e in esiti if e["raggiungibile"] and not r["solo_social"]],
        key=lambda x: x[1]["punteggio"], reverse=True,
    )
    budget_ai = max_ai if valutazione_ai.disponibile() else 0
    if not valutazione_ai.disponibile():
        log("⚠️  OPENAI_API_KEY non impostata: salto il giudizio estetico con l'AI")

    valutati_ai = 0
    in_attesa: list[tuple] = []  # (future AI, riga, esito, screenshot)

    def raccogli_ai(tutti: bool) -> None:
        """Salva i siti la cui valutazione AI è pronta (o tutti, aspettandoli)."""
        nonlocal valutati_ai
        for voce in list(in_attesa):
            futuro, r, e, s = voce
            if not tutti and not futuro.done():
                continue
            in_attesa.remove(voce)
            try:
                ai = futuro.result()
                valutati_ai += 1
            except Exception as ex:
                ai = None
                log(f"  AI non disponibile per {r['dominio']}: {ex}")
            voto = f"design {ai['voto_design']}/10" if ai else "senza AI"
            log(f"  {r['dominio']}: tecnico {e['punteggio']}, {voto}")
            salva(r, e, s, ai)

    if da_fotografare:
        from leadfinder.screenshot import Fotografo
        # Le valutazioni AI girano in parallelo mentre il browser fotografa i siti successivi.
        with Fotografo() as foto, ThreadPoolExecutor(4) as pool_ai:
            for n, (r, e) in enumerate(da_fotografare, 1):
                if time.monotonic() > scadenza:
                    log(f"⏱️  Tempo quasi finito: mi fermo, i {len(da_fotografare) - n + 1} siti rimasti "
                        "verranno analizzati al prossimo giro")
                    break
                cartella_sito = cartella / "img" / report.slug(r["dominio"])
                try:
                    s = foto.fotografa(e.get("url_finale") or r["url"], cartella_sito)
                except Exception as ex:  # timeout, pagina che crasha, ecc.
                    log(f"  [{n}/{len(da_fotografare)}] {r['dominio']}: screenshot fallito ({type(ex).__name__})")
                    salva(r, e, {}, None)
                    continue
                if s["non_adatto_mobile"]:
                    e["problemi"]["non_adatto_mobile"] = {}
                    e["punteggio"] = controlli.punteggio(e["problemi"])
                if n <= budget_ai and s["desktop"]:
                    futuro = pool_ai.submit(valutazione_ai.valuta, r["nome"], r["categoria"], s["desktop"],
                                            s["mobile"], controlli.descrivi(e["problemi"]))
                    in_attesa.append((futuro, r, e, s))
                    log(f"  [{n}/{len(da_fotografare)}] {r['dominio']}: fotografato")
                else:
                    salva(r, e, s, None)
                raccogli_ai(tutti=False)
            raccogli_ai(tutti=True)

    return {"analizzati": analizzati, "valutati_ai": valutati_ai}


def crea_proposte(archivio: Archivio, zona: str, cartella: Path, massimo: int, scadenza: float) -> int:
    """Per i contatti migliori: anteprima del sito rifatto (desktop + mobile) e bozze dei messaggi."""
    from concurrent.futures import as_completed

    from leadfinder import proposta
    from leadfinder.screenshot import Fotografo

    if not valutazione_ai.disponibile() or massimo <= 0:
        return 0
    righe = archivio.senza_proposta(zona, PRIORITA_PROPOSTE, massimo)
    if not righe:
        return 0
    log(f"Preparo le anteprime dei siti rifatti per {len(righe)} contatti (modello {proposta.MODELLO})…")

    def prepara(riga):
        contenuto = proposta.contenuto_sito(riga)
        return contenuto, proposta.genera(riga, contenuto)

    fatte = 0
    with Fotografo() as foto, ThreadPoolExecutor(3) as pool:
        futuri = {pool.submit(prepara, r): r for r in righe}
        for futuro in as_completed(futuri):
            r = futuri[futuro]
            if time.monotonic() > scadenza:
                log("⏱️  Tempo finito: le anteprime mancanti verranno create al prossimo giro")
                for f in futuri:
                    f.cancel()
                break
            try:
                contenuto, dati = futuro.result()
                salvata = proposta.salva_proposta(r, dati, cartella / "proposte" / report.slug(r["dominio"]), foto)
            except Exception as ex:
                log(f"  {r['dominio']}: anteprima non riuscita ({ex})")
                continue
            for chiave in ("desktop", "mobile", "html"):
                salvata[chiave] = relativo(salvata[chiave])
            social = contenuto.get("social") or {}
            archivio.aggiorna(r["dominio"], proposta=salvata,
                              linkedin=r["linkedin"] or social.get("linkedin", ""))
            fatte += 1
            log(f"  {r['dominio']}: anteprima pronta")
    return fatte


def scrivi_report(archivio: Archivio, zona: str, statistiche: dict) -> Path:
    """Report Markdown, CSV e PDF della zona, con tutti i risultati raccolti finora."""
    cartella = REPORT / report.slug(zona) / dt.date.today().isoformat()
    risultati = archivio.risultati(zona)
    report.scrivi_csv(risultati, cartella / "tutti.csv")
    md = report.scrivi_markdown(zona, risultati, cartella, statistiche, RADICE)
    try:
        from leadfinder.pdf import genera_pdf
        genera_pdf(zona, risultati, statistiche, RADICE, cartella / "report.pdf")
    except Exception as ex:  # il PDF è un extra: non deve far fallire il giro
        log(f"⚠️  PDF non generato: {ex}")
    report.aggiorna_indice(REPORT)
    from leadfinder import drive
    if drive.configurato():
        file = drive.file_del_giro(archivio, zona, cartella, RADICE)
        log(f"Copio {len(file)} file su Google Drive…")
        log(f"Google Drive: {drive.carica(file, log)}/{len(file)} file caricati")
    return md


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--zona", help="Sigla provincia (PD), nome provincia, oppure comune:Nome")
    p.add_argument("--dalla-coda", action="store_true", help="Usa la prossima zona di coda_province.txt")
    p.add_argument("--max-siti", type=int, default=500, help="Siti da analizzare in questo giro")
    p.add_argument("--max-ai", type=int, default=500, help="Tetto di valutazioni AI (controllo dei costi)")
    p.add_argument("--max-google", type=int, default=150, help="Tetto di chiamate a Google Maps (costi)")
    p.add_argument("--scopri-google", action="store_true",
                   help="Cerca su Google Maps anche le attività che mancano su OpenStreetMap (costa molto di più)")
    p.add_argument("--griglia", type=int, default=2,
                   help="Ricerca Google: la zona divisa in N×N riquadri (più fitta = più attività, più chiamate)")
    p.add_argument("--max-proposte", type=int, default=0, help="Anteprime del sito rifatto da creare")
    p.add_argument("--aggiorna-dopo", type=int, default=120,
                   help="A coda finita, ricontrolla le zone analizzate da più di tanti giorni")
    p.add_argument("--minuti-max", type=int, default=200, help="Dopo quanti minuti smettere di fotografare")
    p.add_argument("--lavoratori", type=int, default=8, help="Controlli tecnici in parallelo")
    args = p.parse_args()

    archivio = Archivio(ARCHIVIO)
    saltate: set[str] = set()
    zona = args.zona.strip() if args.zona else None

    for _ in range(5):  # con la coda: se una zona non dà risultati passa alla successiva
        if not zona:
            if not args.dalla_coda:
                p.error("indica --zona oppure --dalla-coda")
            zona = prossima_zona(archivio, saltate)
            if not zona:
                zona = archivio.zona_da_aggiornare(args.aggiorna_dopo)
                if not zona:
                    log("Coda completata e archivio aggiornato: niente da fare oggi 🎉")
                    return 0
                log(f"Coda completata: ricontrollo {zona} per trovare le attività nuove")
        trovate = raccogli(archivio, zona, args.max_google, args.scopri_google, args.griglia)
        if trovate or archivio.restanti(zona):
            break
        log(f"Nessuna attività trovata per '{zona}'. Controlla il nome/sigla.")
        archivio.segna_zona(zona, completata=True)
        if not args.dalla_coda:
            return 1
        saltate.add(zona)
        zona = None
    else:
        return 1

    cartella = REPORT / report.slug(zona) / dt.date.today().isoformat()
    scadenza = time.monotonic() + args.minuti_max * 60
    stat = analizza(archivio, zona, args.max_siti, args.max_ai, args.lavoratori, cartella, scadenza)
    # Google Maps solo sui contatti migliori: se il sito è cambiato, si analizza subito quello nuovo.
    if not args.scopri_google and usa_google_maps(archivio, zona, [], args.max_google):
        altro = analizza(archivio, zona, 50, args.max_ai, args.lavoratori, cartella, scadenza + 10 * 60)
        stat = {k: stat[k] + altro[k] for k in stat}
    restanti = archivio.restanti(zona)
    archivio.segna_zona(zona, completata=restanti == 0)

    # Le anteprime hanno un loro margine di tempo, oltre a quello degli screenshot.
    stat["proposte"] = crea_proposte(archivio, zona, cartella, args.max_proposte, scadenza + 25 * 60)
    md = scrivi_report(archivio, zona, {"trovate": trovate, "restanti": restanti, **stat})
    from leadfinder import ai
    log(f"Consumo OpenAI: {ai.riepilogo()}")
    log(f"Fatto. Report: {md.relative_to(RADICE)} — restano {restanti} siti da analizzare in {zona}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
