"""Giudizio estetico degli screenshot con un modello OpenAI con visione."""

import base64
import json
import os

from openai import BadRequestError, NotFoundError

from .ai import chiedi

# Scelto col confronto del 1/10/2026 (report/confronto-modelli.md): gpt-5-mini dà voti stabili (±0,15),
# gpt-5-nano ±0,4 e testi in italiano meno curati, gpt-6-luna voti sistematicamente più bassi di ~1 punto.
# Con la tariffa flex gpt-5-mini costa ~0,04 centesimi a sito: il risparmio degli altri non vale la qualità.
MODELLO = os.environ.get("OPENAI_MODEL") or "gpt-5-mini"
RISERVA = "gpt-5-mini"

ISTRUZIONI = """Sei un web designer senior di Intellecta Solutions, agenzia che crea siti web, chatbot WhatsApp
e campagne social per piccole e medie imprese italiane. Ricevi due screenshot della home page di un'attività:
il primo da computer, il secondo da cellulare.

Valuta il sito con occhio professionale ma onesto: se è moderno e curato, dillo.
Considera: modernità dello stile, tipografia, uso dello spazio, qualità di foto e grafica,
leggibilità su cellulare, chiarezza di cosa fa l'attività e di come contattarla (call to action).

Rispondi SOLO con un oggetto JSON con queste chiavi:
- "voto_design": intero da 1 (vecchissimo/pessimo) a 10 (moderno ed eccellente)
- "epoca_stimata": stringa, gli anni in cui sembra fatto (es. "2008-2012")
- "difetti": lista di massimo 3 frasi brevi, comprensibili per il titolare (niente gergo tecnico)
- "cosa_proporre": frase breve su cosa proporre (es. nuovo sito, chatbot WhatsApp per prenotazioni, social)
- "frase_apertura": una frase cordiale e rispettosa per aprire una telefonata col titolare, senza offendere
- "da_contattare": true se vale la pena proporre un rifacimento, altrimenti false"""


def _immagine(percorso: str) -> dict:
    with open(percorso, "rb") as f:
        dati = base64.b64encode(f.read()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{dati}", "detail": "low"}}


def disponibile() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def valuta(nome: str, categoria: str, desktop: str, mobile: str | None, problemi_tecnici: list[str]) -> dict:
    contenuto = [
        {"type": "text", "text": (
            f"Attività: {nome} ({categoria}).\n"
            f"Problemi tecnici già rilevati: {', '.join(problemi_tecnici) or 'nessuno'}."
        )},
        _immagine(desktop),
    ]
    if mobile:
        contenuto.append(_immagine(mobile))
    global MODELLO
    parametri = dict(
        model=MODELLO,
        messages=[
            {"role": "system", "content": ISTRUZIONI},
            {"role": "user", "content": contenuto},
        ],
        response_format={"type": "json_object"},
    )
    if MODELLO.startswith(("gpt-5", "gpt-6")):
        parametri["reasoning_effort"] = "minimal"
    try:
        risposta = chiedi(parametri)
    except (BadRequestError, NotFoundError) as ex:
        if MODELLO == RISERVA:
            raise
        print(f"Modello {MODELLO} non utilizzabile ({ex.__class__.__name__}): passo a {RISERVA}", flush=True)
        MODELLO = parametri["model"] = RISERVA
        parametri["reasoning_effort"] = "minimal"
        risposta = chiedi(parametri)
    dati = json.loads(risposta.choices[0].message.content)
    dati["voto_design"] = max(1, min(10, int(dati.get("voto_design", 5))))
    dati["difetti"] = [str(d) for d in (dati.get("difetti") or [])][:3]
    return dati
