"""Google Maps (Places API New): verifica il sito delle attività già trovate e ne scopre di nuove.

Serve la variabile GOOGLE_MAPS_API_KEY (chiave Google Cloud con "Places API (New)" attiva).
Ogni chiamata è a pagamento oltre la quota gratuita mensile: il numero di chiamate per giro ha un tetto.
"""

import difflib
import os
import re
import unicodedata

import requests

from .fonti import CAP_ZONA, COMUNI_EXTRA, DOMINI_ESCLUSI, RIQUADRI_FISSI, di_catena, dominio, normalizza_url, senza_sito_proprio
from .pdf import PROVINCE

URL = "https://places.googleapis.com/v1/places:searchText"
CAMPI = ",".join(f"places.{c}" for c in (
    "id", "displayName", "websiteUri", "nationalPhoneNumber", "formattedAddress", "rating",
    "userRatingCount", "businessStatus", "primaryTypeDisplayName", "googleMapsUri", "location",
)) + ",nextPageToken"

# Ricerche per scoprire le attività che mancano su OpenStreetMap.
CATEGORIE = [
    "ristorante", "pizzeria", "bar caffetteria", "hotel", "bed and breakfast", "agriturismo",
    "parrucchiere", "centro estetico", "dentista", "studio medico", "fisioterapista", "veterinario",
    "ottico", "palestra", "autofficina", "carrozzeria", "concessionaria auto", "gommista",
    "idraulico", "elettricista", "impresa edile", "serramenti", "falegnameria", "negozio di arredamento",
    "negozio di abbigliamento", "gioielleria", "fiorista", "panificio", "pasticceria", "gelateria",
    "macelleria", "enoteca", "commercialista", "studio legale", "agenzia immobiliare", "assicurazioni",
    "agenzia viaggi", "autoscuola", "onoranze funebri", "ferramenta", "tipografia", "fotografo",
    "scuola di danza", "centro sportivo", "lavanderia", "azienda agricola", "officina meccanica",
    "studio tecnico geometra",
]


class GoogleMaps:
    def __init__(self, massimo_chiamate: int):
        self.chiave = os.environ["GOOGLE_MAPS_API_KEY"]
        self.massimo = massimo_chiamate
        self.chiamate = 0

    @staticmethod
    def disponibile() -> bool:
        return bool(os.environ.get("GOOGLE_MAPS_API_KEY"))

    def finite(self) -> bool:
        return self.chiamate >= self.massimo

    def cerca(self, testo: str, rettangolo: dict | None = None, pagine: int = 1, risultati: int = 20) -> list[dict]:
        luoghi, token = [], None
        for _ in range(pagine):
            if self.finite():
                break
            corpo = {"textQuery": testo, "languageCode": "it", "regionCode": "IT", "pageSize": risultati}
            if rettangolo:
                corpo["locationRestriction"] = {"rectangle": rettangolo}
            if token:
                corpo["pageToken"] = token
            r = requests.post(URL, json=corpo, timeout=30, headers={
                "X-Goog-Api-Key": self.chiave, "X-Goog-FieldMask": CAMPI,
            })
            self.chiamate += 1
            if r.status_code != 200:
                raise RuntimeError(f"Google Maps HTTP {r.status_code}: {r.text[:300]}")
            dati = r.json()
            luoghi += dati.get("places", [])
            token = dati.get("nextPageToken")
            if not token:
                break
        return luoghi


def _semplice(testo: str) -> str:
    testo = unicodedata.normalize("NFKD", testo or "").encode("ascii", "ignore").decode().lower()
    testo = re.sub(r"\b(srl|s\.r\.l|snc|sas|spa|di|da|del|della|dei|e|&)\b", " ", testo)
    return re.sub(r"[^a-z0-9]+", " ", testo).strip()


def stesso_nome(a: str, b: str) -> bool:
    a, b = _semplice(a), _semplice(b)
    if not a or not b:
        return False
    return a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= 0.6


def nella_zona(indirizzo: str, zona: str) -> bool:
    """Gli indirizzi Google finiscono con "26100 Cremona CR, Italia": controlliamo la sigla o il comune."""
    if zona.lower().startswith("comune:"):
        return zona.split(":", 1)[1].strip().lower() in (indirizzo or "").lower()
    if re.fullmatch(r"[A-Za-z]{2}", zona):
        cap = CAP_ZONA.get(zona.upper())
        if cap and re.search(rf"\b{cap}\d{{{5 - len(cap)}}}\s", indirizzo or ""):
            return True  # es. Olbia "07026 Olbia SS" o con la sigla nuova della Gallura
        if any(c.lower() in (indirizzo or "").lower() for c in COMUNI_EXTRA.get(zona.upper(), ())):
            return True
        return re.search(rf"\b\d{{5}}\s+[^,]+\s{zona.upper()}\b", indirizzo or "") is not None
    return zona.lower() in (indirizzo or "").lower()


def dati_utili(luogo: dict) -> dict:
    return {
        "google_id": luogo.get("id", ""),
        "nome": (luogo.get("displayName") or {}).get("text", ""),
        "sito": luogo.get("websiteUri") or "",
        "telefono": luogo.get("nationalPhoneNumber") or "",
        "indirizzo": luogo.get("formattedAddress") or "",
        "voto": luogo.get("rating"),
        "recensioni": luogo.get("userRatingCount") or 0,
        "stato": luogo.get("businessStatus") or "",
        "categoria": (luogo.get("primaryTypeDisplayName") or {}).get("text", ""),
        "mappa": luogo.get("googleMapsUri") or "",
        "lat": (luogo.get("location") or {}).get("latitude"),
        "lon": (luogo.get("location") or {}).get("longitude"),
    }


# Piattaforme che ospitano pagine di molte attività (menu, prenotazioni, schede): non sono il loro sito.
PIATTAFORME = (
    "mycia.it", "eatbu.com", "thefork.", "tripadvisor.", "booking.com", "glovoapp.com", "justeat.",
    "deliveroo.", "ubereats.com", "paginegialle.it", "paginebianche.it", "virgilio.it", "linktr.ee",
    "wa.me", "menu.", "plateform.", "quandoo.", "treatwell.", "miodottore.it", "prontopro.it",
    "subito.it", "immobiliare.it", "idealista.it", "airbnb.", "expedia.", "trivago.",
)


def _parti(host: str) -> list[str]:
    return [p for p in host.lower().split(".") if p and p != "www"]


def sito_plausibile(vecchio: str, nuovo: str, era_social: bool) -> bool:
    """Il sito indicato da Google è davvero il nuovo sito dell'attività?
    Sì per un dominio suo (veneroni.com → veneroni.it); no per una pagina ospitata da altri
    (borghipiubelliditalia.mycia.it, ristorante-x.eatbu.com, agenzia.generali.it) quando c'era già un sito vero."""
    if any(p in nuovo for p in PIATTAFORME):
        return False
    if era_social:
        return True
    parti_nuovo = _parti(nuovo)
    # Un sottodominio di un dominio altrui (es. agenzia.generali.it) non sostituisce un sito proprio.
    if len(parti_nuovo) >= 3 and parti_nuovo[-2:] != _parti(vecchio)[-2:] and parti_nuovo[-2] not in ("co", "com"):
        return False
    return True


def verifica(gm: GoogleMaps, nome: str, comune: str, zona: str) -> dict | None:
    """La scheda Google dell'attività, se la si trova con buona sicurezza."""
    luogo_zona = comune or PROVINCE.get(zona.upper(), zona.split(":")[-1])
    for luogo in gm.cerca(f"{nome} {luogo_zona}", risultati=3):
        d = dati_utili(luogo)
        if stesso_nome(nome, d["nome"]) and nella_zona(d["indirizzo"], zona):
            return d
    return None


def riquadro_zona(gm: "GoogleMaps", zona: str) -> tuple[float, float, float, float] | None:
    """(lat_min, lat_max, lon_min, lon_max) di tutta la provincia o del comune, chiesto a Google Maps."""
    if zona.upper() in RIQUADRI_FISSI:
        return RIQUADRI_FISSI[zona.upper()]
    if zona.lower().startswith("comune:"):
        testo = zona.split(":", 1)[1].strip()
    else:
        testo = f"Provincia di {PROVINCE.get(zona.upper(), zona)}"
    r = requests.post(URL, timeout=30, json={"textQuery": testo + ", Italia", "languageCode": "it", "pageSize": 1},
                      headers={"X-Goog-Api-Key": gm.chiave, "X-Goog-FieldMask": "places.viewport"})
    gm.chiamate += 1
    luoghi = r.json().get("places", []) if r.ok else []
    vista = (luoghi[0].get("viewport") if luoghi else None) or {}
    basso, alto = vista.get("low"), vista.get("high")
    if not basso or not alto:
        return None
    return basso["latitude"], alto["latitude"], basso["longitude"], alto["longitude"]


def griglia(lat_min: float, lat_max: float, lon_min: float, lon_max: float, lato: int) -> list[dict]:
    """Divide il rettangolo della zona in lato×lato riquadri: Google restituisce al massimo 60 risultati
    per ricerca, quindi riquadri più piccoli trovano più attività."""
    passo_lat, passo_lon = (lat_max - lat_min) / lato, (lon_max - lon_min) / lato
    return [
        {"low": {"latitude": lat_min + i * passo_lat, "longitude": lon_min + j * passo_lon},
         "high": {"latitude": lat_min + (i + 1) * passo_lat, "longitude": lon_min + (j + 1) * passo_lon}}
        for i in range(lato) for j in range(lato)
    ]


def come_attivita(d: dict) -> dict | None:
    """Converte un risultato Google nel formato usato per OpenStreetMap; None se non è una PMI col sito."""
    if not d["sito"] or d["stato"] not in ("", "OPERATIONAL"):
        return None
    url = normalizza_url(d["sito"])
    dom = dominio(url)
    if not dom or any(x in dom for x in DOMINI_ESCLUSI) or di_catena(dom):
        return None
    solo_social = senza_sito_proprio(dom)
    comune = re.search(r"\d{5}\s+([^,]+?)\s+[A-Z]{2}\b", d["indirizzo"])
    return {
        "dominio": url.lower().rstrip("/") if solo_social else dom,
        "url": url,
        "nome": d["nome"],
        "categoria": d["categoria"] or "Attività",
        "telefono": d["telefono"],
        "email": "",
        "indirizzo": d["indirizzo"].split(",")[0],
        "comune": comune.group(1) if comune else "",
        "lat": d["lat"],
        "lon": d["lon"],
        "osm": d["mappa"],
        "solo_social": solo_social,
        "google": d,
    }
