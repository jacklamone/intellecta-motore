"""Archivio SQLite: ricorda i siti già analizzati, così nessuno viene pagato o contattato due volte."""

import datetime as dt
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS siti (
    dominio TEXT PRIMARY KEY,
    zona TEXT,
    nome TEXT,
    categoria TEXT,
    url TEXT,
    telefono TEXT,
    email TEXT,
    indirizzo TEXT,
    comune TEXT,
    osm TEXT,
    solo_social INTEGER DEFAULT 0,
    stato TEXT DEFAULT 'da_analizzare',   -- da_analizzare | analizzato | errore
    raggiungibile INTEGER,
    punteggio_tecnico INTEGER,
    problemi TEXT,
    voto_design INTEGER,
    valutazione_ai TEXT,
    priorita INTEGER,
    screenshot_desktop TEXT,
    screenshot_mobile TEXT,
    analizzato_il TEXT,
    contattato TEXT DEFAULT '',
    linkedin TEXT DEFAULT '',
    social TEXT,
    proposta TEXT
);
CREATE TABLE IF NOT EXISTS domini_sostituiti (
    vecchio TEXT PRIMARY KEY,   -- es. veneroni.com, sito vecchio ancora presente su OpenStreetMap
    nuovo TEXT
);
CREATE TABLE IF NOT EXISTS ricerche_google (
    zona TEXT, categoria TEXT, cella INTEGER, fatta_il TEXT,
    PRIMARY KEY (zona, categoria, cella)
);
CREATE TABLE IF NOT EXISTS zone (
    zona TEXT PRIMARY KEY,
    trovate INTEGER,
    ultimo_giro TEXT,
    completata INTEGER DEFAULT 0
);
"""

# Colonne aggiunte dopo la prima versione: vengono create anche negli archivi già esistenti.
COLONNE_NUOVE = {
    "linkedin": "TEXT DEFAULT ''", "social": "TEXT", "proposta": "TEXT",
    # Google Maps
    "google_id": "TEXT", "voto_google": "REAL", "recensioni": "INTEGER DEFAULT 0", "mappa": "TEXT",
    "google_verificato": "TEXT", "fonte": "TEXT DEFAULT 'osm'",
    # Lettere: pagina personale, indirizzo postale completo, chi non vuole essere contattato
    "pagina": "TEXT", "indirizzo_postale": "TEXT", "lettera_preparata": "TEXT", "non_contattare": "INTEGER DEFAULT 0",
    # Scheda Google Maps: voto 0-10 (10 = curata), difetti in chiaro, data del controllo
    "scheda_voto": "INTEGER", "scheda_difetti": "TEXT", "scheda_controllata": "TEXT",
    # Canali di contatto trovati nel sito e bisogni calcolati (sito, WhatsApp, social, Google)
    "canali": "TEXT", "bisogni": "TEXT", "pacchetto": "TEXT",
}

# Campi dell'analisi da azzerare quando il sito cambia indirizzo e va rianalizzato.
CAMPI_ANALISI = ["raggiungibile", "punteggio_tecnico", "problemi", "voto_design", "valutazione_ai", "priorita",
                 "screenshot_desktop", "screenshot_mobile", "analizzato_il", "proposta"]

CAMPI_ATTIVITA = ["nome", "categoria", "url", "telefono", "email", "indirizzo", "comune", "osm", "solo_social"]


def comune_da_indirizzo(indirizzo: str) -> str:
    """'Via Roma 1, 26013 Crema CR, Italia' → 'Crema'."""
    import re
    trovato = re.search(r"\d{5}\s+([^,]+?)\s+[A-Z]{2}\b", indirizzo or "")
    return trovato.group(1) if trovato else ""


class Archivio:
    def __init__(self, percorso: Path):
        percorso.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(percorso)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        esistenti = {r[1] for r in self.conn.execute("PRAGMA table_info(siti)")}
        for nome, tipo in COLONNE_NUOVE.items():
            if nome not in esistenti:
                self.conn.execute(f"ALTER TABLE siti ADD COLUMN {nome} {tipo}")
        self.conn.commit()

    def aggiungi_attivita(self, zona: str, attivita: list[dict]) -> int:
        """Inserisce le attività nuove; non tocca quelle già presenti. Restituisce quante sono nuove."""
        nuove = 0
        sostituiti = {r[0] for r in self.conn.execute("SELECT vecchio FROM domini_sostituiti")}
        for a in attivita:
            if a["dominio"] in sostituiti:
                continue
            cur = self.conn.execute(
                f"INSERT OR IGNORE INTO siti (dominio, zona, {', '.join(CAMPI_ATTIVITA)}) "
                f"VALUES (?, ?, {', '.join('?' * len(CAMPI_ATTIVITA))})",
                [a["dominio"], zona] + [int(a[c]) if c == "solo_social" else a[c] for c in CAMPI_ATTIVITA],
            )
            nuove += cur.rowcount
        self.conn.execute(
            "INSERT INTO zone (zona, trovate, ultimo_giro) VALUES (?, 0, ?) "
            "ON CONFLICT(zona) DO UPDATE SET ultimo_giro = excluded.ultimo_giro",
            [zona, dt.date.today().isoformat()],
        )
        self.aggiorna_conteggio(zona)
        return nuove

    def aggiorna_conteggio(self, zona: str) -> int:
        """Attività con sito nella zona (OpenStreetMap + Google Maps), escluse quelle chiuse."""
        totale = self.conn.execute("SELECT COUNT(*) FROM siti WHERE zona = ? AND stato NOT IN ('chiusa', 'esclusa')", [zona]).fetchone()[0]
        self.conn.execute("UPDATE zone SET trovate = ? WHERE zona = ?", [totale, zona])
        self.conn.commit()
        return totale

    def salva_google(self, dominio: str, g: dict) -> None:
        """Dati della scheda Google Maps; il telefono solo se mancava."""
        self.conn.execute(
            "UPDATE siti SET google_id = ?, voto_google = ?, recensioni = ?, mappa = ?, google_verificato = ?, "
            "telefono = CASE WHEN telefono = '' OR telefono IS NULL THEN ? ELSE telefono END, "
            "comune = CASE WHEN comune = '' OR comune IS NULL THEN ? ELSE comune END WHERE dominio = ?",
            [g["google_id"], g["voto"], g["recensioni"], g["mappa"], dt.date.today().isoformat(),
             g["telefono"], comune_da_indirizzo(g["indirizzo"]), dominio],
        )
        self.conn.commit()

    def segna_verificato(self, dominio: str) -> None:
        self.conn.execute("UPDATE siti SET google_verificato = ? WHERE dominio = ?", [dt.date.today().isoformat(), dominio])
        self.conn.commit()

    def segna_chiusa(self, dominio: str) -> None:
        self.conn.execute("UPDATE siti SET stato = 'chiusa', google_verificato = ? WHERE dominio = ?",
                          [dt.date.today().isoformat(), dominio])
        self.conn.commit()

    def cambia_sito(self, vecchio: str, nuovo: str, url: str) -> str:
        """Il sito è cambiato (es. veneroni.com → veneroni.it): aggiorna e rimette il sito da analizzare.
        Se il dominio nuovo è già in archivio, la riga vecchia era un doppione e viene tolta."""
        if self.conn.execute("SELECT 1 FROM siti WHERE dominio = ?", [nuovo]).fetchone():
            self.conn.execute("INSERT OR REPLACE INTO domini_sostituiti (vecchio, nuovo) VALUES (?, ?)", [vecchio, nuovo])
            self.conn.execute("DELETE FROM siti WHERE dominio = ?", [vecchio])
            self.conn.commit()
            return "doppione"
        self.conn.execute("INSERT OR REPLACE INTO domini_sostituiti (vecchio, nuovo) VALUES (?, ?)", [vecchio, nuovo])
        azzera = ", ".join(f"{c} = NULL" for c in CAMPI_ANALISI)
        self.conn.execute(
            f"UPDATE siti SET dominio = ?, url = ?, stato = 'da_analizzare', {azzera} WHERE dominio = ?",
            [nuovo, url, vecchio],
        )
        self.conn.commit()
        return "aggiornato"

    def da_verificare_google(self, zona: str, priorita_minima: int | None = None) -> list[sqlite3.Row]:
        """Attività non ancora controllate su Google Maps; con priorita_minima solo i contatti migliori già analizzati."""
        filtro, valori = "", [zona]
        if priorita_minima is not None:
            filtro, valori = " AND stato = 'analizzato' AND priorita >= ?", [zona, priorita_minima]
        return self.conn.execute(
            "SELECT * FROM siti WHERE zona = ? AND google_verificato IS NULL AND stato NOT IN ('chiusa', 'esclusa') "
            f"AND fonte != 'google'{filtro} ORDER BY priorita DESC, (telefono = '') ASC, nome", valori,
        ).fetchall()

    def aggiungi_da_google(self, zona: str, attivita: list[dict]) -> int:
        """Attività trovate solo su Google Maps (non su OpenStreetMap)."""
        nuove = 0
        for a in attivita:
            cur = self.conn.execute(
                f"INSERT OR IGNORE INTO siti (dominio, zona, fonte, {', '.join(CAMPI_ATTIVITA)}) "
                f"VALUES (?, ?, 'google', {', '.join('?' * len(CAMPI_ATTIVITA))})",
                [a["dominio"], zona] + [int(a[c]) if c == "solo_social" else a[c] for c in CAMPI_ATTIVITA],
            )
            if cur.rowcount:
                nuove += 1
                self.salva_google(a["dominio"], a["google"])
        self.aggiorna_conteggio(zona)
        return nuove

    def ricerca_fatta(self, zona: str, categoria: str, cella: int) -> bool:
        return self.conn.execute("SELECT 1 FROM ricerche_google WHERE zona = ? AND categoria = ? AND cella = ?",
                                 [zona, categoria, cella]).fetchone() is not None

    def segna_ricerca(self, zona: str, categoria: str, cella: int) -> None:
        self.conn.execute("INSERT OR REPLACE INTO ricerche_google VALUES (?, ?, ?, ?)",
                          [zona, categoria, cella, dt.date.today().isoformat()])
        self.conn.commit()

    def domini(self) -> set[str]:
        return {r[0] for r in self.conn.execute("SELECT dominio FROM siti")}

    def da_analizzare(self, zona: str, limite: int) -> list[sqlite3.Row]:
        # Prima chi ha un telefono: è il contatto più utile.
        return self.conn.execute(
            "SELECT * FROM siti WHERE zona = ? AND stato = 'da_analizzare' "
            "ORDER BY (telefono = '') ASC, nome LIMIT ?",
            [zona, limite],
        ).fetchall()

    def restanti(self, zona: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM siti WHERE zona = ? AND stato = 'da_analizzare'", [zona]
        ).fetchone()[0]

    def aggiorna(self, dominio: str, **campi) -> None:
        for k in ("problemi", "valutazione_ai", "social", "proposta", "canali", "bisogni"):
            if k in campi and not isinstance(campi[k], str) and campi[k] is not None:
                campi[k] = json.dumps(campi[k], ensure_ascii=False)
        assegnazioni = ", ".join(f"{k} = ?" for k in campi)
        self.conn.execute(f"UPDATE siti SET {assegnazioni} WHERE dominio = ?", [*campi.values(), dominio])
        self.conn.commit()

    def segna_zona(self, zona: str, completata: bool) -> None:
        self.conn.execute("UPDATE zone SET completata = ? WHERE zona = ?", [int(completata), zona])
        self.conn.commit()

    def zona_da_aggiornare(self, giorni: int) -> str | None:
        """La zona completata da più tempo, se l'ultimo giro è più vecchio di `giorni`: si ricontrolla
        per trovare le attività nuove."""
        limite = (dt.date.today() - dt.timedelta(days=giorni)).isoformat()
        riga = self.conn.execute(
            "SELECT zona FROM zone WHERE completata = 1 AND ultimo_giro < ? ORDER BY ultimo_giro LIMIT 1", [limite]
        ).fetchone()
        return riga[0] if riga else None

    def zone_completate(self) -> set[str]:
        return {r[0] for r in self.conn.execute("SELECT zona FROM zone WHERE completata = 1")}

    def senza_proposta(self, zona: str, priorita_minima: int, limite: int) -> list[sqlite3.Row]:
        """I contatti migliori ancora senza anteprima: siti brutti (voto ≤ 5) o attività solo social."""
        return self.conn.execute(
            "SELECT * FROM siti WHERE zona = ? AND stato = 'analizzato' AND proposta IS NULL "
            "AND priorita >= ? AND (solo_social = 1 OR (raggiungibile = 1 AND voto_design <= 5)) "
            "ORDER BY priorita DESC LIMIT ?",
            [zona, priorita_minima, limite],
        ).fetchall()

    def risultati(self, zona: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM siti WHERE zona = ? AND stato = 'analizzato' ORDER BY priorita DESC", [zona]
        ).fetchall()
