"""Di cosa ha bisogno ogni attività: sito, chatbot WhatsApp, social, scheda Google.

Ogni bisogno ha un livello (alto / medio / basso, None se non sappiamo ancora) e il motivo in chiaro.
I motivi dicono cosa abbiamo trovato ("non abbiamo trovato…"), mai cose che non possiamo sapere.
"""

import json

ALTO, MEDIO, BASSO = "alto", "medio", "basso"
ORDINE = ["sito", "whatsapp", "google", "social"]
NOMI = {"sito": "Sito", "whatsapp": "WhatsApp", "google": "Google", "social": "Social"}

# Settori che vivono di richieste e prenotazioni: lì un chatbot WhatsApp lavora davvero.
SETTORI_RICHIESTE = (
    "b&b", "bed", "affittacamere", "hotel", "albergo", "residence", "agriturismo", "casa vacanze", "campeggio",
    "ristorante", "pizzeria", "trattoria", "osteria", "agenzia", "escursion", "noleggio", "diving", "barca",
    "parrucch", "barbier", "estetic", "nail", "spa", "massagg", "tatuagg", "palestra", "fitness", "yoga", "piscina",
    "dentist", "odontoiatr", "medic", "fisioterap", "veterinar", "psicolog", "nutrizion", "ottic", "autoscuola",
    "officina", "meccanic", "carrozzer", "gommist", "elettrauto", "autofficina", "idraulic", "elettricist",
    "immobiliar", "fotograf", "wedding", "catering", "pasticceri", "scuola", "lavanderia",
)


def _json(v, vuoto):
    if v is None or v == "":
        return vuoto
    return json.loads(v) if isinstance(v, str) else v


def calcola(r) -> dict:
    """r: riga dell'archivio (sqlite3.Row o dict). Restituisce {bisogno: {"livello", "motivo"}}."""
    get = (lambda k: r[k]) if not isinstance(r, dict) else r.get
    solo_social = bool(get("solo_social"))
    raggiungibile = get("raggiungibile")
    voto = get("voto_design")
    canali = _json(get("canali"), None)
    social = _json(get("social"), None)
    categoria = (get("categoria") or "").lower()
    b = {}

    # Sito
    if solo_social:
        b["sito"] = (ALTO, "Hanno solo una pagina Facebook o Instagram, nessun sito")
    elif raggiungibile == 0:
        b["sito"] = (ALTO, "Il sito non si apre")
    elif voto is not None and voto <= 4:
        b["sito"] = (ALTO, f"Sito datato o fatto male (design {voto}/10)")
    elif voto is not None and voto <= 6:
        b["sito"] = (MEDIO, f"Sito migliorabile (design {voto}/10)")
    elif voto is not None:
        b["sito"] = (BASSO, f"Sito curato (design {voto}/10)")

    # Chatbot WhatsApp
    a_richieste = any(s in categoria for s in SETTORI_RICHIESTE)
    if canali is not None:
        if canali.get("whatsapp") or canali.get("chat"):
            b["whatsapp"] = (BASSO, "Sul sito c'è già un contatto WhatsApp o una chat")
        elif a_richieste and not canali.get("prenotazione"):
            b["whatsapp"] = (ALTO, "Sul sito non abbiamo trovato WhatsApp, chat né prenotazione online")
        elif a_richieste:
            b["whatsapp"] = (MEDIO, "Hanno la prenotazione online ma nessun WhatsApp o chat per le domande")
        else:
            b["whatsapp"] = (MEDIO, "Sul sito non abbiamo trovato WhatsApp né una chat")
    elif solo_social and a_richieste:
        b["whatsapp"] = (ALTO, "Senza sito, i clienti possono scrivere solo sui social: un chatbot WhatsApp risponde subito")
    elif solo_social:
        b["whatsapp"] = (MEDIO, "Senza sito, un chatbot WhatsApp darebbe un contatto diretto")

    # Social
    if solo_social:
        b["social"] = (MEDIO, "Vivono solo sui social: vanno curati e collegati a un sito vero")
    elif social is not None and raggiungibile:
        reti = [n for n in ("facebook", "instagram") if social.get(n)]
        if not reti:
            b["social"] = (ALTO, "Sulla home del sito non c'è nessun link a Facebook o Instagram")
        elif len(reti) == 1:
            manca = "Instagram" if reti == ["facebook"] else "Facebook"
            b["social"] = (MEDIO, f"Sulla home del sito c'è il link a {reti[0].capitalize()} ma non a {manca}")
        else:
            b["social"] = (BASSO, "Sul sito ci sono Facebook e Instagram")

    # Google
    sv = get("scheda_voto")
    if sv is not None:
        difetti = _json(get("scheda_difetti"), [])
        motivo = "; ".join(difetti[:2]) if difetti else "Scheda Google curata"
        b["google"] = (ALTO if sv <= 4 else MEDIO if sv <= 6 else BASSO, f"Scheda Google {sv}/10. {motivo}".rstrip())

    return {k: {"livello": v[0], "motivo": v[1]} for k, v in b.items()}


def pacchetto(bisogni: dict) -> str:
    """Cosa proporre per primo: i bisogni alti; se non ce ne sono, i due medi più importanti."""
    alti = [k for k in ORDINE if bisogni.get(k, {}).get("livello") == ALTO]
    scelti = alti or [k for k in ORDINE if bisogni.get(k, {}).get("livello") == MEDIO][:2]
    return " + ".join(NOMI[k] for k in scelti)


def aggiorna(archivio, dominio: str) -> None:
    r = archivio.conn.execute("SELECT * FROM siti WHERE dominio = ?", [dominio]).fetchone()
    if not r:
        return
    b = calcola(r)
    archivio.aggiorna(dominio, bisogni=b, pacchetto=pacchetto(b))
