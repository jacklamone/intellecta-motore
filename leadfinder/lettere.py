"""Lettere di carta personalizzate + pagina personale per ogni contatto (raggiungibile col QR code).

La lettera è il primo contatto, lecito per posta verso le aziende; la pagina mostra l'anteprima completa e
i pulsanti per scriverci: così è il titolare a contattarci (e solo allora WhatsApp/email diventano leciti).
"""

import datetime as dt
import html
import io
import json
import os
import secrets
import shutil
from pathlib import Path
from urllib.parse import quote

import qrcode
import qrcode.image.svg
import requests

from . import report
from .fonti import dominio
from .pdf import _css, _dati

MESI = ("gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre").split()


def _e(testo) -> str:
    return html.escape(str(testo or ""))


def data_lunga(giorno: dt.date) -> str:
    return f"{giorno.day} {MESI[giorno.month - 1]} {giorno.year}"


def token(r) -> str:
    """Indirizzo della pagina personale: leggibile ma non indovinabile (es. calzi-carni-srl-4f9a2c)."""
    return f"{report.slug(r['nome'] or r['dominio'])[:40].strip('-')}-{secrets.token_hex(3)}"


def indirizzo_postale(r) -> tuple[str, bool]:
    """(indirizzo completo, è sicuro?) — da Google Maps se c'è la chiave, altrimenti quello che abbiamo."""
    if r["indirizzo_postale"]:
        return r["indirizzo_postale"], True
    chiave = os.environ.get("GOOGLE_MAPS_API_KEY")
    if chiave:
        try:
            if r["google_id"]:
                risposta = requests.get(f"https://places.googleapis.com/v1/places/{r['google_id']}", timeout=20,
                                        headers={"X-Goog-Api-Key": chiave, "X-Goog-FieldMask": "formattedAddress"})
                testo = risposta.json().get("formattedAddress", "") if risposta.ok else ""
            else:
                risposta = requests.post("https://places.googleapis.com/v1/places:searchText", timeout=20,
                                         json={"textQuery": f"{r['nome']} {r['comune']}", "languageCode": "it",
                                               "regionCode": "IT", "pageSize": 1},
                                         headers={"X-Goog-Api-Key": chiave, "X-Goog-FieldMask": "places.formattedAddress"})
                luoghi = risposta.json().get("places", []) if risposta.ok else []
                testo = luoghi[0].get("formattedAddress", "") if luoghi else ""
            if testo:
                return testo.removesuffix(", Italia").removesuffix(", Italy"), True
        except requests.RequestException:
            pass
    return ", ".join(x for x in (r["indirizzo"], r["comune"]) if x), False


def _qr_svg(url: str) -> str:
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()


def _immagini(r, prop: dict, radice: Path) -> dict:
    trovate = {}
    for chiave, sorgente in (("prima_desktop", r["screenshot_desktop"]), ("prima_mobile", r["screenshot_mobile"]),
                             ("dopo_desktop", prop.get("desktop")), ("dopo_mobile", prop.get("mobile"))):
        percorso = report.risolvi(radice, sorgente)
        if percorso and percorso.exists():
            trovate[chiave] = percorso
    return trovate


def _compilato(cfg: dict, chiave: str) -> str:
    """Il valore della configurazione, o "" se è ancora il segnaposto tra parentesi quadre."""
    valore = (cfg.get(chiave) or "").strip()
    return "" if valore.startswith("[") else valore


def _whatsapp(cfg: dict, nome: str) -> str | None:
    numero = "".join(c for c in _compilato(cfg, "whatsapp") if c.isdigit())
    if len(numero) < 9:
        return None
    return f"https://wa.me/{numero}?text=" + quote(f"Ciao, ho ricevuto la vostra lettera per {nome}: vorrei saperne di più.")


# ---------------------------------------------------------------- pagina personale

PAGINA_CSS = """
@font-face{font-family:'Instrument Serif';src:url(/assets/fonts/InstrumentSerif-400.woff2) format('woff2');font-display:swap}
@font-face{font-family:'Instrument Serif';font-style:italic;src:url(/assets/fonts/InstrumentSerif-400-italic.woff2) format('woff2');font-display:swap}
@font-face{font-family:'Barlow';font-weight:400;src:url(/assets/fonts/Barlow-400.woff2) format('woff2');font-display:swap}
@font-face{font-family:'Barlow';font-weight:600;src:url(/assets/fonts/Barlow-600.woff2) format('woff2');font-display:swap}
:root{--bg:#0b0b0d;--card:#141418;--fg:#f2efe8;--muted:#a9a59c;--oro:#d8b46a;--linea:rgba(255,255,255,.1)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:'Barlow',system-ui,sans-serif;font-size:17px;line-height:1.55}
.wrap{max-width:1080px;margin:0 auto;padding:28px 16px 64px}
header{display:flex;align-items:center;gap:12px;margin-bottom:40px}
header img{width:40px;height:40px}
header span{letter-spacing:.16em;text-transform:uppercase;font-size:12px;color:var(--muted)}
.eyebrow{letter-spacing:.16em;text-transform:uppercase;font-size:12px;color:var(--oro)}
h1{font-family:'Instrument Serif',serif;font-weight:400;font-size:clamp(34px,6vw,60px);line-height:1.05;margin:10px 0 14px;text-wrap:balance}
h1 em{color:var(--oro)}
h2{font-family:'Instrument Serif',serif;font-weight:400;font-size:30px;margin:48px 0 14px}
.lead{color:var(--muted);max-width:640px;margin:0}
.tabs{display:inline-flex;border:1px solid var(--linea);border-radius:999px;padding:4px;margin:32px 0 16px}
.tabs button{all:unset;cursor:pointer;padding:8px 18px;border-radius:999px;color:var(--muted);font-size:15px}
.tabs button[aria-selected=true]{background:var(--fg);color:var(--bg)}
.tabs button:focus-visible{outline:2px solid var(--oro);outline-offset:2px}
.schermi{display:grid;grid-template-columns:minmax(0,1fr) 220px;gap:16px;align-items:start}
.schermi img{width:100%;display:block;border-radius:10px;border:1px solid var(--linea);background:#fff}
.didascalia{font-size:13px;color:var(--muted);margin-top:6px}
@media (max-width:720px){.schermi{grid-template-columns:1fr}.schermi .m{max-width:240px}}
.difetti{list-style:none;padding:0;margin:0;display:grid;gap:10px;max-width:760px}
.difetti li{background:var(--card);border:1px solid var(--linea);border-radius:12px;padding:14px 16px}
.difetti li::before{content:"—";color:var(--oro);margin-right:10px}
.cta{background:var(--card);border:1px solid var(--linea);border-radius:18px;padding:28px;margin-top:48px}
.cta p{color:var(--muted);margin:6px 0 20px;max-width:640px}
.bottoni{display:flex;flex-wrap:wrap;gap:10px}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:0 22px;border-radius:999px;
text-decoration:none;font-weight:600;border:1px solid var(--linea);color:var(--fg)}
.btn.primario{background:var(--oro);border-color:var(--oro);color:#15120a}
.btn:focus-visible{outline:2px solid var(--oro);outline-offset:3px}
.completa{display:inline-block;margin-top:14px;color:var(--oro)}
footer{margin-top:56px;padding-top:20px;border-top:1px solid var(--linea);font-size:13px;color:var(--muted)}
footer a{color:var(--muted)}
"""

PAGINA_JS = """
document.querySelectorAll('.tabs').forEach(function(tabs){
  tabs.addEventListener('click',function(e){
    var b=e.target.closest('button'); if(!b) return;
    tabs.querySelectorAll('button').forEach(function(x){x.setAttribute('aria-selected',x===b?'true':'false')});
    document.querySelectorAll('[data-vista]').forEach(function(v){v.hidden=v.dataset.vista!==b.dataset.vista});
  });
});
"""


def pagina_html(r, ai: dict, cfg: dict, immagini: dict, ha_completa: bool, frase: str = "") -> str:
    nome = _e(r["nome"])
    wa = _whatsapp(cfg, r["nome"])
    vista = lambda lato, titolo: (  # noqa: E731
        f'<div class="schermi" data-vista="{lato}"{" hidden" if lato == "prima" else ""}>'
        f'<div><img src="{lato}-desktop.jpg" alt="{titolo}: {nome} da computer"><div class="didascalia">Da computer</div></div>'
        + (f'<div class="m"><img src="{lato}-mobile.jpg" alt="{titolo}: {nome} da cellulare"><div class="didascalia">Da cellulare</div></div>'
           if f"{lato}_mobile" in immagini else "")
        + "</div>")
    ha_prima = "prima_desktop" in immagini
    tabs = ('<div class="tabs" role="tablist" aria-label="Confronto">'
            '<button type="button" role="tab" aria-selected="true" data-vista="dopo">La nostra proposta</button>'
            '<button type="button" role="tab" aria-selected="false" data-vista="prima">Il sito di oggi</button></div>'
            if ha_prima else "")
    intro = (f"Abbiamo guardato il sito di {nome} e, per farci conoscere, abbiamo immaginato come potrebbe diventare: "
             "più moderno, chiaro da cellulare e pensato per farvi contattare dai clienti."
             if not r["solo_social"] else
             f"Abbiamo visto che {nome} è presente sui social ma non ha ancora un sito tutto suo. "
             "Per farci conoscere abbiamo immaginato come potrebbe essere.")
    difetti = ai.get("difetti") or []
    bottoni = []
    if wa:
        bottoni.append(f'<a class="btn primario" href="{_e(wa)}" target="_blank" rel="noopener">Scrivici su WhatsApp</a>')
    if _compilato(cfg, "telefono"):
        tel = "".join(c for c in cfg["telefono"] if c.isdigit() or c == "+")
        bottoni.append(f'<a class="btn" href="tel:{_e(tel)}">Chiamaci · {_e(cfg["telefono"])}</a>')
    oggetto = quote(f"Anteprima del nuovo sito per {r['nome']}")
    bottoni.append(f'<a class="btn{"" if wa else " primario"}" href="mailto:{_e(cfg["email"])}?subject={oggetto}">Scrivici una email</a>')
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Un'idea per {nome} · Intellecta Solutions</title>
<link rel="icon" href="/assets/img/favicon.png"><style>{PAGINA_CSS}</style></head>
<body><div class="wrap">
<header><img src="/assets/img/logo.png" alt=""><span>Intellecta Solutions</span></header>
<div class="eyebrow">Preparato per {nome}{" · " + _e(r["comune"]) if r["comune"] else ""}</div>
<h1>Il vostro sito, <em>come potrebbe essere</em></h1>
<p class="lead">{_e(frase) if frase else intro}</p>
{tabs}
{vista("dopo", "La nostra proposta")}
{vista("prima", "Il sito di oggi") if ha_prima else ""}
{'<a class="completa" href="proposta.html" target="_blank" rel="noopener">Apri la proposta completa →</a>' if ha_completa else ""}
{"<h2>Cosa si può migliorare</h2><ul class='difetti'>" + "".join(f"<li>{_e(d)}</li>" for d in difetti) + "</ul>" if difetti else ""}
<div class="cta"><h2 style="margin:0">Vi piace l'idea?</h2>
<p>In 15 minuti vi spieghiamo tempi e costi, senza impegno. Possiamo anche aggiungere un assistente che risponde ai clienti su WhatsApp a qualsiasi ora.</p>
<div class="bottoni">{"".join(bottoni)}</div></div>
<footer>Pagina preparata da {_e(cfg["ragione_sociale"])} solo per {nome}, con informazioni pubbliche (sito web e scheda Google).
Non volete ricevere altre comunicazioni? Scrivete a <a href="mailto:{_e(cfg["email"])}?subject={quote("Non contattateci più: " + r["nome"])}">{_e(cfg["email"])}</a>
e vi togliamo dall'elenco. <a href="/privacy.html">Privacy</a></footer>
</div><script>{PAGINA_JS}</script></body></html>"""


# ---------------------------------------------------------------- lettera

LETTERA_CSS = """
@page{size:A4;margin:0}
.lettera{width:210mm;height:297mm;padding:14mm 18mm 12mm;position:relative;break-after:page;overflow:hidden}
.intest{display:flex;justify-content:space-between;align-items:flex-start}
.intest .logo{display:flex;align-items:center;gap:3mm}
.intest .logo img{width:13mm;height:13mm}
.intest .logo b{font-family:'Instrument Serif',serif;font-weight:400;font-size:17pt;color:var(--navy)}
.mitt{font-size:8pt;color:var(--grigio);text-align:right;line-height:1.35}
.dest{margin:9mm 0 0 105mm;font-size:10.5pt;line-height:1.35;min-height:24mm}
.data{margin-top:5mm;color:var(--grigio)}
.ogg{margin-top:4mm;font-weight:600;color:var(--navy)}
.corpo{margin-top:3mm;font-size:10pt}
.corpo p{margin:0 0 2.2mm}
.foto{display:grid;grid-template-columns:1fr 1fr;gap:4mm;margin:3mm 0}
.foto figure{margin:0}
.foto img{width:100%;height:40mm;object-fit:cover;object-position:top;border:1px solid var(--linea);border-radius:1.5mm;display:block}
.foto figcaption{font-size:7.5pt;text-transform:uppercase;letter-spacing:.12em;color:var(--grigio);margin-bottom:1mm}
.foto .dopo figcaption{color:var(--oro);font-weight:600}
.solo{grid-template-columns:1fr}.solo img{height:58mm}
ul.dif{margin:1mm 0 2.5mm;padding-left:5mm}
.qr{display:flex;gap:5mm;align-items:center;border:1px solid var(--oro);background:#fbf7ee;border-radius:3mm;padding:3mm 4mm;margin:2mm 0 3mm}
.qr svg{width:27mm;height:27mm;flex:none}
.qr b{color:var(--navy)}
.qr .url{font-size:8pt;color:var(--grigio);word-break:break-all;margin-top:1mm}
.firma{margin-top:3mm}
.firma .n{font-family:'Instrument Serif',serif;font-size:15pt;color:var(--navy)}
.informativa{position:absolute;left:18mm;right:18mm;bottom:9mm;font-size:6.6pt;color:var(--grigio);line-height:1.35;
border-top:1px solid var(--linea);padding-top:2mm}
"""


def lettera_html(r, ai: dict, cfg: dict, indirizzo: str, url: str, immagini: dict, oggi: dt.date,
                 frase: str = "") -> str:
    nome = _e(r["nome"])
    citta = _compilato(cfg, "cap_citta")
    luogo = citta.split(" ", 1)[-1].split("(")[0].strip() if citta else ""
    parti = [x.strip() for x in indirizzo.split(",") if x.strip()]
    # "Via Roma, 37, 26821 Bertonico LO" → "Via Roma, 37" / "26821 Bertonico LO"
    righe_indirizzo = "<br>".join(_e(x) for x in ([", ".join(parti[:-1]), parti[-1]] if len(parti) > 1 else parti))
    sito = dominio(r["url"]) if not r["solo_social"] else ""
    foto = ""
    if "dopo_desktop" in immagini:
        dopo = f'<figure class="dopo"><figcaption>La nostra proposta</figcaption><img src="{_dati(immagini["dopo_desktop"], "image/jpeg")}" alt=""></figure>'
        if "prima_desktop" in immagini:
            prima = f'<figure><figcaption>Il sito di oggi</figcaption><img src="{_dati(immagini["prima_desktop"], "image/jpeg")}" alt=""></figure>'
            foto = f'<div class="foto">{prima}{dopo}</div>'
        else:
            foto = f'<div class="foto solo">{dopo}</div>'
    apertura = (f"siamo {_e(cfg['ragione_sociale'])}, un'agenzia che crea siti web, assistenti WhatsApp e campagne social per "
                f"le piccole e medie imprese. Abbiamo guardato il sito <b>{_e(sito)}</b> e, per farci conoscere, abbiamo preparato "
                "senza impegno un'idea di come potrebbe diventare."
                if sito else
                f"siamo {_e(cfg['ragione_sociale'])}, un'agenzia che crea siti web, assistenti WhatsApp e campagne social per "
                f"le piccole e medie imprese. Abbiamo visto che {nome} è presente sui social ma non ha ancora un sito tutto suo: "
                "per farci conoscere abbiamo preparato, senza impegno, un'idea di come potrebbe essere.")
    difetti = (ai.get("difetti") or [])[:3]
    contatti = [f"WhatsApp {_e(cfg['whatsapp_leggibile'])}" if cfg.get("whatsapp_leggibile") else "",
                f"telefono {_e(cfg['telefono'])}" if _compilato(cfg, "telefono") else "",
                _e(cfg["email"])]
    contatti = " · ".join(c for c in contatti if c)
    return f"""<section class="lettera">
<div class="intest"><div class="logo"><img src="{_dati(LOGO, 'image/png')}" alt=""><b>{_e(cfg['ragione_sociale'])}</b></div>
<div class="mitt">{_e(cfg['indirizzo'])}<br>{_e(cfg['cap_citta'])}<br>{_e(cfg['email'])}<br>{_e(cfg['sito'].removeprefix('https://'))}</div></div>
<div class="dest">Spett.le<br><b>{nome}</b><br>{righe_indirizzo}</div>
<div class="data">{_e(luogo + ", ") if luogo else ""}{data_lunga(oggi)}</div>
<div class="ogg">Un'idea per il sito di {nome}</div>
<div class="corpo">
<p>Gentile titolare,</p>
<p>{apertura}</p>
{f"<p>{_e(frase)}</p>" if frase else ""}
{foto}
{"<p>Cosa si potrebbe migliorare, in breve:</p><ul class='dif'>" + "".join(f"<li>{_e(d)}</li>" for d in difetti) + "</ul>" if difetti and sito else ""}
<div class="qr">{_qr_svg(url)}<div><b>Inquadrate il codice con il telefono</b>: vedrete l'anteprima completa, da computer e da cellulare,
preparata solo per voi.<div class="url">{_e(url)}</div></div></div>
<p>Se l'idea vi piace, scriveteci ({contatti}): in 15 minuti vi spieghiamo tempi e costi.
Se invece non vi interessa, nessun problema: non vi scriveremo più.</p>
<div class="firma">Un cordiale saluto,<div class="n">{_e(cfg['firma'])}</div>{_e(cfg.get('ruolo', ''))}, {_e(cfg['ragione_sociale'])}</div>
</div>
<div class="informativa"><b>Informativa privacy (art. 14 GDPR).</b> Titolare: {_e(cfg['ragione_sociale'])}{(" di " + _e(cfg['titolare'])) if not _compilato(cfg, 'partita_iva') and cfg.get('titolare') else ""}, {_e(cfg['indirizzo'])}, {_e(cfg['cap_citta'])}.
{("P.IVA " + _e(cfg['partita_iva']) + ".") if _compilato(cfg, 'partita_iva') else ""} Nome e indirizzo della vostra attività provengono da fonti pubbliche (sito web, Google Maps, OpenStreetMap)
e sono usati solo per questa comunicazione, sulla base del nostro legittimo interesse a presentare i nostri servizi alle imprese.
Potete opporvi in qualsiasi momento, chiedere accesso o cancellazione scrivendo a {_e(cfg['email'])}: vi toglieremo subito dall'elenco.
Informativa completa: {_e(cfg['sito'].removeprefix('https://'))}/privacy</div>
</section>"""


LOGO = Path(__file__).resolve().parent.parent / "assets" / "logo.png"


def carica_config(percorso: Path) -> dict:
    cfg = json.loads(percorso.read_text(encoding="utf-8"))
    numero = "".join(c for c in _compilato(cfg, "whatsapp") if c.isdigit())
    if len(numero) >= 9:
        locale = numero[2:] if numero.startswith("39") else numero
        cfg["whatsapp_leggibile"] = f"{locale[:3]} {locale[3:6]} {locale[6:]}".strip()
    return cfg


def mancanti(cfg: dict) -> list[str]:
    return [k for k, v in cfg.items() if isinstance(v, str) and v.startswith("[")]


def prepara(archivio, righe, cfg: dict, radice: Path, cartella_pagine: Path, cartella_lettere: Path, log=print) -> list[dict]:
    """Crea pagina personale (cartella_pagine/<token>/) e lettera PDF per ogni riga. Restituisce l'elenco preparato."""
    from playwright.sync_api import sync_playwright

    oggi = dt.date.today()
    cartella_lettere.mkdir(parents=True, exist_ok=True)
    fatte, sezioni = [], []
    for r in righe:
        prop = json.loads(r["proposta"] or "{}")
        ai = json.loads(r["valutazione_ai"] or "{}")
        immagini = _immagini(r, prop, radice)
        if "dopo_desktop" not in immagini:
            log(f"  {r['nome']}: manca l'anteprima, salto")
            continue
        codice = r["pagina"] or token(r)
        indirizzo, sicuro = indirizzo_postale(r)
        cartella = cartella_pagine / codice
        cartella.mkdir(parents=True, exist_ok=True)
        for chiave, sorgente in immagini.items():
            shutil.copyfile(sorgente, cartella / f"{chiave.replace('_', '-')}.jpg")
        completa = report.risolvi(radice, prop.get("html"))
        if completa and completa.exists():
            testo = completa.read_text(encoding="utf-8")
            if "noindex" not in testo:
                testo = testo.replace("<head>", '<head><meta name="robots" content="noindex,nofollow">', 1)
            (cartella / "proposta.html").write_text(testo, encoding="utf-8")
        (cartella / "index.html").write_text(
            pagina_html(r, ai, cfg, immagini, (cartella / "proposta.html").exists(), prop.get("frase_lettera", "")), encoding="utf-8")
        url = f"{cfg['sito'].rstrip('/')}/per/{codice}/"
        sezioni.append(lettera_html(r, ai, cfg, indirizzo, url, immagini, oggi, prop.get("frase_lettera", "")))
        archivio.aggiorna(r["dominio"], pagina=codice, indirizzo_postale=indirizzo if sicuro else None,
                          lettera_preparata=oggi.isoformat())
        fatte.append({"nome": r["nome"], "indirizzo": indirizzo, "indirizzo_sicuro": sicuro, "pagina": url,
                      "telefono": r["telefono"], "priorita": r["priorita"]})
        log(f"  {r['nome']}: pronta{'' if sicuro else ' (⚠️ indirizzo da verificare)'}")
    if not sezioni:
        return fatte
    documento = (f"<!doctype html><html lang='it'><head><meta charset='utf-8'><style>{_css()}{LETTERA_CSS}</style></head>"
                 f"<body>{''.join(sezioni)}</body></html>")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        pagina = browser.new_page()
        pagina.set_content(documento, wait_until="load")
        pagina.pdf(path=str(cartella_lettere / "lettere.pdf"), format="A4", print_background=True,
                   margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        browser.close()
    return fatte
