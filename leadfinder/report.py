"""Report leggibile direttamente su GitHub (Markdown con immagini) + CSV per Excel."""

import csv
import datetime as dt
import json
import os
import re
from pathlib import Path


def slug(testo: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", testo.lower()).strip("-") or "zona"


def risolvi(radice: Path, percorso: str | None) -> Path | None:
    """Percorso di uno screenshot salvato nell'archivio (relativo alla radice; i vecchi erano assoluti)."""
    if not percorso:
        return None
    p = Path(percorso)
    if p.is_absolute() and "/report/" in percorso:
        p = Path("report") / percorso.split("/report/", 1)[1]
    return radice / p


def _problemi(riga) -> list[str]:
    return json.loads(riga["problemi"] or "[]")


def _ai(riga) -> dict:
    return json.loads(riga["valutazione_ai"] or "{}")


def _cella(testo) -> str:
    return str(testo or "").replace("|", "/").replace("\n", " ")


def stelle(r) -> str:
    """Es. "★ 4,6 (240 recensioni Google)"; vuoto se non c'è la scheda Google."""
    if not r["voto_google"]:
        return ""
    return f"★ {r['voto_google']:.1f} ({r['recensioni']} recensioni Google)".replace(".", ",")


def linkedin_md(r) -> str:
    from .proposta import link_ricerca_linkedin
    if r["linkedin"]:
        return f"💼 [Pagina LinkedIn]({r['linkedin']})"
    return f"💼 LinkedIn non trovato nel sito — [cercalo su LinkedIn]({link_ricerca_linkedin(r['nome'], r['comune'])})"


def _proposta(r) -> dict:
    return json.loads(r["proposta"] or "{}")


def proposta_md(r, radice: Path, cartella: Path) -> list[str]:
    p = _proposta(r)
    if not p:
        return []
    out = ["### ✨ Come potrebbe essere il nuovo sito", ""]
    immagini = [f'<img src="{os.path.relpath(risolvi(radice, p[k]), cartella)}" width="{w}">'
                for k, w in (("desktop", 560), ("mobile", 180)) if p.get(k)]
    out += [" ".join(immagini), ""]
    if p.get("html"):
        out += [f"[Apri l'anteprima completa (HTML)]({os.path.relpath(risolvi(radice, p['html']), cartella)})", ""]
    for titolo, testo in (("Nota per il collegamento LinkedIn", p.get("nota_collegamento")),
                          ("Messaggio LinkedIn", p.get("messaggio_linkedin")),
                          (f"Email — oggetto: {p.get('email_oggetto', '')}", p.get("email_testo"))):
        if testo:
            out += [f"<details><summary><b>{titolo}</b></summary>", "", testo, "", "</details>", ""]
    return out


def scrivi_csv(righe, percorso: Path) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    # Punto e virgola + BOM: Excel italiano lo apre correttamente con doppio clic.
    with open(percorso, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Priorità", "Nome", "Categoria", "Comune", "Indirizzo", "Telefono", "Email", "Sito",
                    "Voto design (1-10)", "Epoca stimata", "Problemi", "Cosa proporre", "Frase di apertura",
                    "LinkedIn", "Messaggio LinkedIn", "Oggetto email", "Testo email", "Voto Google",
                    "Recensioni Google", "Scheda (Google Maps o OpenStreetMap)"])
        for r in righe:
            ai = _ai(r)
            w.writerow([
                r["priorita"], r["nome"], r["categoria"], r["comune"], r["indirizzo"], r["telefono"], r["email"],
                r["url"], r["voto_design"] or "", ai.get("epoca_stimata", ""),
                " · ".join(ai.get("difetti") or _problemi(r)), ai.get("cosa_proporre", ""),
                ai.get("frase_apertura", ""), r["linkedin"], _proposta(r).get("messaggio_linkedin", ""),
                _proposta(r).get("email_oggetto", ""), _proposta(r).get("email_testo", ""),
                r["voto_google"] or "", r["recensioni"] or "", r["mappa"] or r["osm"],
            ])


def scrivi_markdown(zona: str, righe, cartella: Path, statistiche: dict, radice: Path,
                    max_schede: int = 60) -> Path:
    percorso = cartella / "README.md"
    oggi = dt.date.today().strftime("%d/%m/%Y")
    righe = list(righe)
    migliori = [r for r in righe if r["priorita"] and r["priorita"] >= 40][:max_schede]

    out = [
        f"# Siti da rifare — {zona} ({oggi})",
        "",
        f"- Attività con sito trovate nella zona: **{statistiche['trovate']}**",
        f"- Siti analizzati in questo giro: **{statistiche['analizzati']}**",
        f"- Valutati dall'AI: **{statistiche['valutati_ai']}**",
        f"- Contatti promettenti (priorità ≥ 40): **{len(migliori)}**",
        f"- Ancora da analizzare in questa zona: **{statistiche['restanti']}**",
        "",
        "📥 [Scarica l'elenco completo per Excel](tutti.csv)",
        "",
        "**Priorità** (0-100): più è alta, più il sito è vecchio e più vale la pena chiamare.",
        "",
        "## Riepilogo",
        "",
        "| # | Priorità | Attività | Categoria | Telefono | Sito | Voto design |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(migliori, 1):
        voto = f"{r['voto_design']}/10" if r["voto_design"] else "—"
        out.append(
            f"| {i} | **{r['priorita']}** | [{_cella(r['nome'])}](#{i}) | {_cella(r['categoria'])} | "
            f"{_cella(r['telefono']) or '—'} | [{_cella(r['url'])}]({r['url']}) | {voto} |"
        )
    out.append("")

    for i, r in enumerate(migliori, 1):
        ai = _ai(r)
        out += [f'<a id="{i}"></a>', "", f"## {i}. {r['nome']} — priorità {r['priorita']}", ""]
        dati = [r["categoria"], r["comune"], r["indirizzo"], r["telefono"], r["email"], stelle(r)]
        out.append(" · ".join(_cella(d) for d in dati if d))
        out += ["", f"🌐 {r['url']}", "", linkedin_md(r), ""]
        if r["solo_social"]:
            out += ["**Non ha un sito vero: usa solo una pagina social.** Proposta ideale: sito + chatbot.", ""]
        elif not r["raggiungibile"]:
            out += ["**Il sito non si apre dai nostri server.** Verificate a mano: se non si apre neanche a voi, "
                    "è scaduto o abbandonato (ottimo motivo per chiamare).", ""]
        if ai:
            out += [f"**Voto design:** {r['voto_design']}/10 · **Sembra del:** {ai.get('epoca_stimata', '?')}", ""]
        difetti = ai.get("difetti") or []
        tecnici = _problemi(r)
        if difetti or tecnici:
            out.append("**Cosa non va:**")
            out += [f"- {d}" for d in difetti]
            if tecnici:
                out.append(f"- *Controlli tecnici:* {'; '.join(tecnici)}")
            out.append("")
        if ai.get("cosa_proporre"):
            out += [f"**Cosa proporre:** {ai['cosa_proporre']}", ""]
        if ai.get("frase_apertura"):
            out += [f"> 📞 {ai['frase_apertura']}", ""]
        immagini = []
        for colonna, larghezza in (("screenshot_desktop", 560), ("screenshot_mobile", 180)):
            immagine = risolvi(radice, r[colonna])
            if immagine:
                immagini.append(f'<img src="{os.path.relpath(immagine, cartella)}" width="{larghezza}">')
        if immagini:
            out += [" ".join(immagini), ""]
        out += proposta_md(r, radice, cartella)
        out += ["---", ""]

    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text("\n".join(out), encoding="utf-8")
    return percorso


def aggiorna_indice(radice: Path) -> None:
    """report/README.md: elenco di tutti i giri, dal più recente."""
    giri = sorted(radice.glob("*/*/README.md"), key=lambda p: p.parent.name, reverse=True)
    out = ["# Report", "", "| Data | Zona | Report | Excel |", "|---|---|---|---|"]
    for p in giri:
        rel = p.parent.relative_to(radice).as_posix()
        out.append(f"| {p.parent.name} | {p.parent.parent.name} | [apri]({rel}/README.md) | [csv]({rel}/tutti.csv) |")
    (radice / "README.md").write_text("\n".join(out) + "\n", encoding="utf-8")
