"""Controlli tecnici gratuiti sull'HTML della home page: capiscono se un sito è vecchio senza usare l'AI."""

import datetime as dt
import re
import time

from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Molti siti bloccano i client "sconosciuti": ci presentiamo come un normale Chrome.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"
)

ANNO = dt.date.today().year

# Ogni problema ha un peso: la somma (max 100) è il "punteggio vecchiaia". Più alto = sito peggiore.
PESI = {
    "no_https": 20,
    "no_viewport": 30,
    "copyright_vecchio": 15,
    "copyright_molto_vecchio": 25,
    "tag_obsoleti": 15,
    "layout_a_tabelle": 10,
    "flash": 20,
    "jquery_vecchio": 10,
    "cms_vecchio": 15,
    "no_privacy": 5,
    "lento": 5,
    "non_adatto_mobile": 15,
}

DESCRIZIONI = {
    "no_https": "Niente HTTPS: il browser mostra 'Non sicuro'",
    "no_viewport": "Non è pensato per il cellulare",
    "copyright_vecchio": "Copyright fermo al {anno}",
    "copyright_molto_vecchio": "Copyright fermo al {anno}",
    "tag_obsoleti": "Codice HTML anni 2000 (tag obsoleti)",
    "layout_a_tabelle": "Impaginazione a tabelle (tecnica superata)",
    "flash": "Usa Flash, che non funziona più",
    "jquery_vecchio": "Librerie JavaScript vecchie ({versione})",
    "cms_vecchio": "CMS non aggiornato ({versione})",
    "no_privacy": "Manca privacy/cookie policy (rischio GDPR)",
    "lento": "Lento a caricare ({secondi:.1f}s)",
    "non_adatto_mobile": "Su cellulare la pagina esce dallo schermo",
}

RE_COPYRIGHT = re.compile(
    r"(?:©|&copy;|\(c\)|copyright)\s*(?:[^0-9<]{0,40}?)((?:19|20)\d{2})(?:\s*[-–/]\s*((?:19|20)\d{2}))?", re.I
)
RE_JQUERY = re.compile(r"jquery[.-]?(\d)\.(\d+)(?:\.\d+)?(?:\.min)?\.js|jquery(?:\.min)?\.js\?ver=(\d)\.(\d+)", re.I)
TAG_OBSOLETI = ["font", "center", "marquee", "blink", "frameset", "frame", "applet", "basefont", "big", "tt"]


def scarica(url: str) -> dict:
    """Scarica la pagina: https, URL originale, poi la home del dominio (l'indirizzo in OSM può essere vecchio)."""
    host = urlparse(url).netloc
    tentativi = []
    for u in ["https://" + url.split("://", 1)[1], url, f"https://{host}/", f"http://{host}/"]:
        if u not in tentativi:
            tentativi.append(u)
    ultimo_errore = ""
    for u in tentativi:
        inizio = time.monotonic()
        try:
            r = requests.get(u, timeout=25, allow_redirects=True,
                             headers={"User-Agent": USER_AGENT, "Accept-Language": "it-IT,it;q=0.9"})
            secondi = time.monotonic() - inizio
            if r.status_code >= 400:
                ultimo_errore = f"HTTP {r.status_code}"
                continue
            r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else r.apparent_encoding
            return {"ok": True, "url_finale": r.url, "html": r.text, "secondi": secondi}
        except requests.exceptions.SSLError:
            ultimo_errore = "certificato SSL non valido"
        except requests.RequestException as e:
            ultimo_errore = type(e).__name__
    return {"ok": False, "errore": ultimo_errore}


def analizza_html(html: str, url_finale: str, secondi: float) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    problemi: dict[str, dict] = {}

    if not url_finale.lower().startswith("https://"):
        problemi["no_https"] = {}

    if not soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)}):
        problemi["no_viewport"] = {}

    anni = []
    for m in RE_COPYRIGHT.finditer(html):
        anni += [int(a) for a in m.groups() if a]
    anni = [a for a in anni if 1995 <= a <= ANNO]
    anno_copyright = max(anni) if anni else None
    if anno_copyright and ANNO - anno_copyright >= 6:
        problemi["copyright_molto_vecchio"] = {"anno": anno_copyright}
    elif anno_copyright and ANNO - anno_copyright >= 3:
        problemi["copyright_vecchio"] = {"anno": anno_copyright}

    obsoleti = [t for t in TAG_OBSOLETI if soup.find(t)]
    if obsoleti:
        problemi["tag_obsoleti"] = {"tag": obsoleti}

    tabelle = soup.find_all("table")
    tabelle_annidate = [t for t in tabelle if t.find_parent("table")]
    tabelle_layout = [t for t in tabelle if t.get("width") or t.get("bgcolor") or t.get("cellpadding") is not None]
    if len(tabelle_annidate) >= 2 or len(tabelle_layout) >= 2:
        problemi["layout_a_tabelle"] = {}

    if re.search(r"\.swf\b|application/x-shockwave-flash", html, re.I):
        problemi["flash"] = {}

    for m in RE_JQUERY.finditer(html):
        major, minor = [int(x) for x in m.groups() if x][:2]
        if major < 3:
            problemi["jquery_vecchio"] = {"versione": f"jQuery {major}.{minor}"}
            break

    generatore = soup.find("meta", attrs={"name": re.compile("^generator$", re.I)})
    generatore = (generatore.get("content") or "").strip() if generatore else ""
    m = re.search(r"(WordPress|Joomla!?)\s*(\d+)(?:\.(\d+))?", generatore, re.I)
    if m:
        cms, major = m.group(1), int(m.group(2))
        if (cms.lower() == "wordpress" and major < 5) or (cms.lower().startswith("joomla") and major < 4):
            problemi["cms_vecchio"] = {"versione": generatore}

    testo = html.lower()
    if "privacy" not in testo and "cookie" not in testo:
        problemi["no_privacy"] = {}

    if secondi > 4:
        problemi["lento"] = {"secondi": secondi}

    email = sorted({m.lower() for m in re.findall(r"mailto:([\w.+-]+@[\w-]+\.[\w.-]+)", html, re.I)})
    titolo = soup.title.get_text(strip=True)[:120] if soup.title else ""

    return {
        "problemi": problemi,
        "anno_copyright": anno_copyright,
        "generatore": generatore,
        "email_sito": email[:3],
        "titolo": titolo,
        "social": link_social(soup),
    }


RE_SOCIAL = {
    "linkedin": re.compile(r"linkedin\.com/(company|in|school|showcase)/", re.I),
    "facebook": re.compile(r"facebook\.com/(?!sharer|share|dialog|plugins|tr\b)", re.I),
    "instagram": re.compile(r"instagram\.com/(?!p/|explore)", re.I),
}


def link_social(soup: BeautifulSoup) -> dict:
    """Link alle pagine social dell'attività trovati nel sito (spesso nel footer)."""
    trovati = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        for nome, regex in RE_SOCIAL.items():
            if nome not in trovati and regex.search(href):
                trovati[nome] = href.split("?")[0]
    return trovati


def estrai_contenuto(html: str, url: str) -> dict:
    """Testi, foto e logo del sito attuale: il materiale per disegnare l'anteprima del sito nuovo."""
    soup = BeautifulSoup(html, "html.parser")
    social = link_social(soup)
    descrizione = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    descrizione = (descrizione.get("content") or "").strip() if descrizione else ""

    immagini, logo = [], ""
    # Il logo di solito è la prima immagine nell'intestazione o nel link alla home.
    in_testa = soup.select_one("header img, #header img, .header img, a[href='/'] img, a[href='./'] img, "
                               "a[href='index.html'] img, a[href='index.php'] img")
    if in_testa and (in_testa.get("src") or "").strip() and not in_testa["src"].startswith("data:"):
        logo = urljoin(url, in_testa["src"].strip())
    for img in soup.find_all("img"):
        src = (img.get("src") or img.get("data-src") or img.get("data-lazy-src") or "").strip()
        if not src or src.startswith("data:") or re.search(r"\.(svg|gif)(\?|$)", src, re.I):
            continue
        assoluto = urljoin(url, src)
        if assoluto == logo:
            continue
        testo_img = f"{src} {img.get('alt', '')} {' '.join(img.get('class', []))}".lower()
        if not logo and "logo" in testo_img:
            logo = assoluto
            continue
        larghezza = img.get("width") or ""
        if larghezza.isdigit() and int(larghezza) < 150:
            continue  # icone e bottoni
        if re.search(r"icon|sprite|pixel|spacer|banner-cookie|flag", testo_img):
            continue
        if assoluto not in immagini:
            immagini.append(assoluto)

    for t in soup(["script", "style", "noscript", "svg", "iframe", "form"]):
        t.decompose()
    titoli = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
    testo = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

    return {
        "titolo": soup.title.get_text(strip=True) if soup.title else "",
        "descrizione": descrizione,
        "titoli": [t for t in titoli if t][:15],
        "testo": testo[:4000],
        "immagini": immagini[:8],
        "logo": logo,
        "social": social,
    }


def punteggio(problemi: dict) -> int:
    return min(100, sum(PESI.get(p, 0) for p in problemi))


def descrivi(problemi: dict) -> list[str]:
    righe = []
    for chiave, dati in problemi.items():
        try:
            righe.append(DESCRIZIONI[chiave].format(**dati))
        except (KeyError, IndexError):
            righe.append(DESCRIZIONI.get(chiave, chiave))
    return righe


def controlla(url: str) -> dict:
    pagina = scarica(url)
    if not pagina["ok"]:
        return {"raggiungibile": False, "errore": pagina["errore"], "problemi": {}, "punteggio": 0}
    analisi = analizza_html(pagina["html"], pagina["url_finale"], pagina["secondi"])
    analisi.update(raggiungibile=True, url_finale=pagina["url_finale"], punteggio=punteggio(analisi["problemi"]))
    return analisi
