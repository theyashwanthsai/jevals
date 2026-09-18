"""Minimal Jev client. Zero dependencies (stdlib only).

Talks to OpenRouter by default; set JEV_PROVIDER=typesafe to hit TypeSafe direct.
"""
import json, os, time, urllib.request, urllib.error
from pathlib import Path

ENDPOINTS = {
    "openrouter": ("https://openrouter.ai/api/alpha/decisions", "~typesafe/jev-latest", "OPENROUTER_API_KEY"),
    "typesafe":   ("https://api.typesafe.ai/v1/systemone",       "jev-latest",           "TYPESAFE_API_KEY"),
}
IN_PRICE_PER_M = 0.042  # USD / 1M input tokens (output is $0)


def _load_env():
    p = Path(__file__).parent / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def decide(state, questions, timeout=60):
    """POST one decision request. Returns (parsed_json, latency_ms)."""
    provider = os.environ.get("JEV_PROVIDER", "openrouter")
    url, model, keyvar = ENDPOINTS[provider]
    key = os.environ.get(keyvar)
    if not key:
        raise SystemExit(f"{keyvar} not set. Put it in .env (see .env.example)")

    body = json.dumps({"model": model, "state": state, "questions": questions}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "X-OpenRouter-Title": "jev-test",
    })
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {e.read().decode()[:600]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"network error: {e.reason}") from None
    return raw, (time.perf_counter() - t0) * 1000


def cost_usd(raw):
    """Input cost + token count from the usage block."""
    u = raw.get("usage") or {}
    toks = u.get("input_tokens") or u.get("prompt_tokens") or 0
    return toks * IN_PRICE_PER_M / 1_000_000, toks
