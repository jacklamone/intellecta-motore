"""Carica su Google Drive i report già fatti (tutte le zone, o una sola).

    python carica_drive.py            # tutte le zone
    python carica_drive.py --zona CR
"""

import argparse
import sys

from cerca import ARCHIVIO, RADICE, REPORT, log
from leadfinder import drive
from leadfinder.db import Archivio


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--zona", help="Sigla della zona (es. CR); vuoto = tutte")
    args = p.parse_args()
    if not drive.configurato():
        log("DRIVE_UPLOAD_URL e DRIVE_TOKEN non impostati: niente da fare")
        return 1

    archivio = Archivio(ARCHIVIO)
    totale = 0
    # Per ogni zona solo il giro più recente: ha già tutte le anteprime della zona.
    ultime = {}
    for cartella in sorted(REPORT.glob("*/*")):
        if cartella.is_dir():
            ultime[cartella.parent.name.upper()] = cartella
    for zona, cartella in sorted(ultime.items()):
        if args.zona and zona != args.zona.upper():
            continue
        file = drive.file_del_giro(archivio, zona, cartella, RADICE)
        fatti = drive.carica(file, log)
        totale += fatti
        log(f"{zona} {cartella.name}: {fatti}/{len(file)} file su Drive")
    return 0 if totale else 1


if __name__ == "__main__":
    sys.exit(main())
