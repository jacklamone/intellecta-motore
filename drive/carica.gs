// Riceve i file del Lead Finder da GitHub e li salva in Google Drive → Intellecta Solutions → Lead Finder.
// Installazione: script.google.com → Nuovo progetto → incolla questo codice → sostituisci il TOKEN →
// Esegui il deployment → Nuovo deployment → App web, "Esegui come: io", "Chi può accedere: chiunque".

const TOKEN = 'INCOLLA_QUI_IL_TOKEN';
const CARTELLA_LEAD_FINDER = '1ryv6X4pkN3TPE47DAmZIKOgNcgJGAbHy';

function doPost(e) {
  const d = JSON.parse(e.postData.contents);
  if (d.token !== TOKEN) return risposta({ ok: false, errore: 'token non valido' });

  let cartella = DriveApp.getFolderById(CARTELLA_LEAD_FINDER);
  for (const nome of String(d.percorso || '').split('/').filter(String)) {
    const trovate = cartella.getFoldersByName(nome);
    cartella = trovate.hasNext() ? trovate.next() : cartella.createFolder(nome);
  }

  // Un file con lo stesso nome viene sostituito dalla versione nuova.
  const vecchi = cartella.getFilesByName(d.nome);
  while (vecchi.hasNext()) vecchi.next().setTrashed(true);

  const file = cartella.createFile(Utilities.newBlob(Utilities.base64Decode(d.dati), d.tipo, d.nome));
  return risposta({ ok: true, id: file.getId() });
}

function risposta(oggetto) {
  return ContentService.createTextOutput(JSON.stringify(oggetto)).setMimeType(ContentService.MimeType.JSON);
}

// Da eseguire una volta a mano (pulsante ▶ Esegui) per autorizzare l'accesso a Drive.
function autorizza() {
  DriveApp.getFolderById(CARTELLA_LEAD_FINDER).getName();
}
