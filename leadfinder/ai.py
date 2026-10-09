"""Chiamata a OpenAI col prezzo "flex" (metà prezzo, risposte un po' più lente).

Se flex non è disponibile in quel momento o per quel modello, si riprova col prezzo normale;
se il modello non accetta reasoning_effort, si riprova senza.
"""

import threading

from openai import APITimeoutError, BadRequestError, OpenAI, RateLimitError

_client = None
_lucchetto = threading.Lock()
# Token usati in questo giro, per modello e tariffa: {("gpt-6-luna", "flex"): [richieste, input, output]}
USO: dict[tuple[str, str], list[int]] = {}


def _cliente() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(timeout=600, max_retries=1)
    return _client


def _senza(parametri: dict, chiave: str) -> dict:
    return {k: v for k, v in parametri.items() if k != chiave}


def chiedi(parametri: dict):
    tentativi = [{**parametri, "service_tier": "flex"}, parametri]
    tentativi += [_senza(t, "reasoning_effort") for t in tentativi if "reasoning_effort" in t]
    ultimo = None
    for p in tentativi:
        try:
            risposta = _cliente().chat.completions.create(**p)
            _registra(risposta)
            return risposta
        except BadRequestError as ex:
            ultimo = ex
        except (RateLimitError, APITimeoutError) as ex:  # flex senza capacità al momento
            if p.get("service_tier") != "flex":
                raise
            ultimo = ex
    raise ultimo


def _registra(risposta) -> None:
    uso = getattr(risposta, "usage", None)
    if not uso:
        return
    chiave = (risposta.model, getattr(risposta, "service_tier", None) or "default")
    with _lucchetto:
        r = USO.setdefault(chiave, [0, 0, 0])
        r[0] += 1
        r[1] += uso.prompt_tokens or 0
        r[2] += uso.completion_tokens or 0


def riepilogo() -> str:
    return "; ".join(f"{m} ({t}): {n} richieste, {i:,} token in, {o:,} token out"
                     for (m, t), (n, i, o) in sorted(USO.items())) or "nessuna richiesta"
