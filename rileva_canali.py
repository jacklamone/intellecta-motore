"""Ricontrolla i siti già analizzati per trovare WhatsApp, chat, prenotazione online e link social,
poi ricalcola i bisogni (sito, WhatsApp, social, Google) e il pacchetto consigliato.

    python rileva_canali.py --zona SS            # i siti di Sassari non ancora ricontrollati
    python rileva_canali.py --zona SS --max 3000
    python rileva_canali.py --solo-bisogni       # ricalcola i bisogni di tutto l'archivio, senza scaricare

Non usa Google né OpenAI: scarica solo la home page di ogni sito.
"""

import argparse
import datetime as dt
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bs4 import BeautifulSoup

from leadfinder import bisogni, controlli
from leadfinder.db import Archivio

RADICE = Path(__file__).parent


def log(testo: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {testo}", flush=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--zona", default="", help="Sigla della zona; vuoto = tutte")
    p.add_argument("--max", type=int, default=3000)
    p.add_argument("--lavoratori", type=int, default=16)
    p.add_argument("--solo-bisogni", action="store_true")
    args = p.parse_args()
    archivio = Archivio(RADICE / "dati" / "archivio.sqlite")
    filtro, valori = ("AND zona = ?", [args.zona.upper()]) if args.zona else ("", [])

    if not args.solo_bisogni:
        righe = archivio.conn.execute(
            "SELECT dominio, url FROM siti WHERE stato = 'analizzato' AND raggiungibile = 1 AND solo_social = 0 "
            f"AND canali IS NULL {filtro} ORDER BY priorita DESC LIMIT ?", valori + [args.max]).fetchall()
        log(f"Canali: {len(righe)} siti da ricontrollare")

        def scarica(r):
            pagina = controlli.scarica(r["url"])
            if not pagina["ok"]:
                return r, None, None
            soup = BeautifulSoup(pagina["html"], "html.parser")
            return r, controlli.canali(pagina["html"]), controlli.link_social(soup)

        trovati = {"whatsapp": 0, "chat": 0, "prenotazione": 0}
        fatti = 0
        with ThreadPoolExecutor(args.lavoratori) as pool:
            for r, canali, social in pool.map(scarica, righe):
                if canali is None:
                    continue
                campi = {"canali": canali}
                if social:
                    campi["social"] = social
                archivio.aggiorna(r["dominio"], **campi)
                fatti += 1
                for k in trovati:
                    trovati[k] += canali[k]
        log(f"Canali: {fatti} siti ricontrollati; WhatsApp {trovati['whatsapp']}, chat {trovati['chat']}, "
            f"prenotazione online {trovati['prenotazione']}")

    log(f"Bisogni: esclusi {bisogni.escludi_enti(archivio, args.zona.upper())} enti pubblici")
    domini = [d for (d,) in archivio.conn.execute(
        f"SELECT dominio FROM siti WHERE stato = 'analizzato' {filtro}", valori)]
    for d in domini:
        bisogni.aggiorna(archivio, d)
    conta = archivio.conn.execute(
        f"SELECT pacchetto, COUNT(*) FROM siti WHERE stato = 'analizzato' AND priorita >= 55 {filtro} "
        "GROUP BY pacchetto ORDER BY 2 DESC LIMIT 6", valori).fetchall()
    log(f"Bisogni: ricalcolati per {len(domini)} attività; pacchetti più frequenti tra i buoni contatti: "
        + "; ".join(f"{p or 'nessuno'} {n}" for p, n in conta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
