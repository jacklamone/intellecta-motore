"""Qualità della scheda Google Maps (Google Business Profile): foto, orari, recensioni, contatti.

Una chiamata "Place Details" per attività, che Google conta come "Enterprise" (orari, voto, sito):
20 $ ogni 1.000, ma le prime 1.000 di ogni mese sono gratuite.
"""

import requests

URL = "https://places.googleapis.com/v1/places/{}"
CAMPI = "photos,regularOpeningHours,rating,userRatingCount,websiteUri,nationalPhoneNumber"


def scarica(gm, google_id: str) -> dict | None:
    """Dati della scheda; None se Google non la trova più."""
    r = requests.get(URL.format(google_id), params={"languageCode": "it"}, timeout=30,
                     headers={"X-Goog-Api-Key": gm.chiave, "X-Goog-FieldMask": CAMPI})
    gm.chiamate += 1
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise RuntimeError(f"Google Maps HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def valuta(d: dict) -> tuple[int, list[str]]:
    """Voto 0-10 della scheda (10 = curata) e i difetti, scritti per il titolare."""
    voto, difetti = 0, []

    foto = len(d.get("photos") or [])  # Google ne elenca al massimo 10
    if foto >= 10:
        voto += 3
    elif foto >= 5:
        voto += 2
    elif foto >= 1:
        voto += 1
        difetti.append(f"Sulla scheda Google ci sono solo {foto} foto")
    else:
        difetti.append("Sulla scheda Google non c'è nessuna foto")

    if d.get("regularOpeningHours"):
        voto += 3
    else:
        difetti.append("Gli orari di apertura non sono indicati su Google")

    recensioni = d.get("userRatingCount") or 0
    if recensioni >= 50:
        voto += 2
    elif recensioni >= 10:
        voto += 1
    else:
        difetti.append(f"Poche recensioni su Google ({recensioni})")
    # Niente controllo sulla data delle recensioni: Google restituisce le 5 "più pertinenti", non le più
    # recenti, quindi "l'ultima recensione è di N mesi fa" potrebbe essere falso.

    if d.get("nationalPhoneNumber"):
        voto += 1
    else:
        difetti.append("Il telefono non è indicato su Google")
    if d.get("websiteUri"):
        voto += 1
    else:
        difetti.append("Il sito non è collegato alla scheda Google")
    return voto, difetti


def bonus_priorita(voto: int) -> int:
    """Una scheda trascurata è un motivo in più per contattarli (e un servizio in più da proporre)."""
    return 10 if voto <= 4 else 5 if voto <= 6 else 0
