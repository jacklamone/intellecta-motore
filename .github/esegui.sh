#!/usr/bin/env bash
# Esegue un comando del programma scrivendo il registro completo nel progetto PRIVATO
# (privato/registri/). Questo progetto è pubblico: qui si mostrano solo le righe di riepilogo,
# mai nomi, siti o punteggi delle attività.
set -uo pipefail
cd "$GITHUB_WORKSPACE"
registro="privato/registri/$(date -u +%Y-%m-%d)-${GITHUB_WORKFLOW// /-}-${GITHUB_RUN_ID}.log"
"$@" > "$registro" 2>&1
esito=$?
grep -E "Schede Google: [0-9]|Canali: [0-9]|Bisogni: ricalcolati|Bisogni: esclusi|Google Maps: [0-9]|Google Maps: verifico|Google Drive: [0-9]|Consumo OpenAI|restano [0-9]+ siti|Trovate [0-9]+ PMI" "$registro" \
  | sed -E 's/Report: [^ ]+ — //' || true
if [ $esito -ne 0 ]; then
  echo "::error::Il giro si è fermato (codice $esito). Tipo di errore:"
  grep -E "^[A-Za-z_.]+(Error|Exception):" "$registro" | tail -1 | cut -d: -f1 || true
  echo "Il registro completo è nel progetto privato: ${registro#privato/}"
fi
exit $esito
