# Intellecta Lead Finder

Trova in automatico le **PMI con un sito web vecchio, rotto o poco moderno**, per proporre un rifacimento
(sito, chatbot WhatsApp, social). Gira tutto su GitHub: **non serve installare niente**.

## Cosa fa

1. **Raccoglie** da OpenStreetMap tutte le attività di una provincia che hanno un sito
   (ristoranti, negozi, artigiani, studi professionali, hotel…). Esclude catene, enti pubblici e scuole.
2. **Controlla il codice** di ogni sito: HTTPS, adattamento al cellulare, anno del copyright,
   tecnologie superate (Flash, tabelle, vecchie versioni di Joomla/WordPress/jQuery), privacy policy.
3. **Fotografa** la home da computer e da cellulare con un vero browser.
4. **Fa valutare gli screenshot a ChatGPT**: voto di design 1-10, epoca in cui sembra fatto,
   3 difetti spiegati semplici, cosa proporre e una frase per aprire la telefonata.
5. **Prepara la proposta** per i contatti migliori, quando la chiedete (**Crea anteprime e messaggi**): l'AI disegna la **nuova home page**
   con i testi e le foto del sito attuale, fotografata da computer e da cellulare, più le **bozze dei messaggi**
   (nota di collegamento LinkedIn, messaggio LinkedIn, email). Cerca anche il link **LinkedIn** nel loro sito.
6. **Stila la classifica**: più alta la *priorità* (0-100), più vale la pena chiamare.
   Sono in cima anche le attività **senza un sito vero** (solo Facebook/Instagram) e quelle con il **sito morto**.

Ogni sito viene analizzato una volta sola: l'archivio (`dati/archivio.sqlite`) se lo ricorda.

## Codice pubblico, dati privati

Questo progetto è **pubblico** e contiene solo il programma (così i minuti di GitHub Actions sono gratis).
Archivio, report, anteprime, pagine personali e registri dei giri stanno nel progetto **privato**
`jacklamone/intellecta-lead-finder`: ogni giro lo scarica in `./privato`, ci lavora e ci salva i risultati.
Nei registri di questo progetto compaiono solo i riepiloghi (quante attività, chiamate, consumo AI),
mai nomi, siti o punteggi: il registro completo di ogni giro è in `registri/` del progetto privato.

## Configurazione (una volta sola)

0. **Accesso ai dati**: secret `DATI_TOKEN` = un *fine-grained personal access token* di GitHub
   (Settings → Developer settings → Personal access tokens → Fine-grained tokens) limitato al solo
   repository `intellecta-lead-finder`, con permesso **Contents: Read and write**.
1. **Chiave OpenAI**: su GitHub aprite questo repository → **Settings** → **Secrets and variables** →
   **Actions** → **New repository secret**. Nome: `OPENAI_API_KEY`, valore: la vostra chiave
   (la trovate su platform.openai.com → API keys). Nessuno potrà più leggerla, nemmeno voi.
2. *(Facoltativo)* Per cambiare modello AI: stessa pagina, scheda **Variables** → `OPENAI_MODEL`
   (predefinito: `gpt-5-mini`, scelto col confronto in `report/confronto-modelli.md`;
   lo si può rifare con **Actions → Confronta modelli AI**). Per le anteprime dei siti rifatti:
   `OPENAI_MODEL_PROPOSTE` (predefinito: `gpt-5`, più bravo nel design).

3. *(Consigliato)* **Google Maps**: secret `GOOGLE_MAPS_API_KEY` con una chiave Google Cloud che abbia
   "Places API (New)" attiva. Serve a verificare il sito attuale dei **contatti migliori** (OpenStreetMap può
   essere vecchio), scartare quelli chiusi e aggiungere voto e recensioni. Ogni giro usa al massimo
   `max_google` chiamate (predefinito 0: le chiamate a pagamento si fanno solo a mano). Google costa circa 35 $ ogni 1.000 chiamate: la ricerca delle
   attività che mancano su OpenStreetMap (`scopri_google`) si attiva solo a mano, costa ~20 $ a provincia.

## Come si usa

**Lanciare una ricerca a mano** (anche da telefono, dal browser):
**Actions** → **Cerca siti da rifare** → **Run workflow** → scrivete la zona → **Run workflow**.

- `PD` = tutta la provincia di Padova (qualsiasi sigla di provincia)
- `comune:Abano Terme` = un solo comune
- vuoto = la prossima provincia della coda

Ci mette da 15 minuti a un'ora circa. Quando la spunta diventa verde, i risultati sono nella cartella **`report`**.

**Anteprime per una zona già analizzata**: **Actions** → **Crea anteprime e messaggi** → **Run workflow**
→ zona (es. `CR`) e quante anteprime creare.

**In automatico**: ogni mattina parte da solo con la prossima provincia di
[`coda_province.txt`](coda_province.txt). Mettete in cima le province dove volete lavorare prima.
Le province grandi richiedono più giri: il sistema continua da dove si era fermato.
Finita la coda passa agli **aggiornamenti**: ogni giorno ricontrolla la provincia analizzata da più tempo
(oltre 4 mesi) e analizza solo le attività nuove.

## Leggere i risultati

- [`report/README.md`](report/README.md): elenco di tutti i giri.
- In ogni giro, il `README.md` ha le schede con screenshot, difetti e frase di apertura, direttamente su GitHub.
- `report.pdf` è il report da condividere: schede, anteprime del sito rifatto e bozze dei messaggi.
- Nella cartella `proposte/` di ogni giro ci sono le anteprime (`proposta-desktop.jpg`, `proposta-mobile.jpg`)
  da allegare ai messaggi, e la pagina `index.html` completa.
- `tutti.csv` si apre con Excel (doppio clic) e contiene tutti i siti analizzati, ordinati per priorità.

## Lettere con QR code (primo contatto senza telefono)

**Actions** → **Prepara lettere** → zona e quante lettere. Prepara, per i contatti migliori con anteprima:
- `report/<zona>/lettere-<data>/lettere.pdf`: una lettera A4 per azienda (prima/dopo, difetti, QR code), da
  stampare o caricare su un servizio di posta online; `indirizzi.csv` con gli indirizzi (verificati su Google Maps);
- `pagine/per/<codice>/`: la pagina personale che si apre col QR code (anteprima completa e pulsanti
  WhatsApp/email), da pubblicare su intellectasolutions.it/per/ — non compare su Google.

I dati del mittente (sede, P.IVA, firma, WhatsApp) sono in [`lettere_config.json`](lettere_config.json).
Chi chiede di non essere più contattato: segnarlo (colonna `non_contattare` = 1) e non riceverà altre lettere.
La spunta "Rifai prima le anteprime" rifà le anteprime con lo stile nuovo (colori chiari per settore, logo ridisegnato).

## Cruscotto contatti

Il cruscotto (link su claude.ai) mostra i contatti migliori con il confronto prima/dopo, i pulsanti per aprire
LinkedIn/Instagram con il messaggio già copiato e lo stato di ogni contatto (da contattare, contattato,
ha risposto…), condiviso tra chi lo usa. `python esporta_cruscotto.py` prepara i dati in `cruscotto/`;
la pubblicazione la fa Claude.

## Costi

- GitHub Actions: gratuito entro i minuti inclusi (repository privati: 2.000 minuti/mese sul piano Free).
  Finiti i minuti del mese i giri si fermano e ripartono il mese dopo (senza costi, se non avete messo
  un budget a pagamento su GitHub).
- OpenStreetMap: gratuito.
- OpenAI: con `gpt-5-mini`, tariffa flex (metà prezzo) e immagini a bassa risoluzione, circa 0,4 centesimi
  ogni 10 siti (~20 $ per tutta Italia). Le anteprime (`gpt-5`, flex) costano qualche centesimo l'una.
  Per contenere la spesa abbassate `max_ai` all'avvio, oppure impostate un limite su platform.openai.com → Limits.

## ⚠️ Prima di contattare

**LinkedIn**: i messaggi vanno inviati a mano. L'invio automatico o lo scraping violano le regole di LinkedIn
e fanno bloccare l'account.


In Italia le **email commerciali non richieste sono vietate anche verso le aziende** (art. 130 Codice Privacy).
Usate telefono (controllando il Registro delle Opposizioni se il numero è di una persona fisica),
visita di persona o il form contatti del loro sito. Il report è pensato per la telefonata: difetti
in parole semplici e una frase di apertura rispettosa.

## Per chi sviluppa

```bash
pip install -r requirements.txt && python -m playwright install chromium
export OPENAI_API_KEY=...
python cerca.py --zona PD --max-siti 20
```

Struttura: `leadfinder/fonti.py` (OpenStreetMap), `controlli.py` (analisi HTML e punteggio),
`screenshot.py` (Playwright), `valutazione_ai.py` (OpenAI), `db.py` (archivio), `report.py` (Markdown + CSV).
