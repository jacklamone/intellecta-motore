"""Proposta per i contatti migliori: anteprima del sito rifatto (desktop + mobile) e bozze dei messaggi."""

import json
import os
from pathlib import Path
from urllib.parse import quote_plus

from .ai import chiedi

from . import controlli

MODELLO = os.environ.get("OPENAI_MODEL_PROPOSTE") or "gpt-5"

ISTRUZIONI = """Sei il lead designer di Intellecta Solutions, agenzia italiana che crea siti web moderni,
chatbot WhatsApp e campagne social per PMI. Devi preparare una proposta per un'attività che ha un sito
datato (o solo una pagina social).

LA REGOLA PIÙ IMPORTANTE: il titolare deve guardare l'anteprima ed emozionarsi, pensare "questo sono io, ma
come ho sempre sognato di essere". Prima di disegnare chiediti: cosa rende speciale QUESTA attività? (il paese,
la tradizione, la famiglia, le mani dell'artigiano, il prodotto, i clienti affezionati, la cura…). Cercalo nei
contenuti del sito attuale e mettilo al centro: nel titolo, nelle foto, nei testi.
   - Titolo dell'hero che parla al cuore dei LORO clienti, concreto e caldo (es. per una macelleria di paese:
     "La carne buona di Bertonico, scelta come una volta"), mai frasi da agenzia vuote come "Qualità e
     professionalità al vostro servizio" o "Soluzioni su misura".
   - Testi brevi, umani, in italiano naturale, con il nome del paese e i prodotti veri; il "chi siamo" racconta
     una storia (solo con fatti presenti nei dati: niente anni o premi inventati).
   - L'atmosfera visiva deve evocare il prodotto: per un forno il calore del pane, per un vivaio il verde e la
     luce, per un'officina la precisione e la fiducia, per uno studio la serenità.

1) "html": la NUOVA HOME PAGE dell'attività, come file HTML unico e completo.
   - CSS dentro <style>, nessun JavaScript esterno. Puoi usare Google Fonts con <link>.
   - Design contemporaneo, curato, adatto al settore: header con logo/nome e menu, hero forte con titolo,
     sottotitolo e call to action (Chiama, WhatsApp, Prenota o Richiedi preventivo, secondo il settore),
     sezione servizi/prodotti, chi siamo, dove siamo/contatti, footer.
   - Responsive: deve essere perfetto a 390 px di larghezza (menu compatto, testi leggibili, niente
     scorrimento orizzontale) e a 1366 px.
   - FOTO: usa come immagini grandi (hero, sfondi, card) SOLO "foto_grandi" (URL assoluti, almeno 800 px),
     con object-fit: cover. "foto_piccole" vanno solo in riquadri piccoli (max 300 px), mai ingrandite né
     come sfondo: sgranerebbero. Se non ci sono foto grandi, usa sfumature, forme e colori eleganti:
     niente immagini inventate o segnaposto grigi.
   - LOGO: non usare mai il file del logo attuale (spesso è piccolo o sgranato). RIDISEGNALO tu, più bello e
     pulito, come SVG inline nell'header (e in piccolo nel footer): un marchio con il nome dell'attività in un
     bel carattere e, se ha senso, un simbolo semplice. Se ti è mostrata l'immagine del logo attuale,
     riprendine colori, iniziali o simbolo: deve restare riconoscibile, solo più moderno ed elegante.
   - Usa SOLO informazioni presenti nei dati forniti. NON inventare prezzi, anni di attività, premi,
     numeri, recensioni o testimonianze. Dove mancano dettagli, scrivi testi generici ma credibili.
   - COLORI: sfondo CHIARO (bianco, crema, sabbia, grigio chiarissimo) con testo scuro, salvo che il settore
     non chieda proprio un'atmosfera notturna (cocktail bar, discoteca, pub serale). NON fare siti neri o
     blu notte per ristoranti, negozi, artigiani, studi o servizi: il cliente si deve riconoscere.
     Usa la "palette_consigliata" fornita come base e, se il sito attuale ha colori o logo riconoscibili,
     riprendili: il titolare deve ritrovare la sua identità, solo più moderna.
   - In basso a destra un piccolo badge fisso: "Anteprima di Intellecta Solutions".
2) "nota_collegamento": nota per la richiesta di collegamento LinkedIn, massimo 280 caratteri.
3) "messaggio_linkedin": messaggio LinkedIn di 80-120 parole.
4) "email_oggetto" ed "email_testo": email di 100-150 parole.
5) "frase_lettera": UNA frase (max 35 parole) per la lettera di carta, che riconosce con sincerità cosa c'è di
   bello nella loro attività (dai contenuti del sito o dalla categoria) e collega il nuovo sito a quel valore.
   Es.: "Dal vostro sito traspare la passione per la carne di qualità del territorio: meritate un sito che la
   racconti con la stessa cura, e che porti in negozio anche i clienti più giovani." Dai del voi.

Per i messaggi: tono cordiale, rispettoso e concreto, mai offensivo sul sito attuale. Dai del Lei.
Cita 2 o 3 problemi del sito attuale in parole semplici, di' che abbiamo preparato un'anteprima di come
potrebbe essere il nuovo sito (da computer e da cellulare, in allegato), proponi una chiamata di 15 minuti
senza impegno. Firma: "Intellecta Solutions — info@intellectasolutions.it".

Per tutti i testi: prima il loro valore, poi i problemi. Chi legge deve sentirsi capito, non giudicato.

Rispondi SOLO con un oggetto JSON con le chiavi: html, nota_collegamento, messaggio_linkedin,
email_oggetto, email_testo, frase_lettera."""


# Palette chiare e diverse per settore, così le anteprime non si somigliano tutte (sfondo, testo, accento).
PALETTE = (
    (("ristorant", "trattori", "osteri", "pizzeri", "agriturism", "cascina", "enotec", "vin", "cantin"),
     "sfondo crema #faf6ef, testo #2b2118, accento terracotta #b5532c, secondario verde oliva #6b7a3a"),
    (("parrucch", "estetic", "barber", "beauty", "spa", "massagg", "unghie"),
     "sfondo #fbf7f5, testo #2d2426, accento rosa antico #b56b74, secondario oro chiaro #d9b77e"),
    (("bar", "caff", "pasticc", "gelat", "panific", "fornaio", "forno"),
     "sfondo bianco caldo #fffaf3, testo #3a2a1f, accento caramello #c27a3a, secondario rosa cipria #e9c9c0"),
    (("dentist", "odontoiatr", "medic", "fisioterap", "farmac", "veterinar", "ottic", "clinica"),
     "sfondo bianco #ffffff, testo #1d2a33, accento azzurro clinico #2a7fa8, secondario verde acqua #5fb3a5"),
    (("avvocat", "legale", "commercialist", "notai", "consulen", "assicura", "immobiliar", "studio"),
     "sfondo #f7f7f4, testo #1f2933, accento blu petrolio #1f5f74, secondario sabbia #c8b38a"),
    (("edil", "impres", "costruz", "serrament", "infissi", "impiant", "elettric", "idraul", "carpent", "metal", "falegnam"),
     "sfondo #f5f6f3, testo #222a2f, accento arancio cantiere #e07b24, secondario grigio ardesia #4a5560"),
    (("auto", "carrozzer", "officin", "gomm", "ricambi", "moto", "concessionar"),
     "sfondo #f4f5f7, testo #1b1f24, accento rosso #c8302c, secondario acciaio #6c7a89"),
    (("fior", "vivai", "giardin", "agricol", "macelleri", "salumer", "alimentar", "gastronom"),
     "sfondo #f7f8f2, testo #1f2a1c, accento verde foglia #4f7f3a, secondario giallo grano #e3b94d"),
    (("hotel", "b&b", "bed and breakfast", "affittacamer", "residence", "ostello"),
     "sfondo #fbf9f6, testo #23262b, accento blu lago #3f6f8f, secondario sabbia #d8c3a0"),
    (("abbigliament", "calzatur", "gioiell", "boutique", "moda", "borse", "arredament", "arredo"),
     "sfondo #faf9f7, testo #1e1e1e, accento ottone #a8874a, secondario grigio tortora #b9b0a6"),
)
PALETTE_GENERICA = "sfondo #fafaf8, testo #1f2430, accento verde salvia #5e8b6f, secondario corallo tenue #e28f73"


def palette(categoria: str, nome: str) -> str:
    testo = f"{categoria} {nome}".lower()
    for parole, colori in PALETTE:
        if any(p in testo for p in parole):
            return colori
    return PALETTE_GENERICA


def link_ricerca_linkedin(nome: str, comune: str = "") -> str:
    return f"https://www.linkedin.com/search/results/companies/?keywords={quote_plus(f'{nome} {comune}'.strip())}"


def _dati_attivita(riga, contenuto: dict) -> str:
    ai = json.loads(riga["valutazione_ai"] or "{}")
    problemi = ai.get("difetti") or json.loads(riga["problemi"] or "[]")
    dati = {
        "nome": riga["nome"],
        "categoria": riga["categoria"],
        "indirizzo": " ".join(x for x in [riga["indirizzo"], riga["comune"]] if x),
        "telefono": riga["telefono"],
        "email": riga["email"],
        "sito_attuale": None if riga["solo_social"] else riga["url"],
        "pagina_social": riga["url"] if riga["solo_social"] else None,
        "problemi_sito_attuale": problemi,
        "palette_consigliata": palette(riga["categoria"] or "", riga["nome"] or ""),
        "contenuti_sito_attuale": contenuto,
    }
    return json.dumps(dati, ensure_ascii=False)


def genera(riga, contenuto: dict) -> dict:
    logo = contenuto.pop("_logo_dati", None)
    messaggio = [{"type": "text", "text": _dati_attivita(riga, contenuto)}]
    if logo:
        messaggio += [{"type": "text", "text": "Questo è il logo attuale, da ridisegnare:"},
                      {"type": "image_url", "image_url": {"url": logo, "detail": "low"}}]
    parametri = dict(
        model=MODELLO,
        messages=[
            {"role": "system", "content": ISTRUZIONI},
            {"role": "user", "content": messaggio},
        ],
        response_format={"type": "json_object"},
    )
    if MODELLO.startswith("gpt-5"):
        parametri["reasoning_effort"] = "low"
    risposta = chiedi(parametri)
    dati = json.loads(risposta.choices[0].message.content)
    if "<body" not in dati.get("html", "").lower():
        raise ValueError("l'AI non ha restituito una pagina HTML valida")
    return dati


def contenuto_sito(riga) -> dict:
    """Scarica il sito attuale e ne estrae testi, foto, logo e link social."""
    if riga["solo_social"]:
        return {}
    pagina = controlli.scarica(riga["url"])
    if not pagina["ok"]:
        return {}
    contenuto = controlli.estrai_contenuto(pagina["html"], pagina["url_finale"])
    return misura_immagini(contenuto)


def _scarica_immagine(url: str) -> tuple[bytes, tuple[int, int], str] | None:
    import io
    import requests
    from PIL import Image
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": controlli.USER_AGENT}, stream=True)
        if r.status_code != 200:
            return None
        dati = r.raw.read(3_000_000, decode_content=True)
        with Image.open(io.BytesIO(dati)) as img:
            return dati, img.size, (img.format or "JPEG").lower()
    except Exception:  # noqa: BLE001 — immagine rotta o formato strano: la saltiamo
        return None


def misura_immagini(contenuto: dict) -> dict:
    """Divide le foto in grandi (usabili come sfondo) e piccole; prepara il logo da far vedere all'AI."""
    import base64
    grandi, piccole = [], []
    for url in contenuto.pop("immagini", []):
        scaricata = _scarica_immagine(url)
        if not scaricata:
            continue
        larghezza, altezza = scaricata[1]
        if larghezza >= 800 and altezza >= 350:
            grandi.append(url)
        elif larghezza >= 150:
            piccole.append(url)
    contenuto["foto_grandi"], contenuto["foto_piccole"] = grandi, piccole
    if contenuto.get("logo"):
        scaricata = _scarica_immagine(contenuto["logo"])
        if scaricata and len(scaricata[0]) < 1_000_000:
            tipo = {"png": "image/png", "webp": "image/webp", "gif": "image/gif"}.get(scaricata[2], "image/jpeg")
            contenuto["_logo_dati"] = f"data:{tipo};base64,{base64.b64encode(scaricata[0]).decode()}"
    contenuto.pop("logo", None)
    return contenuto


def salva_proposta(riga, dati: dict, cartella: Path, fotografo) -> dict:
    """Salva l'HTML dell'anteprima e ne fa gli screenshot. Restituisce cosa salvare nell'archivio."""
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / "index.html").write_text(dati["html"], encoding="utf-8")
    foto = fotografo.fotografa_html(dati["html"], cartella)
    return {
        "desktop": foto["desktop"],
        "mobile": foto["mobile"],
        "html": str(cartella / "index.html"),
        "nota_collegamento": (dati.get("nota_collegamento") or "")[:300],
        "messaggio_linkedin": dati.get("messaggio_linkedin", ""),
        "email_oggetto": dati.get("email_oggetto", ""),
        "email_testo": dati.get("email_testo", ""),
        "frase_lettera": (dati.get("frase_lettera") or "").strip(),
    }
