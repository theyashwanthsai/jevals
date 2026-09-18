"""HTTP client for Jev: retry, optional pacing, usage accounting."""
import json, os, threading, time, urllib.request, urllib.error
from pathlib import Path

ENDPOINTS = {
    "openrouter": ("https://openrouter.ai/api/alpha/decisions", "~typesafe/jev-latest", "OPENROUTER_API_KEY"),
    "typesafe":   ("https://api.typesafe.ai/v1/systemone",       "jev-latest",           "TYPESAFE_API_KEY"),
}
RETRY_STATUS = {429, 500, 502, 503, 529}
IN_PRICE_PER_M = 0.042


def load_env(start=None):
    """Walk up from `start` looking for a .env; load without clobbering real env."""
    d = Path(start or Path(__file__).parent).resolve()
    for cand in [d, *d.parents][:4]:
        p = cand / ".env"
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        return p
    return None


load_env(Path.cwd())


class JevError(RuntimeError):
    pass


class Client:
    """Thread-safe. One instance per suite run; accumulates usage.

    min_interval spaces calls out (seconds). Measured 2026-09-18: bursts on the
    OpenRouter alpha endpoint incur a quantized ~1-2.5s queueing tax, while
    calls spaced ~4s apart return in ~415ms. Leave at 0 and raise concurrency
    if you care about total wall clock; set it if you care about per-call latency.
    """

    def __init__(self, provider=None, max_retries=4, min_interval=0.0, timeout=60):
        self.provider = provider or os.environ.get("JEV_PROVIDER", "openrouter")
        if self.provider not in ENDPOINTS:
            raise ValueError(f"unknown provider {self.provider!r}")
        self.url, self.model, self._keyvar = ENDPOINTS[self.provider]
        self.max_retries, self.min_interval, self.timeout = max_retries, min_interval, timeout
        self._lock = threading.Lock()
        self._last = 0.0
        self.calls = self.retries = self.input_tokens = 0
        self.cost = 0.0
        self.latencies = []

    def _key(self):
        k = os.environ.get(self._keyvar)
        if not k:
            raise JevError(f"{self._keyvar} not set (put it in .env)")
        return k

    def _pace(self):
        if self.min_interval <= 0:
            return
        with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def decide(self, state, questions):
        """Returns (answers, meta). meta = {ms, input_tokens, cost, id, model}."""
        payload = json.dumps({"model": self.model, "state": state, "questions": questions}).encode()
        last = None
        for attempt in range(self.max_retries + 1):
            self._pace()
            req = urllib.request.Request(self.url, data=payload, headers={
                "Authorization": f"Bearer {self._key()}",
                "Content-Type": "application/json",
                "X-OpenRouter-Title": "jevals",
            })
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    raw = json.loads(r.read().decode())
                ms = (time.perf_counter() - t0) * 1000
                break
            except urllib.error.HTTPError as e:
                body = e.read().decode()[:300]
                last = JevError(f"HTTP {e.code}: {body}")
                if e.code not in RETRY_STATUS or attempt == self.max_retries:
                    raise last from None
            except urllib.error.URLError as e:
                last = JevError(f"network: {e.reason}")
                if attempt == self.max_retries:
                    raise last from None
            with self._lock:
                self.retries += 1
            time.sleep(min(2 ** attempt * 0.5, 8))
        else:
            raise last

        usage = raw.get("usage") or {}
        toks = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
        cost = usage.get("cost")
        if cost is None:
            cost = toks * IN_PRICE_PER_M / 1_000_000
        with self._lock:
            self.calls += 1
            self.input_tokens += toks
            self.cost += cost
            self.latencies.append(ms)
        if "answers" not in raw:
            raise JevError(f"no 'answers' in response: {json.dumps(raw)[:300]}")
        return raw["answers"], {"ms": ms, "input_tokens": toks, "cost": cost,
                                "id": raw.get("id"), "model": raw.get("model")}
