"""Crea le anteprime dei siti rifatti e le bozze dei messaggi per i contatti migliori di una zona
già analizzata, poi rigenera report e PDF.

    python crea_proposte.py --zona CR --max 15
"""

import argparse
import time

from cerca import ARCHIVIO, REPORT, crea_proposte, log, scrivi_report
from leadfinder import report
from leadfinder.db import Archivio


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--zona", required=True)
    p.add_argument("--max", type=int, default=15, help="Quante anteprime creare")
    p.add_argument("--minuti-max", type=int, default=150)
    p.add_argument("--rifai", action="store_true",
                   help="Rifà anche le anteprime già esistenti dei contatti migliori (es. dopo aver cambiato lo stile)")
    args = p.parse_args()

    import datetime as dt
    archivio = Archivio(ARCHIVIO)
    zona = args.zona.strip()
    cartella = REPORT / report.slug(zona) / dt.date.today().isoformat()
    if args.rifai:
        da_rifare = archivio.conn.execute(
            "SELECT dominio FROM siti WHERE zona = ? AND proposta IS NOT NULL AND stato = 'analizzato' "
            "ORDER BY priorita DESC LIMIT ?", [zona, args.max]).fetchall()
        for (dominio,) in da_rifare:
            archivio.aggiorna(dominio, proposta=None)
        log(f"Rifaccio {len(da_rifare)} anteprime già esistenti")
    fatte = crea_proposte(archivio, zona, cartella, args.max, time.monotonic() + args.minuti_max * 60)
    riga_zona = archivio.conn.execute("SELECT trovate FROM zone WHERE zona = ?", [zona]).fetchone()
    md = scrivi_report(archivio, zona, {
        "trovate": riga_zona[0] if riga_zona else "—", "restanti": archivio.restanti(zona),
        "analizzati": len(archivio.risultati(zona)), "valutati_ai": 0, "proposte": fatte,
    })
    from leadfinder import ai
    log(f"Consumo OpenAI: {ai.riepilogo()}")
    log(f"Fatto: {fatte} anteprime. Report: {md}")


if __name__ == "__main__":
    main()
