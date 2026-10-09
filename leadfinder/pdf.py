"""Report PDF da condividere, con la grafica Intellecta. Generato con Chromium (lo stesso degli screenshot)."""

import base64
import datetime as dt
import html
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

from .fonti import ETICHETTE
from .proposta import link_ricerca_linkedin
from .report import risolvi, stelle

ASSETS = Path(__file__).resolve().parent.parent / "assets"

PROVINCE = {
    "AG": "Agrigento", "AL": "Alessandria", "AN": "Ancona", "AO": "Aosta", "AP": "Ascoli Piceno", "AQ": "L'Aquila",
    "AR": "Arezzo", "AT": "Asti", "AV": "Avellino", "BA": "Bari", "BG": "Bergamo", "BI": "Biella", "BL": "Belluno",
    "BN": "Benevento", "BO": "Bologna", "BR": "Brindisi", "BS": "Brescia", "BT": "Barletta-Andria-Trani",
    "BZ": "Bolzano", "CA": "Cagliari", "CB": "Campobasso", "CE": "Caserta", "CH": "Chieti", "CL": "Caltanissetta",
    "CN": "Cuneo", "CO": "Como", "CR": "Cremona", "CS": "Cosenza", "CT": "Catania", "CZ": "Catanzaro", "EN": "Enna",
    "FC": "Forlì-Cesena", "FE": "Ferrara", "FG": "Foggia", "FI": "Firenze", "FM": "Fermo", "FR": "Frosinone",
    "GE": "Genova", "GO": "Gorizia", "GR": "Grosseto", "IM": "Imperia", "IS": "Isernia", "KR": "Crotone",
    "LC": "Lecco", "LE": "Lecce", "LI": "Livorno", "LO": "Lodi", "LT": "Latina", "LU": "Lucca", "MB": "Monza e Brianza",
    "MC": "Macerata", "ME": "Messina", "MI": "Milano", "MN": "Mantova", "MO": "Modena", "MS": "Massa-Carrara",
    "MT": "Matera", "NA": "Napoli", "NO": "Novara", "NU": "Nuoro", "OR": "Oristano", "PA": "Palermo",
    "PC": "Piacenza", "PD": "Padova", "PE": "Pescara", "PG": "Perugia", "PI": "Pisa", "PN": "Pordenone",
    "PO": "Prato", "PR": "Parma", "PT": "Pistoia", "PU": "Pesaro e Urbino", "PV": "Pavia", "PZ": "Potenza",
    "RA": "Ravenna", "RC": "Reggio Calabria", "RE": "Reggio Emilia", "RG": "Ragusa", "RI": "Rieti", "RM": "Roma",
    "RN": "Rimini", "RO": "Rovigo", "SA": "Salerno", "SI": "Siena", "SO": "Sondrio", "SP": "La Spezia",
    "SR": "Siracusa", "SS": "Sassari", "SU": "Sud Sardegna", "SV": "Savona", "TA": "Taranto", "TE": "Teramo",
    "TN": "Trento", "TO": "Torino", "TP": "Trapani", "TR": "Terni", "TS": "Trieste", "TV": "Treviso", "UD": "Udine",
    "VA": "Varese", "VB": "Verbano-Cusio-Ossola", "VC": "Vercelli", "VE": "Venezia", "VI": "Vicenza",
    "VR": "Verona", "VT": "Viterbo", "VV": "Vibo Valentia",
}


def nome_zona(zona: str) -> str:
    if zona.upper() in PROVINCE:
        return f"Provincia di {PROVINCE[zona.upper()]}"
    if zona.lower().startswith("comune:"):
        return f"Comune di {zona.split(':', 1)[1].strip()}"
    return zona


def _dati(percorso: Path, tipo: str) -> str:
    return f"data:{tipo};base64,{base64.b64encode(percorso.read_bytes()).decode()}"


def _e(testo) -> str:
    return html.escape(str(testo or ""))


def _css() -> str:
    font = [("Barlow", 400, "normal", "Barlow-400"), ("Barlow", 600, "normal", "Barlow-600"),
            ("Instrument Serif", 400, "normal", "InstrumentSerif-400"),
            ("Instrument Serif", 400, "italic", "InstrumentSerif-400-italic")]
    face = "".join(
        f"@font-face{{font-family:'{f}';font-weight:{w};font-style:{s};"
        f"src:url({_dati(ASSETS / (n + '.woff2'), 'font/woff2')}) format('woff2')}}"
        for f, w, s, n in font
    )
    return face + """
:root{--navy:#14213d;--navy-2:#1e2f52;--oro:#b8924a;--oro-chiaro:#f3ead7;--testo:#1c2333;--grigio:#5d6678;
--linea:#e3e0d8;--rosso:#b4432f;--ambra:#b7791f;--verde:#3f7d4e}
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;font-family:'Barlow',sans-serif;font-size:10pt;color:var(--testo);line-height:1.45;background:#fff}
h1,h2,h3{font-family:'Instrument Serif',serif;font-weight:400;margin:0;color:var(--navy)}
.copertina{background:var(--navy);color:#fff;padding:22mm 18mm 16mm;margin:-1px}
.copertina img{width:26mm;height:26mm}
.copertina .etichetta{letter-spacing:.18em;text-transform:uppercase;font-size:8pt;color:var(--oro);margin-top:10mm}
.copertina h1{color:#fff;font-size:34pt;line-height:1.05;margin-top:3mm}
.copertina h1 em{color:#e2c68c}
.copertina .data{color:#c9cfdb;margin-top:3mm}
.kpi{display:grid;grid-template-columns:repeat(4,1fr);gap:4mm;margin-top:10mm}
.kpi div{border:1px solid rgba(226,198,140,.45);border-radius:3mm;padding:4mm}
.kpi b{display:block;font-family:'Instrument Serif',serif;font-size:24pt;font-weight:400;color:#fff;line-height:1}
.kpi span{font-size:8pt;color:#c9cfdb}
.pagina{padding:10mm 18mm 0}
.nota{background:var(--oro-chiaro);border-left:3px solid var(--oro);padding:3mm 4mm;margin:6mm 0;font-size:9pt}
h2{font-size:20pt;margin:8mm 0 3mm}
table{width:100%;border-collapse:collapse;font-size:8.6pt}
th{text-align:left;font-weight:600;color:var(--grigio);font-size:7.5pt;text-transform:uppercase;letter-spacing:.06em;
border-bottom:1.5px solid var(--navy);padding:2mm 1.5mm}
td{border-bottom:1px solid var(--linea);padding:2mm 1.5mm;vertical-align:top}
tr{break-inside:avoid}
.pr{display:inline-block;min-width:9mm;text-align:center;border-radius:2mm;padding:.5mm 1.5mm;font-weight:600;color:#fff}
.alta{background:var(--rosso)}.media{background:var(--ambra)}.bassa{background:var(--verde)}
.scheda{border:1px solid var(--linea);border-radius:3mm;padding:5mm;margin:0 0 6mm;break-inside:avoid}
.testa{display:flex;justify-content:space-between;align-items:flex-start;gap:4mm}
.testa h3{font-size:17pt;line-height:1.1}
.info{color:var(--grigio);font-size:8.8pt;margin-top:1mm}
.info a{color:var(--navy)}
.foto{display:flex;gap:3mm;margin:4mm 0 3mm;align-items:flex-start}
.foto img{border:1px solid var(--linea);border-radius:1.5mm;display:block}
.foto .d{width:118mm}.foto .m{width:36mm}
.voto{display:flex;gap:6mm;font-size:9pt;margin-bottom:2mm}
.voto b{color:var(--navy)}
ul{margin:1mm 0 2mm;padding-left:5mm}li{margin:.5mm 0}
.tecnici{font-size:8pt;color:var(--grigio)}
.proposta{margin-top:2mm}.proposta b{color:var(--oro)}
.apertura{font-family:'Instrument Serif',serif;font-style:italic;font-size:12pt;color:var(--navy);
border-left:2px solid var(--oro);padding-left:3mm;margin-top:3mm}
.proposta-box{border-color:var(--oro);background:linear-gradient(180deg,#fbf7ee,#fff 40%)}
.etichetta-oro{letter-spacing:.14em;text-transform:uppercase;font-size:7.5pt;color:var(--oro);font-weight:600;margin-bottom:1mm}
.msg{margin-top:3mm;font-size:9pt}.msg p{margin:1mm 0 0;white-space:normal}
.legale{font-size:8pt;color:var(--grigio);margin-top:8mm;border-top:1px solid var(--linea);padding-top:3mm}
"""


def _categoria(r) -> str:
    """Traduce anche le categorie salvate in inglese dai primi giri (es. 'Funeral directors')."""
    cat = r["categoria"] or ""
    return ETICHETTE.get(cat.lower().replace(" ", "_"), cat)


def _classe(p: int) -> str:
    return "alta" if p >= 70 else "media" if p >= 50 else "bassa"


def _scheda(i: int, r, radice: Path) -> str:
    ai = json.loads(r["valutazione_ai"] or "{}")
    tecnici = json.loads(r["problemi"] or "[]")
    info = " · ".join(_e(x) for x in [_categoria(r), r["comune"], r["indirizzo"], r["telefono"], r["email"],
                                         stelle(r)] if x)
    foto = ""
    desktop, mobile = risolvi(radice, r["screenshot_desktop"]), risolvi(radice, r["screenshot_mobile"])
    if desktop and desktop.exists():
        foto = f'<img class="d" src="{_dati(desktop, "image/jpeg")}">'
        if mobile and mobile.exists():
            foto += f'<img class="m" src="{_dati(mobile, "image/jpeg")}">'
        foto = f'<div class="foto">{foto}</div>'
    difetti = "".join(f"<li>{_e(d)}</li>" for d in ai.get("difetti") or [])
    return f"""<div class="scheda">
<div class="testa"><div><h3>{i}. {_e(r['nome'])}</h3>
<div class="info">{info}<br><a href="{_e(r['url'])}">{_e(r['url'])}</a><br>{_linkedin(r)}</div></div>
<span class="pr {_classe(r['priorita'])}">{r['priorita']}</span></div>
{foto}
{_voto(r, ai)}
{f'<ul>{difetti}</ul>' if difetti else ''}
{f'<div class="tecnici">Controlli tecnici: {_e("; ".join(tecnici))}</div>' if tecnici else ''}
{f'<div class="proposta"><b>Cosa proporre</b> — {_e(ai["cosa_proporre"])}</div>' if ai.get('cosa_proporre') else ''}
{f'<div class="apertura">“{_e(ai["frase_apertura"])}”</div>' if ai.get('frase_apertura') else ''}
</div>"""


def _voto(r, ai: dict) -> str:
    if r["solo_social"]:
        return '<div class="voto"><span><b>Non ha un sito:</b> usa solo una pagina social</span></div>'
    if not r["voto_design"]:
        return ""
    return (f'<div class="voto"><span>Voto design <b>{r["voto_design"]}/10</b></span>'
            f'<span>Sembra del <b>{_e(ai.get("epoca_stimata", "?"))}</b></span></div>')


def _linkedin(r) -> str:
    if r["linkedin"]:
        return f'LinkedIn: <a href="{_e(r["linkedin"])}">{_e(r["linkedin"])}</a>'
    return f'LinkedIn: <a href="{_e(link_ricerca_linkedin(r["nome"], r["comune"]))}">cerca su LinkedIn</a>'


def _messaggio(titolo: str, testo: str) -> str:
    return f'<div class="msg"><b>{_e(titolo)}</b><p>{_e(testo).replace(chr(10), "<br>")}</p></div>' if testo else ""


def _proposta(r, radice: Path) -> str:
    p = json.loads(r["proposta"] or "{}")
    desktop, mobile = risolvi(radice, p.get("desktop")), risolvi(radice, p.get("mobile"))
    if not (desktop and desktop.exists()):
        return ""
    foto = f'<img class="d" src="{_dati(desktop, "image/jpeg")}">'
    if mobile and mobile.exists():
        foto += f'<img class="m" src="{_dati(mobile, "image/jpeg")}">'
    return f"""<div class="scheda proposta-box">
<div class="etichetta-oro">La nostra proposta</div><h3>Come potrebbe essere — {_e(r['nome'])}</h3>
<div class="foto">{foto}</div></div>
<div class="scheda messaggi"><div class="etichetta-oro">Bozze dei messaggi — {_e(r['nome'])}</div>
{_messaggio("Nota per il collegamento LinkedIn", p.get("nota_collegamento"))}
{_messaggio("Messaggio LinkedIn", p.get("messaggio_linkedin"))}
{_messaggio("Email — oggetto: " + (p.get("email_oggetto") or ""), p.get("email_testo"))}
</div>"""


def _tabella(righe, colonne: str) -> str:
    corpo = "".join(
        f"<tr><td><span class='pr {_classe(r['priorita'])}'>{r['priorita']}</span></td><td><b>{_e(r['nome'])}</b></td>"
        f"<td>{_e(_categoria(r))}</td><td>{_e(r['comune'])}</td><td>{_e(r['telefono']) or '—'}</td>"
        f"<td>{_e(r['url'])}</td></tr>"
        for r in righe
    )
    return (f"<table><thead><tr><th>Priorità</th><th>Attività</th><th>Categoria</th><th>Comune</th>"
            f"<th>Telefono</th><th>{colonne}</th></tr></thead><tbody>{corpo}</tbody></table>")


def genera_html(zona: str, righe, statistiche: dict, radice: Path, max_schede: int = 40) -> str:
    righe = list(righe)
    valutati = [r for r in righe if r["voto_design"]]
    schede = [r for r in righe if (r["voto_design"] or r["proposta"]) and r["priorita"] >= 40][:max_schede]
    social = [r for r in righe if r["solo_social"]]
    irraggiungibili = [r for r in righe if not r["raggiungibile"] and not r["solo_social"]]
    voto_medio = sum(r["voto_design"] for r in valutati) / len(valutati) if valutati else 0
    oggi = dt.date.today().strftime("%d/%m/%Y")
    zona_estesa = nome_zona(zona)

    kpi = [
        (statistiche.get("trovate", "—"), "PMI con sito nella zona"),
        (len(righe), "siti analizzati"),
        (len(schede) + len(social), "contatti promettenti"),
        (f"{voto_medio:.1f}".replace(".", ",") if valutati else "—", "voto medio design (1-10)"),
    ]
    parti = [f"""<!doctype html><html lang="it"><head><meta charset="utf-8"><title>Siti da rifare — {_e(zona_estesa)}</title>
<style>{_css()}</style></head><body>
<section class="copertina">
<img src="{_dati(ASSETS / 'logo.png', 'image/png')}" alt="">
<div class="etichetta">Intellecta Solutions · Analisi siti web PMI</div>
<h1>Siti da rifare<br><em>{_e(zona_estesa)}</em></h1>
<div class="data">Report del {oggi}</div>
<div class="kpi">{''.join(f'<div><b>{_e(v)}</b><span>{_e(t)}</span></div>' for v, t in kpi)}</div>
</section>
<section class="pagina">
<div class="nota"><b>Come leggere il report.</b> La <b>priorità</b> (0-100) combina i controlli tecnici
(cellulare, sicurezza, tecnologie superate, privacy) e il giudizio sulla grafica: più è alta, più il sito è
datato e più vale la pena proporre un rifacimento. Rosso ≥ 70 · Ambra 50-69 · Verde sotto 50.</div>
<h2>I contatti migliori</h2>
{_tabella(schede, "Sito")}"""]

    if schede:
        parti.append("<h2>Schede dettagliate</h2>")
        parti += [_scheda(i, r, radice) + _proposta(r, radice) for i, r in enumerate(schede, 1)]
    if social:
        parti.append("<h2>Senza sito: solo pagina social</h2>"
                     "<p>Attività che al posto del sito hanno una pagina Facebook/Instagram: "
                     "proposta ideale sito + chatbot WhatsApp.</p>")
        parti.append(_tabella(social, "Pagina social"))
    if irraggiungibili:
        parti.append("<h2>Siti che non si aprono</h2><p>Non raggiungibili dai nostri server: verificare a mano. "
                     "Se non si aprono neanche dal browser, il sito è scaduto o abbandonato.</p>")
        parti.append(_tabella(irraggiungibili[:40], "Sito"))
    parti.append("""<div class="legale">Dati delle attività da OpenStreetMap (© contributori OpenStreetMap, licenza ODbL).
Giudizi sulla grafica generati con intelligenza artificiale: da verificare prima del contatto.
Ricordate che in Italia le email commerciali non richieste sono vietate anche verso le aziende (art. 130 Codice Privacy):
preferite telefono o visita.</div></section></body></html>""")
    return "".join(parti)


def genera_pdf(zona: str, righe, statistiche: dict, radice: Path, percorso: Path) -> Path:
    documento = genera_html(zona, righe, statistiche, radice)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        pagina = browser.new_page()
        pagina.set_content(documento, wait_until="load")
        pagina.pdf(
            path=str(percorso), format="A4", print_background=True,
            margin={"top": "0", "bottom": "14mm", "left": "0", "right": "0"},
            display_header_footer=True, header_template="<span></span>",
            footer_template=(
                "<div style='font-size:7pt;color:#8a90a0;width:100%;padding:0 18mm;display:flex;"
                "justify-content:space-between;font-family:sans-serif'><span>Intellecta Solutions · "
                "intellectasolutions.it</span><span><span class='pageNumber'></span>/<span class='totalPages'>"
                "</span></span></div>"
            ),
        )
        browser.close()
    return percorso
