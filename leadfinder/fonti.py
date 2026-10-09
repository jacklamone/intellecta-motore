"""Raccolta delle attività con sito web da OpenStreetMap (gratuito, nessuna chiave)."""

import re
import time
from urllib.parse import urlparse

import requests

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

USER_AGENT = "IntellectaLeadFinder/1.0 (+https://intellectasolutions.it)"

# Zone definite da un rettangolo fisso invece che dai confini amministrativi, più il prefisso dei CAP
# che le appartengono. Sassari = la provincia "storica": Sassari, Alghero, Stintino, Castelsardo e tutta
# la Gallura (Olbia, Costa Smeralda, La Maddalena, Santa Teresa). Con la riforma sarda del 2025 la Gallura
# è diventata un ente a parte e sulle mappe i confini possono essere divisi: il rettangolo la tiene dentro.
RIQUADRI_FISSI = {"SS": (40.35, 41.33, 8.10, 9.85)}  # lat_min, lat_max, lon_min, lon_max
CAP_ZONA = {"SS": "07"}
COMUNI_EXTRA = {"SS": ("San Teodoro", "Budoni")}  # Gallura turistica ma con CAP di Nuoro (08020)

# Chiavi OSM che identificano un'attività economica.
CHIAVI_ATTIVITA = ["shop", "craft", "office", "amenity", "tourism", "healthcare", "leisure", "club"]

# Valori da escludere: enti pubblici, luoghi non commerciali.
ESCLUSI = {
    "amenity": {
        "school", "kindergarten", "university", "college", "townhall", "police", "fire_station",
        "place_of_worship", "hospital", "library", "parking", "post_office", "courthouse",
        "prison", "grave_yard", "social_facility", "community_centre", "public_building",
        "bus_station", "ferry_terminal", "toilets", "shelter", "fountain", "bench", "waste_disposal",
        "recycling", "charging_station", "atm", "bicycle_parking", "music_school", "language_school",
        "arts_centre", "theatre", "cinema", "bank", "fuel", "monastery", "embassy",
    },
    "office": {"government", "diplomatic", "political_party", "religion", "ngo", "association", "union"},
    "leisure": {"park", "playground", "pitch", "garden", "nature_reserve", "marina", "stadium", "track"},
    "tourism": {"attraction", "viewpoint", "museum", "information", "artwork", "picnic_site", "camp_pitch"},
    "healthcare": {"hospital"},
}

# Domini che non sono un sito dell'attività.
DOMINI_SOCIAL = ("facebook.com", "instagram.com", "fb.com", "fb.me", "tiktok.com", "linktr.ee", "tr.ee", "wa.me")
# Pagine ospitate da piattaforme (menu, schede, vetrine): l'attività non ha un sito suo, come chi ha solo Facebook.
PAGINE_DI_PIATTAFORMA = (
    "eatbu.com", "mycia.it", "myadj.it", "beautycheck.it", "metadaesplorare.top", "italiacongusto.top",
    "plateform.app", "menu.it", "quandoo.it", "treatwell.it", "miodottore.it", "prontopro.it", "canva.com",
    "business.site", "paginegialle.it", "virgilio.it",
)
# Servizi per farsi il sito da soli: tanti siti diversi sullo stesso dominio, non sono una catena.
HOSTING = ("wixsite.com", "weebly.com", "blogspot.com", "altervista.org", "wordpress.com", "jimdofree.com",
           "jimdo.com", "webnode.it", "webnode.com", "myshopify.com", "site123.me", "netlify.app", "github.io")
# Catene, franchising, banche, assicurazioni ed enti: non sono PMI a cui proporre un sito (dominio principale).
CATENE = (
    "tecnocasa.it", "tempocasa.it", "gabetti.it", "toscano.it", "frimm.com", "remax.it", "generali.it", "sara.it",
    "allianz.it", "unipolsai.it", "unipol.it", "axa.it", "reale.it", "cattolica.it", "zurich.it", "groupama.it",
    "vittoriaassicurazioni.com", "orodeicompro.it", "bludental.it", "dentalpro.it", "vitaldent.it", "unimi.it",
    "poste.it", "intesasanpaolo.com", "unicredit.it", "bper.it", "bancobpm.it", "credit-agricole.it", "mps.it",
    "fielmann.it", "salmoiraghievigano.it", "grandvision.it", "chicco.it", "adecco.it", "randstad.it", "gigroup.it",
    "manpower.it", "tigota.it", "acquaesapone.it", "kikocosmetics.com", "douglas.it", "mediaworld.it", "euronics.it",
    "unieuro.it", "esselunga.it", "conad.it", "coop.it", "e-coop.it", "carrefour.it", "lidl.it", "eurospin.it",
    "decathlon.it", "leroymerlin.it", "bricocenter.it", "mcdonalds.it", "burgerking.it", "autogrill.it",
    "petit-bateau.it", "calzedonia.com", "intimissimi.com", "tezenis.com", "ovs.it", "pittarello.com",
)

DOMINI_ESCLUSI = (
    "gov.it", "comune.", "regione.", "provincia.", "wikipedia.org", "google.", "tripadvisor.",
    "booking.com", "thefork.", "paginegialle.it", "youtube.com", "linkedin.com", "twitter.com", "x.com",
)

ETICHETTE = {
    "restaurant": "Ristorante", "cafe": "Bar/Caffè", "bar": "Bar", "pub": "Pub", "pizzeria": "Pizzeria",
    "fast_food": "Fast food / Take away", "ice_cream": "Gelateria", "pharmacy": "Farmacia",
    "dentist": "Dentista", "doctors": "Studio medico", "clinic": "Clinica", "veterinary": "Veterinario",
    "hairdresser": "Parrucchiere", "beauty": "Centro estetico", "bakery": "Panificio", "butcher": "Macelleria",
    "clothes": "Abbigliamento", "shoes": "Calzature", "furniture": "Arredamento", "car_repair": "Autofficina",
    "car": "Concessionaria auto", "optician": "Ottico", "florist": "Fiorista", "jewelry": "Gioielleria",
    "hotel": "Hotel", "guest_house": "B&B / Affittacamere", "apartment": "Case vacanza",
    "agriturismo": "Agriturismo", "wine": "Enoteca", "winery": "Cantina", "electrician": "Elettricista",
    "plumber": "Idraulico", "carpenter": "Falegname", "lawyer": "Avvocato", "accountant": "Commercialista",
    "estate_agent": "Agenzia immobiliare", "insurance": "Assicurazioni", "architect": "Architetto",
    "travel_agency": "Agenzia viaggi", "fitness_centre": "Palestra", "sports_centre": "Centro sportivo",
    "physiotherapist": "Fisioterapista", "supermarket": "Supermercato", "convenience": "Alimentari",
    "hardware": "Ferramenta", "bicycle": "Biciclette", "pastry": "Pasticceria", "tattoo": "Tatuaggi",
    "photographer": "Fotografo", "company": "Azienda", "it": "Informatica", "books": "Libreria",
    "pet": "Animali", "gift": "Articoli regalo", "mobile_phone": "Telefonia", "electronics": "Elettronica",
    "funeral_directors": "Onoranze funebri", "fireplace": "Caminetti e stufe", "childcare": "Asilo / Baby parking",
    "kitchen": "Cucine", "interior_decoration": "Arredo interni", "tiles": "Piastrelle", "doityourself": "Fai da te",
    "garden_centre": "Vivaio / Giardinaggio", "car_parts": "Ricambi auto", "tyres": "Gommista", "motorcycle": "Moto",
    "cosmetics": "Profumeria", "massage": "Massaggi", "nutrition_supplements": "Integratori", "medical_supply": "Sanitaria",
    "hearing_aids": "Apparecchi acustici", "deli": "Gastronomia", "confectionery": "Dolciumi", "seafood": "Pescheria",
    "greengrocer": "Ortofrutta", "farm": "Azienda agricola", "beverages": "Bevande", "coffee": "Torrefazione",
    "tobacco": "Tabaccheria", "newsagent": "Edicola", "stationery": "Cartoleria", "copyshop": "Copisteria",
    "toys": "Giocattoli", "sports": "Articoli sportivi", "outdoor": "Outdoor", "bag": "Borse e pelletteria",
    "boutique": "Boutique", "fabric": "Tessuti", "sewing": "Merceria", "tailor": "Sartoria", "laundry": "Lavanderia",
    "dry_cleaning": "Tintoria", "funeral_home": "Onoranze funebri", "car_wash": "Autolavaggio",
    "driving_school": "Autoscuola", "nightclub": "Discoteca", "biergarten": "Birreria", "food_court": "Ristorazione",
    "wine_bar": "Wine bar", "brewery": "Birrificio", "caterer": "Catering", "builder": "Impresa edile",
    "painter": "Imbianchino", "roofer": "Lattoniere / Tetti", "hvac": "Climatizzazione", "gardener": "Giardiniere",
    "locksmith": "Fabbro", "metal_construction": "Carpenteria metallica", "window_construction": "Serramenti",
    "stonemason": "Marmista", "upholsterer": "Tappezziere", "shoemaker": "Calzolaio", "glaziery": "Vetraio",
    "consulting": "Consulenza", "employment_agency": "Agenzia per il lavoro", "notary": "Notaio",
    "tax_advisor": "Consulente fiscale", "financial": "Servizi finanziari", "advertising_agency": "Agenzia pubblicitaria",
    "surveyor": "Geometra", "engineer": "Ingegnere", "graphic_design": "Grafica", "yoga": "Yoga",
    "dance": "Scuola di danza", "swimming_pool": "Piscina", "golf_course": "Golf", "horse_riding": "Maneggio",
    "sauna": "Sauna / Spa", "motel": "Motel", "alpine_hut": "Rifugio", "wine_cellar": "Cantina",
    "nursing_home": "Casa di riposo", "animal_boarding": "Pensione animali", "pet_grooming": "Toelettatura",
    "photo": "Foto", "art": "Galleria d'arte", "antiques": "Antiquariato", "second_hand": "Usato",
    "houseware": "Casalinghi", "lighting": "Illuminazione", "bed": "Materassi", "carpet": "Tappeti",
    "paint": "Colorificio", "trade": "Ingrosso", "wholesale": "Ingrosso", "agrarian": "Consorzio agrario",
    "camp_site": "Campeggio", "chalet": "Chalet", "hostel": "Ostello", "psychotherapist": "Psicologo",
}


def dominio(url: str) -> str:
    if not re.match(r"^https?://", url, re.I):
        url = "http://" + url
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def normalizza_url(url: str) -> str:
    url = url.strip().split(";")[0].strip()
    if not re.match(r"^https?://", url, re.I):
        url = "http://" + url
    return url


def _regex_overpass(testo: str) -> str:
    """Escape per una regex dentro una stringa Overpass: il backslash va raddoppiato."""
    return re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\\\1", testo).replace('"', '\\"')


def _query(zona: str) -> str:
    """Una sigla (PD) cerca la provincia; 'comune:Nome' cerca un comune; altrimenti il nome della provincia."""
    zona = zona.strip()
    if zona.upper() in RIQUADRI_FISSI:
        lat_min, lat_max, lon_min, lon_max = RIQUADRI_FISSI[zona.upper()]
        r = f"({lat_min},{lon_min},{lat_max},{lon_max})"
        return f"""[out:json][timeout:600];
(
  nwr["website"]["name"]{r};
  nwr["contact:website"]["name"]{r};
  nwr["url"]["name"]{r};
);
out tags center;"""
    if zona.lower().startswith("comune:"):
        nome = _regex_overpass(zona.split(":", 1)[1].strip())
        area = f'area["boundary"="administrative"]["admin_level"="8"]["name"~"^{nome}$",i]->.a;'
    elif re.fullmatch(r"[A-Za-z]{2}", zona):
        sigla = zona.upper()
        area = (
            f'( area["ISO3166-2"="IT-{sigla}"];'
            f' area["boundary"="administrative"]["admin_level"="6"]["ref"="{sigla}"];'
            f' area["boundary"="administrative"]["admin_level"="6"]["short_name"="{sigla}"]; )->.a;'
        )
    else:
        nome = _regex_overpass(zona)
        prefissi = "(Provincia di |Provincia del |Provincia dell'|Città metropolitana di |Libero consorzio comunale di )?"
        area = f'area["boundary"="administrative"]["admin_level"="6"]["name"~"^{prefissi}{nome}$",i]->.a;'
    return f"""[out:json][timeout:600];
{area}
(
  nwr(area.a)["website"]["name"];
  nwr(area.a)["contact:website"]["name"];
  nwr(area.a)["url"]["name"];
);
out tags center;"""


def scarica_osm(zona: str) -> list[dict]:
    query = _query(zona)
    ultimo_errore = None
    for tentativo in range(3):
        for endpoint in OVERPASS_ENDPOINTS:
            try:
                r = requests.post(endpoint, data={"data": query}, timeout=700,
                                  headers={"User-Agent": USER_AGENT})
                if r.status_code == 200:
                    dati = r.json()
                    nota = dati.get("remark", "")
                    if "error" in nota.lower() or "timed out" in nota.lower():
                        # Overpass ha risposto "200" ma con un risultato parziale: non è affidabile
                        ultimo_errore = f"{endpoint}: risultato incompleto ({nota[:120]})"
                        continue
                    elementi = dati.get("elements", [])
                    cap = CAP_ZONA.get(zona.strip().upper())
                    if cap:  # il rettangolo sfiora le province vicine: via chi ha un CAP di fuori
                        extra = COMUNI_EXTRA.get(zona.strip().upper(), ())
                        elementi = [e for e in elementi
                                    if (e.get("tags") or {}).get("addr:postcode", cap).strip().startswith(cap)
                                    or (e.get("tags") or {}).get("addr:city") in extra]
                    return elementi
                ultimo_errore = f"{endpoint}: HTTP {r.status_code}"
            except requests.RequestException as e:
                ultimo_errore = f"{endpoint}: {e}"
        time.sleep(30 * (tentativo + 1))
    raise RuntimeError(f"OpenStreetMap non raggiungibile ({ultimo_errore})")


def _categoria(tags: dict) -> tuple[str, str] | None:
    for chiave in CHIAVI_ATTIVITA:
        valore = tags.get(chiave)
        if not valore or valore in ("yes", "no"):
            continue
        if valore in ESCLUSI.get(chiave, set()):
            return None
        return chiave, valore
    return None


def estrai_attivita(elementi: list[dict]) -> list[dict]:
    """Filtra le PMI (niente catene, enti pubblici, siti di terzi) e toglie i doppioni per dominio."""
    visti: dict[str, dict] = {}
    for el in elementi:
        tags = el.get("tags", {})
        cat = _categoria(tags)
        if not cat:
            continue
        # Le catene hanno il marchio registrato in OSM: non sono PMI.
        if tags.get("brand") or tags.get("brand:wikidata") or tags.get("operator:wikidata"):
            continue
        url = tags.get("website") or tags.get("contact:website") or tags.get("url")
        url = normalizza_url(url)
        dom = dominio(url)
        if not dom or "." not in dom or any(x in dom for x in DOMINI_ESCLUSI) or di_catena(dom):
            continue
        solo_social = senza_sito_proprio(dom)
        centro = el.get("center") or {"lat": el.get("lat"), "lon": el.get("lon")}
        indirizzo = " ".join(x for x in [tags.get("addr:street"), tags.get("addr:housenumber")] if x)
        attivita = {
            # Per le pagine social la chiave è l'URL intero: più attività non condividono lo stesso "sito".
            "dominio": url.lower().rstrip("/") if solo_social else dom,
            "url": url,
            "nome": tags.get("name", ""),
            "categoria": ETICHETTE.get(cat[1], cat[1].replace("_", " ").capitalize()),
            "telefono": tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile") or "",
            "email": tags.get("email") or tags.get("contact:email") or "",
            "indirizzo": indirizzo,
            "comune": tags.get("addr:city", ""),
            "lat": centro.get("lat"),
            "lon": centro.get("lon"),
            "osm": f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
            "solo_social": solo_social,
        }
        # A parità di dominio tieni la scheda più completa (con telefono).
        precedente = visti.get(attivita["dominio"])
        if not precedente or (not precedente["telefono"] and attivita["telefono"]):
            visti[attivita["dominio"]] = attivita
    return list(visti.values())


def _del_dominio(dom: str, elenco: tuple[str, ...]) -> bool:
    return any(dom == d or dom.endswith("." + d) for d in elenco)


def di_catena(dom: str) -> bool:
    return _del_dominio(dom, CATENE)


def senza_sito_proprio(dom: str) -> bool:
    """Pagina social o di una piattaforma: chi la usa non ha un sito suo (contatto da proporre)."""
    return _del_dominio(dom, DOMINI_SOCIAL + PAGINE_DI_PIATTAFORMA)
