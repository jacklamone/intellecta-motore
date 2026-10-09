"""Confronta due modelli AI sugli stessi siti già giudicati, per scegliere il più economico senza perdere qualità.

    python confronta_modelli.py --modelli gpt-6-luna,gpt-5-mini --quanti 20

Non modifica l'archivio: scrive solo report/confronto-modelli.md.
"""

import argparse
import json
import random
import statistics

from cerca import ARCHIVIO, RADICE
from leadfinder import ai, report, valutazione_ai
from leadfinder.db import Archivio


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--modelli", default="gpt-6-luna,gpt-5-mini")
    p.add_argument("--quanti", type=int, default=20)
    args = p.parse_args()
    modelli = [m.strip() for m in args.modelli.split(",") if m.strip()]

    righe = []
    for r in Archivio(ARCHIVIO).conn.execute(
            "SELECT * FROM siti WHERE stato = 'analizzato' AND voto_design IS NOT NULL AND screenshot_desktop IS NOT NULL"):
        d, m = report.risolvi(RADICE, r["screenshot_desktop"]), report.risolvi(RADICE, r["screenshot_mobile"])
        if d and d.exists():
            righe.append((r, d, m if m and m.exists() else None))
    random.Random(42).shuffle(righe)
    righe = righe[:args.quanti]

    risultati = {m: [] for m in modelli}
    for modello in modelli:
        for r, d, m in righe:
            valutazione_ai.MODELLO = modello
            try:
                v = valutazione_ai.valuta(r["nome"], r["categoria"], str(d), str(m) if m else None,
                                          json.loads(r["problemi"] or "[]"))
                usato = valutazione_ai.MODELLO
            except Exception as ex:  # noqa: BLE001
                v, usato = {"errore": str(ex)[:120]}, modello
            risultati[modello].append((v, usato))
            print(f"{modello:12} {r['nome'][:40]:40} vecchio {r['voto_design']} → {v.get('voto_design', '?')}", flush=True)

    vecchi = [r["voto_design"] for r, _, _ in righe]
    vecchi_contattare = [json.loads(r["valutazione_ai"] or "{}").get("da_contattare") for r, _, _ in righe]
    righe_md = ["# Confronto modelli AI", "",
                f"{len(righe)} siti già giudicati in passato, rigiudicati con: {', '.join(modelli)}.", "",
                "| Modello | Usato davvero | Differenza media dal voto originale | Stesso «da contattare» | Errori |",
                "|---|---|---|---|---|"]
    for modello in modelli:
        voti = [(v.get("voto_design"), o) for (v, _), o in zip(risultati[modello], vecchi) if "voto_design" in v]
        diff = statistics.mean(abs(a - b) for a, b in voti) if voti else float("nan")
        uguali = sum(1 for (v, _), c in zip(risultati[modello], vecchi_contattare) if v.get("da_contattare") == c)
        usati = {u for _, u in risultati[modello]}
        errori = sum(1 for v, _ in risultati[modello] if "errore" in v)
        righe_md.append(f"| {modello} | {', '.join(sorted(usati))} | {diff:.2f} | {uguali}/{len(righe)} | {errori} |")
    righe_md += ["", "## Dettaglio", "", "| Sito | Originale | " + " | ".join(modelli) + " |",
                 "|---|---|" + "---|" * len(modelli)]
    for i, (r, _, _) in enumerate(righe):
        celle = [str(risultati[m][i][0].get("voto_design", "errore")) for m in modelli]
        righe_md.append(f"| {r['nome']} | {r['voto_design']} | " + " | ".join(celle) + " |")
    righe_md += ["", "## Esempio di difetti (primo sito)", ""]
    for m in modelli:
        righe_md.append(f"- **{m}**: " + "; ".join(risultati[m][0][0].get("difetti", [])) if righe else "")
    righe_md += ["", f"Consumo: {ai.riepilogo()}"]
    uscita = RADICE / "report" / "confronto-modelli.md"
    uscita.write_text("\n".join(righe_md) + "\n", encoding="utf-8")
    print("\n".join(righe_md))


if __name__ == "__main__":
    main()
