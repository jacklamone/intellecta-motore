"""Applica all'archivio le regole su catene e pagine di piattaforma (da eseguire dopo averle cambiate).

    python pulisci_archivio.py
"""

from cerca import ARCHIVIO, calcola_priorita
from leadfinder import fonti
from leadfinder.db import Archivio


def main() -> None:
    archivio = Archivio(ARCHIVIO)
    escluse = senza_sito = 0
    for r in archivio.conn.execute("SELECT * FROM siti WHERE stato NOT IN ('chiusa', 'esclusa')").fetchall():
        dom = fonti.dominio(r["url"]) or r["dominio"]
        if fonti.di_catena(dom):
            archivio.aggiorna(r["dominio"], stato="esclusa")
            escluse += 1
        elif not r["solo_social"] and fonti.senza_sito_proprio(dom):
            campi = {"solo_social": 1}
            if r["stato"] == "analizzato":
                campi["priorita"] = calcola_priorita(True, True, 0, None, r["telefono"], r["recensioni"])
            archivio.aggiorna(r["dominio"], **campi)
            senza_sito += 1
    for (zona,) in archivio.conn.execute("SELECT zona FROM zone").fetchall():
        archivio.aggiorna_conteggio(zona)
    print(f"{escluse} catene escluse, {senza_sito} pagine di piattaforma segnate come «senza sito proprio»")


if __name__ == "__main__":
    main()
