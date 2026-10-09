"""Screenshot desktop e mobile con un vero browser, più un controllo sulla resa da cellulare."""

import io
import os
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

from .controlli import USER_AGENT

DESKTOP = {"width": 1366, "height": 900}
MOBILE = {"width": 390, "height": 844}


def _salva_jpeg(png: bytes, percorso: Path, larghezza: int) -> None:
    img = Image.open(io.BytesIO(png)).convert("RGB")
    if img.width > larghezza:
        img = img.resize((larghezza, round(img.height * larghezza / img.width)), Image.LANCZOS)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    img.save(percorso, "JPEG", quality=70, optimize=True)


class Fotografo:
    def __enter__(self):
        self._pw = sync_playwright().start()
        # In locale si può indicare un Chromium già installato; su GitHub usa quello di Playwright.
        eseguibile = os.environ.get("CHROMIUM_PATH") or None
        self._browser = self._pw.chromium.launch(executable_path=eseguibile)
        return self

    def __exit__(self, *exc):
        self._browser.close()
        self._pw.stop()

    def _pagina(self, url: str, viewport: dict, mobile: bool):
        contesto = self._browser.new_context(
            viewport=viewport,
            is_mobile=mobile,
            has_touch=mobile,
            device_scale_factor=2 if mobile else 1,
            user_agent=None if mobile else USER_AGENT,  # evita "HeadlessChrome", che alcuni siti bloccano
            locale="it-IT",
            ignore_https_errors=True,
        )
        pagina = contesto.new_page()
        pagina.goto(url, wait_until="load", timeout=30000)
        pagina.wait_for_timeout(2500)  # animazioni, slider, banner cookie
        return contesto, pagina

    def fotografa_html(self, html: str, cartella: Path) -> dict:
        """Screenshot di una pagina generata (l'anteprima del sito nuovo): proposta-desktop/mobile.jpg."""
        risultato = {}
        for nome, viewport, mobile, larghezza in (("desktop", DESKTOP, False, 900), ("mobile", MOBILE, True, 390)):
            contesto = self._browser.new_context(
                viewport=viewport, is_mobile=mobile, has_touch=mobile,
                device_scale_factor=2 if mobile else 1, locale="it-IT",
            )
            try:
                pagina = contesto.new_page()
                pagina.set_content(html, wait_until="load", timeout=45000)
                pagina.wait_for_timeout(1500)
                percorso = cartella / f"proposta-{nome}.jpg"
                _salva_jpeg(pagina.screenshot(), percorso, larghezza)
                risultato[nome] = str(percorso)
            finally:
                contesto.close()
        return risultato

    def fotografa(self, url: str, cartella: Path) -> dict:
        """Salva desktop.jpg e mobile.jpg nella cartella. Restituisce i controlli sulla versione mobile."""
        risultato = {"desktop": None, "mobile": None, "non_adatto_mobile": False}
        contesto, pagina = self._pagina(url, DESKTOP, mobile=False)
        try:
            _salva_jpeg(pagina.screenshot(), cartella / "desktop.jpg", 900)
            risultato["desktop"] = str(cartella / "desktop.jpg")
        finally:
            contesto.close()

        contesto, pagina = self._pagina(url, MOBILE, mobile=True)
        try:
            larghezza = pagina.evaluate("() => document.documentElement.scrollWidth")
            risultato["non_adatto_mobile"] = larghezza > MOBILE["width"] + 20
            risultato["larghezza_mobile"] = larghezza
            _salva_jpeg(pagina.screenshot(), cartella / "mobile.jpg", 390)
            risultato["mobile"] = str(cartella / "mobile.jpg")
        finally:
            contesto.close()
        return risultato
