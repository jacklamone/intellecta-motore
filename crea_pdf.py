"""Rigenera il PDF di una zona con tutti i risultati raccolti finora.

    python crea_pdf.py --zona CR
"""

import argparse
import datetime as dt

from cerca import ARCHIVIO, RADICE, REPORT
from leadfinder import report
from leadfinder.db import Archivio
from leadfinder.pdf import genera_pdf


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--zona", required=True)
    args = p.parse_args()

    archivio = Archivio(ARCHIVIO)
    zona = args.zona.strip()
    riga_zona = archivio.conn.execute("SELECT trovate FROM zone WHERE zona = ?", [zona]).fetchone()
    statistiche = {"trovate": riga_zona[0] if riga_zona else "—", "restanti": archivio.restanti(zona)}
    percorso = REPORT / report.slug(zona) / dt.date.today().isoformat() / "report.pdf"
    genera_pdf(zona, archivio.risultati(zona), statistiche, RADICE, percorso)
    print(percorso.relative_to(RADICE))


if __name__ == "__main__":
    main()
