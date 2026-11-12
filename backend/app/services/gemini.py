"""Appels serveur vers Gemini (Google GenAI SDK) : timeout, retries avec backoff, usage des jetons.

La clé d'API ne quitte jamais le backend. Les tests remplacent `generate` / `stream`.
"""
from __future__ import annotations

import logging
import random
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.errors import AppError

log = logging.getLogger("documind.gemini")
_client = None


@dataclass
class Usage:
    prompt_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    extra: dict = field(default_factory=dict)


def _get_client():
    global _client
    if _client is None:
        s = get_settings()
        if not s.gemini_api_key:
            raise AppError(503, "GEMINI_API_KEY n'est pas configurée sur le serveur.", "gemini_not_configured")
        from google import genai
        from google.genai import types

        _client = genai.Client(api_key=s.gemini_api_key,
                               http_options=types.HttpOptions(timeout=s.gemini_timeout_s * 1000))
    return _client


def _config(system: str | None, temperature: float, max_tokens: int | None, json_schema: dict | None,
            thinking: bool = True):
    from google.genai import types

    s = get_settings()
    kwargs: dict = {"temperature": temperature, "max_output_tokens": max_tokens or s.gemini_max_output_tokens}
    if system:
        kwargs["system_instruction"] = system
    if thinking and s.gemini_thinking_budget is not None:
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=s.gemini_thinking_budget)
    if json_schema:
        kwargs["response_mime_type"] = "application/json"
        kwargs["response_schema"] = json_schema
    return types.GenerateContentConfig(**kwargs)


def _translate(exc: Exception) -> AppError:
    code = getattr(exc, "code", None)
    log.warning("Erreur Gemini (%s) : %s", code, type(exc).__name__)
    if code == 429:
        return AppError(429, "Quota Gemini atteint. Réessayez dans quelques instants.", "gemini_quota")
    if code in (401, 403):
        return AppError(502, "Clé Gemini refusée : vérifiez GEMINI_API_KEY.", "gemini_auth")
    if code in (400, 404):
        return AppError(502, "Requête refusée par Gemini (modèle ou paramètres invalides).", "gemini_bad_request")
    return AppError(503, "Le service Gemini est momentanément indisponible.", "gemini_unavailable")


def _retryable(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    # 504 (délai dépassé) : inutile d'attendre encore le même modèle, on bascule sur le suivant
    return code in (429, 500, 502, 503) or code is None


def _with_retries(fn):
    s = get_settings()
    last: Exception | None = None
    for attempt in range(s.gemini_max_retries):
        try:
            return fn()
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 - erreurs SDK / réseau
            last = exc
            if not _retryable(exc) or attempt == s.gemini_max_retries - 1:
                break
            time.sleep(min(8.0, 1.0 * 2 ** attempt) + random.random() * 0.3)
    raise _translate(last) from last


def _usage(resp, t0: float) -> Usage:
    um = getattr(resp, "usage_metadata", None)
    return Usage(
        prompt_tokens=getattr(um, "prompt_token_count", 0) or 0,
        output_tokens=getattr(um, "candidates_token_count", 0) or 0,
        latency_ms=round((time.perf_counter() - t0) * 1000),
    )


def _models() -> list[str]:
    s = get_settings()
    return list(dict.fromkeys([s.gemini_model] + [m.strip() for m in s.gemini_fallback_models.split(",") if m.strip()]))


_no_thinking: set[str] = set()        # modèles qui refusent thinking_config (400 INVALID_ARGUMENT)
_down_until: dict[str, float] = {}    # modèle -> instant jusqu'auquel il est mis à l'écart (surcharge, timeout)
COOLDOWN_S = 120.0


def _attempt(call, model: str):
    """Appelle un modèle ; sur un 400, réessaie une fois sans thinking_config et mémorise le refus.

    Certains modèles (ex. gemini-3.5-flash-lite) rejettent thinking_budget=0 alors que d'autres l'acceptent.
    """
    thinking = model not in _no_thinking and get_settings().gemini_thinking_budget is not None
    try:
        return _with_retries(lambda: call(model, thinking))
    except AppError as exc:
        if not (thinking and getattr(exc.__cause__, "code", None) == 400):
            raise
        log.warning("Modèle %s : 400 avec thinking_config, nouvel essai sans ce paramètre", model)
        result = _with_retries(lambda: call(model, False))
        _no_thinking.add(model)
        return result


def _with_fallback(call):
    """Essaie le modèle principal puis les modèles de secours (surcharge 503/504, quota 429, modèle retiré 404).

    Un modèle qui vient d'échouer pour indisponibilité est essayé en dernier pendant COOLDOWN_S secondes,
    pour ne pas faire attendre chaque question jusqu'au timeout.
    """
    now = time.monotonic()
    configured = _models()
    models = ([m for m in configured if _down_until.get(m, 0) <= now]
              + [m for m in configured if _down_until.get(m, 0) > now])
    for i, model in enumerate(models):
        try:
            result = _attempt(call, model)
            _down_until.pop(model, None)
            return result, model
        except AppError as exc:
            if exc.code in ("gemini_unavailable", "gemini_quota"):
                _down_until[model] = time.monotonic() + COOLDOWN_S
            if exc.code == "gemini_auth" or i == len(models) - 1:
                raise
            log.warning("Modèle %s indisponible (%s) : bascule sur %s", model, exc.code, models[i + 1])
    raise AppError(503, "Le service Gemini est momentanément indisponible.", "gemini_unavailable")


def generate(prompt: str, system: str | None = None, temperature: float = 0.2, max_tokens: int | None = None,
             json_schema: dict | None = None) -> tuple[str, Usage]:
    client = _get_client()
    t0 = time.perf_counter()
    resp, model = _with_fallback(lambda m, thinking: client.models.generate_content(
        model=m, contents=prompt, config=_config(system, temperature, max_tokens, json_schema, thinking)))
    usage = _usage(resp, t0)
    usage.extra["model"] = model
    return (resp.text or "").strip(), usage


def stream(prompt: str, usage: Usage, system: str | None = None, temperature: float = 0.2) -> Iterator[str]:
    """Génère la réponse par fragments ; `usage` est rempli à la fin du flux."""
    client = _get_client()
    t0 = time.perf_counter()

    def start(m: str, thinking: bool):
        # la requête HTTP part au premier next() : on l'inclut dans les retries / la bascule
        gen = client.models.generate_content_stream(
            model=m, contents=prompt, config=_config(system, temperature, None, None, thinking))
        return next(gen, None), gen

    (first, rest), model = _with_fallback(start)
    usage.extra["model"] = model
    last = None
    try:
        for chunk in ([first] if first is not None else []) + [None]:
            if chunk is None:
                break
            last = chunk
            if chunk.text:
                yield chunk.text
        for chunk in rest:
            last = chunk
            if chunk.text:
                yield chunk.text
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _translate(exc) from exc
    u = _usage(last, t0)
    usage.prompt_tokens, usage.output_tokens, usage.latency_ms = u.prompt_tokens, u.output_tokens, u.latency_ms
