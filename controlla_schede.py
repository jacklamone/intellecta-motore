"""Controlla la scheda Google Maps dei contatti migliori: voto 0-10, difetti, bonus di priorità.

    python controlla_schede.py --zona SS --max 400          # i migliori di Sassari non ancora controllati
    python controlla_schede.py --zona SS --max 400 --min 65

Costa una chiamata Google per attività (vedi leadfinder/scheda_google.py).
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from leadfinder import google_maps as gmaps
from leadfinder import scheda_google
from leadfinder.db import Archivio

RADICE = Path(__file__).parent


def log(testo: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {testo}", flush=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--zona", required=True)
    p.add_argument("--max", type=int, default=300, help="Tetto di chiamate a Google")
    p.add_argument("--min", type=int, default=55, help="Priorità minima")
    args = p.parse_args()
    if not gmaps.GoogleMaps.disponibile():
        log("GOOGLE_MAPS_API_KEY non impostata: niente da fare")
        return 1

    archivio = Archivio(RADICE / "dati" / "archivio.sqlite")
    righe = archivio.conn.execute(
        "SELECT dominio, nome, priorita, google_id FROM siti WHERE zona = ? AND stato = 'analizzato' "
        "AND priorita >= ? AND google_id IS NOT NULL AND google_id != '' AND scheda_controllata IS NULL "
        "ORDER BY priorita DESC LIMIT ?", [args.zona.upper(), args.min, args.max]).fetchall()
    log(f"Schede Google: {len(righe)} da controllare in {args.zona.upper()} (tetto {args.max} chiamate)")

    gm = gmaps.GoogleMaps(args.max)
    fatte = deboli = 0
    for r in righe:
        if gm.finite():
            break
        d = scheda_google.scarica(gm, r["google_id"])
        oggi = dt.date.today().isoformat()
        if d is None:
            archivio.conn.execute("UPDATE siti SET scheda_controllata = ? WHERE dominio = ?", [oggi, r["dominio"]])
            continue
        voto, difetti = scheda_google.valuta(d)
        fatte += 1
        bonus = scheda_google.bonus_priorita(voto)
        deboli += voto <= 4
        archivio.conn.execute(
            "UPDATE siti SET scheda_voto = ?, scheda_difetti = ?, scheda_controllata = ?, priorita = MIN(100, priorita + ?) "
            "WHERE dominio = ?", [voto, json.dumps(difetti, ensure_ascii=False), oggi, bonus, r["dominio"]])
        log(f"  {r['nome']}: scheda {voto}/10 {'; '.join(difetti)}")
        archivio.conn.commit()
    archivio.conn.commit()
    log(f"Schede Google: {fatte} controllate, {deboli} trascurate (voto ≤ 4), {gm.chiamate} chiamate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
