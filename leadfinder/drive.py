"""Copia report, Excel e anteprime di un giro su Google Drive, tramite un piccolo Google Apps Script
(vedi drive/carica.gs) pubblicato come web app sull'account Google di Intellecta.

Struttura su Drive:  Lead Finder / <Provincia> / <data> / Report.pdf, Tutti i siti (Excel).csv,
                     Anteprime / <Azienda> / Sito attuale…, Proposta…, Messaggi.txt
"""

import base64
import hashlib
import json
import os
import re
from pathlib import Path

import requests

from . import report
from .pdf import nome_zona


def configurato() -> bool:
    return bool(os.environ.get("DRIVE_UPLOAD_URL") and os.environ.get("DRIVE_TOKEN"))


def _nome_file(testo: str) -> str:
    return re.sub(r'[/\\:*?"<>|]', "", testo).strip() or "Senza nome"


def file_del_giro(archivio, zona: str, cartella: Path, radice: Path) -> list[tuple[str, bytes, str]]:
    """(percorso su Drive, contenuto, tipo) per tutti i file di un giro."""
    base = f"{nome_zona(zona).replace('Provincia di ', '')}/{cartella.name}"
    file = []
    for sorgente, nome, tipo in (("report.pdf", "Report.pdf", "application/pdf"),
                                 ("tutti.csv", "Tutti i siti (Excel).csv", "text/csv")):
        if (cartella / sorgente).exists():
            file.append((f"{base}/{nome}", (cartella / sorgente).read_bytes(), tipo))

    righe = archivio.conn.execute("SELECT * FROM siti WHERE zona = ? AND proposta IS NOT NULL", [zona]).fetchall()
    for r in righe:
        p = json.loads(r["proposta"] or "{}")
        azienda = f"{base}/Anteprime/{_nome_file(r['nome'])}"
        for percorso, nome in ((r["screenshot_desktop"], "Sito attuale computer.jpg"),
                               (r["screenshot_mobile"], "Sito attuale cellulare.jpg"),
                               (p.get("desktop"), "Proposta computer.jpg"),
                               (p.get("mobile"), "Proposta cellulare.jpg")):
            sorgente = report.risolvi(radice, percorso)
            if sorgente and sorgente.exists():
                file.append((f"{azienda}/{nome}", sorgente.read_bytes(), "image/jpeg"))
        messaggi = (
            f"{r['nome']}\n{r['url']}\nTelefono: {r['telefono'] or '-'}\n\n"
            f"--- Nota collegamento LinkedIn ---\n{p.get('nota_collegamento', '')}\n\n"
            f"--- Messaggio LinkedIn ---\n{p.get('messaggio_linkedin', '')}\n\n"
            f"--- Email ---\nOggetto: {p.get('email_oggetto', '')}\n\n{p.get('email_testo', '')}\n"
        )
        file.append((f"{azienda}/Messaggi.txt", messaggi.encode("utf-8"), "text/plain"))
    return file


# Impronta dei file già su Drive: un file uguale a quello già caricato non si ricarica.
REGISTRO = Path(__file__).resolve().parent.parent / "dati" / "drive_caricati.json"


def _registro() -> dict:
    try:
        return json.loads(REGISTRO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def carica(file: list[tuple[str, bytes, str]], log=print) -> int:
    """Carica i file nuovi o cambiati; un file già presente con lo stesso nome viene sostituito.
    Restituisce quanti file sono su Drive aggiornati (caricati ora o già presenti)."""
    url, token = os.environ["DRIVE_UPLOAD_URL"], os.environ["DRIVE_TOKEN"]
    registro = _registro()
    gia = sum(1 for percorso, contenuto, _ in file if registro.get(percorso) == hashlib.sha1(contenuto).hexdigest())
    if gia:
        log(f"  Drive: {gia} file già presenti e uguali, li salto")
    riusciti, errori_di_fila = gia, 0
    try:
        for percorso, contenuto, tipo in file:
            impronta = hashlib.sha1(contenuto).hexdigest()
            if registro.get(percorso) == impronta:
                continue
            if _invia(url, token, percorso, contenuto, tipo, log):
                registro[percorso] = impronta
                riusciti += 1
                errori_di_fila = 0
                continue
            errori_di_fila += 1
            if errori_di_fila >= 3 and riusciti == gia:
                log("  Drive: 3 errori di fila, mi fermo (controllare l'Apps Script e i segreti)")
                break
    finally:
        REGISTRO.parent.mkdir(parents=True, exist_ok=True)
        REGISTRO.write_text(json.dumps(registro, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    return riusciti


def _invia(url: str, token: str, percorso: str, contenuto: bytes, tipo: str, log) -> bool:
    cartella, _, nome = percorso.rpartition("/")
    corpo = {"token": token, "percorso": cartella, "nome": nome, "tipo": tipo,
             "dati": base64.b64encode(contenuto).decode()}
    try:
        r = requests.post(url, data=json.dumps(corpo), timeout=120,
                          headers={"Content-Type": "application/json"})
        try:
            esito = r.json()
        except ValueError:
            # Google ha risposto con una pagina web: di solito accesso non "Chiunque" o URL sbagliato.
            testo = " ".join(r.text.split())[:200]
            esito = {"ok": False, "errore": f"HTTP {r.status_code}, risposta non JSON da {r.url[:60]}…: {testo}"}
        if esito.get("ok"):
            return True
        log(f"  Drive: {percorso} non caricato ({esito.get('errore')})")
    except requests.RequestException as ex:
        log(f"  Drive: {percorso} non caricato ({type(ex).__name__})")
    return False
