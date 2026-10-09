"""Esporta i contatti migliori per il cruscotto: cruscotto/contatti.json + immagini prima/dopo.

    python esporta_cruscotto.py            # tutte le zone
    python esporta_cruscotto.py --min 50   # solo priorità ≥ 50
"""

import argparse
import datetime as dt
import json
import re
import shutil
from urllib.parse import quote_plus

from cerca import ARCHIVIO, RADICE
from leadfinder import report
from leadfinder.db import Archivio
from leadfinder.fonti import ETICHETTE
from leadfinder.pdf import nome_zona
from leadfinder.proposta import link_ricerca_linkedin

USCITA = RADICE / "cruscotto"

# Attività i cui titolari usano davvero LinkedIn: studi professionali, imprese, aziende B2B.
PAROLE_LINKEDIN = (
    "studio", "avvocat", "legale", "commercialist", "notai", "architett", "ingegner", "geometr", "consulen",
    "impresa", "edil", "costruzion", "azienda", "industria", "produtt", "fornitor", "ingrosso", "trasport",
    "logistic", "carpenteri", "metal", "impiant", "serrament", "infissi", "immobiliar", "assicura", "informatic",
    "software", "marketing", "agenzia", "dentist", "odontoiatr", "medic", "fisioterap", "veterinar", "tipografi",
    "progettazion", "ricambi", "concessionari", "elaborazione dati", "formazione", "servizi",
)
# S.r.l. e S.p.A. (le snc/sas sono spesso bar e negozi di famiglia, poco presenti su LinkedIn).
SOCIETA = re.compile(r"\b(s\.?r\.?l\.?s?|s\.?p\.?a\.?)(?=\W|$)", re.I)


def adatto_linkedin(r, categoria_it: str) -> int:
    """2 = ha un profilo LinkedIn collegato al sito; 1 = tipo di attività presente su LinkedIn; 0 = meglio la lettera."""
    if r["linkedin"]:
        return 2
    testo = f"{categoria_it} {r['categoria'] or ''}".lower()
    return 1 if any(p in testo for p in PAROLE_LINKEDIN) or SOCIETA.search(r["nome"] or "") else 0


def categoria(testo: str) -> str:
    return ETICHETTE.get((testo or "").lower().replace(" ", "_"), testo or "")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--min", type=int, default=65, help="Priorità minima (il cruscotto regge circa 500 file)")
    args = p.parse_args()

    archivio = Archivio(ARCHIVIO)
    righe = archivio.conn.execute(
        "SELECT * FROM siti WHERE stato = 'analizzato' AND (priorita >= ? OR proposta IS NOT NULL) AND (voto_design IS NOT NULL "
        "OR solo_social = 1 OR proposta IS NOT NULL) ORDER BY priorita DESC",
        [args.min],
    ).fetchall()

    shutil.rmtree(USCITA / "img", ignore_errors=True)
    contatti = []
    for r in righe:
        ident = report.slug(r["dominio"])[:80]
        ai = json.loads(r["valutazione_ai"] or "{}")
        prop = json.loads(r["proposta"] or "{}")
        social = json.loads(r["social"] or "{}")
        immagini = {}
        for chiave, sorgente in (("prima_desktop", r["screenshot_desktop"]), ("prima_mobile", r["screenshot_mobile"]),
                                 ("dopo_desktop", prop.get("desktop")), ("dopo_mobile", prop.get("mobile"))):
            percorso = report.risolvi(RADICE, sorgente)
            if percorso and percorso.exists():
                destinazione = USCITA / "img" / ident / f"{chiave.replace('_', '-')}.jpg"
                destinazione.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(percorso, destinazione)
                immagini[chiave] = destinazione.relative_to(USCITA).as_posix()
        facebook = social.get("facebook") or (r["url"] if r["solo_social"] and "facebook" in r["url"] else "")
        instagram = social.get("instagram") or (r["url"] if r["solo_social"] and "instagram" in r["url"] else "")
        cat = categoria(r["categoria"])
        contatti.append({
            "id": ident,
            "linkedin_adatto": adatto_linkedin(r, cat),
            "nome": r["nome"],
            "categoria": cat,
            "zona": nome_zona(r["zona"]),
            "comune": r["comune"],
            "indirizzo": r["indirizzo"],
            "telefono": r["telefono"],
            "email": r["email"],
            "sito": r["url"],
            "solo_social": bool(r["solo_social"]),
            "priorita": r["priorita"],
            "voto_google": r["voto_google"],
            "recensioni": r["recensioni"] or 0,
            "mappa": r["mappa"] or "",
            "voto": r["voto_design"],
            "epoca": ai.get("epoca_stimata", ""),
            "difetti": ai.get("difetti") or json.loads(r["problemi"] or "[]")[:3],
            "proposta": ai.get("cosa_proporre", ""),
            "apertura": ai.get("frase_apertura", ""),
            "linkedin": r["linkedin"] or "",
            "linkedin_ricerca": link_ricerca_linkedin(r["nome"], r["comune"]),
            "facebook": facebook,
            "instagram": instagram,
            "instagram_ricerca": "https://www.google.com/search?q=" + quote_plus(f"site:instagram.com {r['nome']} {r['comune']}"),
            "messaggi": {
                "nota": prop.get("nota_collegamento", ""),
                "linkedin": prop.get("messaggio_linkedin", ""),
                "email_oggetto": prop.get("email_oggetto", ""),
                "email_testo": prop.get("email_testo", ""),
            },
            "immagini": immagini,
        })

    USCITA.mkdir(exist_ok=True)
    (USCITA / "contatti.json").write_text(json.dumps({
        "aggiornato": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "contatti": contatti,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(contatti)} contatti esportati in {USCITA.relative_to(RADICE)}/")


if __name__ == "__main__":
    main()
