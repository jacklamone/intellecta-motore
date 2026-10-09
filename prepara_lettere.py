"""Prepara le lettere di carta e le pagine personali (QR code) per i contatti migliori di una zona.

    python prepara_lettere.py --zona LO --quanti 30

Crea:
  report/<zona>/lettere-<data>/lettere.pdf   da stampare (una pagina A4 per azienda)
  report/<zona>/lettere-<data>/indirizzi.csv per i servizi di posta online (si apre con Excel)
  pagine/per/<codice>/                       pagine personali da pubblicare su intellectasolutions.it/per/
Servono le anteprime (Crea anteprime e messaggi). Chi ha chiesto di non essere contattato viene saltato.
"""

import argparse
import csv
import datetime as dt
import sys

from cerca import ARCHIVIO, RADICE, REPORT, log
from leadfinder import lettere, report
from leadfinder.db import Archivio

CONFIG = RADICE / "lettere_config.json"
PAGINE = RADICE / "pagine" / "per"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--zona", required=True)
    p.add_argument("--quanti", type=int, default=30)
    p.add_argument("--anche-gia-preparate", action="store_true", help="Rifà anche le lettere già preparate")
    args = p.parse_args()

    cfg = lettere.carica_config(CONFIG)
    if mancano := lettere.mancanti(cfg):
        log(f"⚠️  Da completare in lettere_config.json: {', '.join(mancano)} (le lettere li mostrano tra parentesi)")
    archivio = Archivio(ARCHIVIO)
    zona = args.zona.strip()
    filtro = "" if args.anche_gia_preparate else " AND lettera_preparata IS NULL"
    righe = archivio.conn.execute(
        "SELECT * FROM siti WHERE zona = ? AND stato = 'analizzato' AND proposta IS NOT NULL "
        f"AND COALESCE(non_contattare, 0) = 0{filtro} ORDER BY priorita DESC LIMIT ?",
        [zona, args.quanti]).fetchall()
    if not righe:
        log("Nessun contatto con anteprima da preparare: crea prima le anteprime.")
        return 1
    cartella = REPORT / report.slug(zona) / f"lettere-{dt.date.today().isoformat()}"
    log(f"Preparo {len(righe)} lettere per {zona}…")
    fatte = lettere.prepara(archivio, righe, cfg, RADICE, PAGINE, cartella, log)
    with open(cartella / "indirizzi.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Azienda", "Indirizzo", "Indirizzo verificato", "Pagina personale", "Telefono", "Priorità"])
        for x in fatte:
            w.writerow([x["nome"], x["indirizzo"], "sì" if x["indirizzo_sicuro"] else "NO, controllare",
                        x["pagina"], x["telefono"], x["priorita"]])
    from leadfinder import drive
    from leadfinder.pdf import nome_zona
    if drive.configurato():
        base = f"{nome_zona(zona).replace('Provincia di ', '')}/Lettere {dt.date.today().strftime('%d-%m-%Y')}"
        file = [(f"{base}/Lettere da stampare.pdf", (cartella / "lettere.pdf").read_bytes(), "application/pdf"),
                (f"{base}/Indirizzi (Excel).csv", (cartella / "indirizzi.csv").read_bytes(), "text/csv")]
        log(f"Google Drive: {drive.carica(file, log)}/{len(file)} file caricati")
    da_controllare = sum(1 for x in fatte if not x["indirizzo_sicuro"])
    log(f"Fatto: {len(fatte)} lettere in {cartella.relative_to(RADICE)}"
        + (f" — {da_controllare} indirizzi da controllare a mano" if da_controllare else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
