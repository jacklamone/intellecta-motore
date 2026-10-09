#!/usr/bin/env bash
# Salva i risultati nel progetto PRIVATO. Tutto in silenzio: i nomi dei file contengono i siti delle attività.
set -uo pipefail
cd "$GITHUB_WORKSPACE/privato"
git config user.name "lead-finder"
git config user.email "lead-finder@users.noreply.github.com"
git add -A dati report pagine cruscotto registri >/dev/null 2>&1
git diff --cached --quiet && { echo "Niente di nuovo da salvare"; exit 0; }
git commit -q -m "$1 $(date +%Y-%m-%d)" >/dev/null
for i in 1 2 3 4; do
  if git pull -q --rebase -X theirs >/dev/null 2>&1 && git push -q >/dev/null 2>&1; then echo "Risultati salvati nel progetto privato"; exit 0; fi
  git rebase --abort >/dev/null 2>&1 || true; sleep $((i * 5))
done
echo "::error::Non riesco a salvare i risultati nel progetto privato"; exit 1
