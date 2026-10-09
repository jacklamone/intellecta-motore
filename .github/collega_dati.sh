#!/usr/bin/env bash
# I dati (archivio, report, pagine, cruscotto, mittente delle lettere) stanno nel progetto PRIVATO,
# scaricato in ./privato: qui si collegano con dei link, così il programma li trova al solito posto.
set -euo pipefail
cd "$GITHUB_WORKSPACE"
for d in dati report pagine cruscotto registri; do mkdir -p "privato/$d"; done
for d in dati report pagine cruscotto; do ln -sfn "privato/$d" "$d"; done
[ -f privato/lettere_config.json ] && ln -sfn privato/lettere_config.json lettere_config.json
true
