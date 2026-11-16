"""ai_de_kit.py - starter kit for the AI x data engineering projects.

Standard library only. Read it, then rewrite each part yourself as you do the projects.

What is in here (and which project uses it)
  P1  triage:    MockLLM / OllamaLLM / AnthropicLLM, CachedLLM, GuardedLLM, Router, redact_pii,
                 parse_json_loose, validate_ticket, classification_report, triage()
  P2  RAG:       chunk_text, HashEmbedder, OllamaEmbedder, VectorStore, recall_at_k, build_rag_prompt, check_citations
  P3  quality:   detect_volume_anomalies, check_freshness, build_incident_prompt, summarize_without_llm
  P4  text->SQL: check_sql, safe_select, execution_accuracy
  P5  cost:      PRICES, estimate_cost, cost_scenarios, build_batch_requests, LoggedLLM, ledger_report

IMPORTANT HONESTY NOTES
  * MockLLM is a rule-based stand-in so the plumbing can be tested offline. It says NOTHING about
    how well a real model performs. Always measure a real model on your own golden set.
  * OllamaLLM and AnthropicLLM were written from the vendors' documentation and were NOT run
    against a live model while this kit was built. Test them with 5 requests before trusting them.
  * Prices in PRICES come from the Claude API pricing page as read in October 2026. Prices change.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import statistics
import time
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Optional

# =====================================================================================
# 1. Prices and cost maths
# =====================================================================================
# USD per million tokens. Source: platform.claude.com/docs/en/about-claude/pricing (read Oct 2026).
# Haiku 5.5 price is for prompts up to 100K tokens. cache_read is a multiplier on the input price.
PRICES = {
    "claude-haiku-5-5":  {"in": 0.10,  "out": 0.50,  "cache_read": 0.10},
    "claude-sonnet-5-5": {"in": 2.00,  "out": 10.00, "cache_read": 0.05},
    "claude-opus-5-5":   {"in": 4.00,  "out": 20.00, "cache_read": 0.05},
    "claude-fable-5-1":  {"in": 10.00, "out": 50.00, "cache_read": 0.025},
}
CACHE_WRITE_5MIN = 1.25   # multiplier on input price
CACHE_WRITE_1HOUR = 2.0
BATCH_DISCOUNT = 0.5      # Batch API: 50% off input and output; stacks with caching

# The mock models borrow the price of the real model class they stand in for.
MODEL_CLASS = {"mock-cheap": "claude-haiku-5-5", "mock-strong": "claude-sonnet-5-5"}


def approx_tokens(text: str) -> int:
    """Very rough: about 4 characters per token for English. Use the provider's counter for real budgets."""
    return max(1, len(text) // 4)


def estimate_cost(model: str, input_tokens: int, output_tokens: int, *, batch: bool = False,
                  cache_write_tokens: int = 0, cache_read_tokens: int = 0,
                  cache_write_mult: float = CACHE_WRITE_5MIN) -> float:
    """USD cost of one request. input_tokens = fresh (uncached) input only."""
    model = MODEL_CLASS.get(model, model)
    if model not in PRICES:
        return 0.0  # local / unknown models cost no API money (they still cost hardware and time)
    p = PRICES[model]
    cost = (input_tokens * p["in"]
            + cache_write_tokens * p["in"] * cache_write_mult
            + cache_read_tokens * p["in"] * p["cache_read"]
            + output_tokens * p["out"]) / 1_000_000
    return cost * (BATCH_DISCOUNT if batch else 1.0)


def cost_scenarios(requests: int = 100_000, system_tokens: int = 1200, user_tokens: int = 350,
                   output_tokens: int = 60, cache_hit_rate: float = 0.9, escalation_rate: float = 0.15) -> list:
    """Compare ways to run the same job. Returns [(name, total_usd)]. Every input is an assumption you can change.

    The system prompt must be at least 512 tokens for Haiku 5.5, Sonnet 5.5 and Opus 5.5, or it is silently not cached.
    """
    def run(model, batch=False, cached=False, n=requests):
        if cached:
            hits = int(n * cache_hit_rate)
            misses = n - hits
            c = hits * estimate_cost(model, user_tokens, output_tokens, batch=batch, cache_read_tokens=system_tokens)
            c += misses * estimate_cost(model, user_tokens, output_tokens, batch=batch, cache_write_tokens=system_tokens)
            return c
        return n * estimate_cost(model, user_tokens + system_tokens, output_tokens, batch=batch)

    n_esc = int(requests * escalation_rate)
    n_cheap = requests - n_esc
    routed = run("claude-haiku-5-5", True, True, n_cheap) + run("claude-haiku-5-5", True, True, n_esc) \
        + run("claude-sonnet-5-5", True, True, n_esc)  # escalated tickets are paid for twice
    return [
        ("A. Sonnet 5.5, standard, no caching", run("claude-sonnet-5-5")),
        ("B. Haiku 5.5, standard, no caching", run("claude-haiku-5-5")),
        ("C. Haiku 5.5, Batch API", run("claude-haiku-5-5", batch=True)),
        ("D. Haiku 5.5, Batch API + prompt caching", run("claude-haiku-5-5", batch=True, cached=True)),
        ("E. Routed: Haiku first, 15% escalate to Sonnet 5.5 (batch + caching)", routed),
        ("F. Sonnet 5.5, Batch API + prompt caching", run("claude-sonnet-5-5", batch=True, cached=True)),
    ]


# =====================================================================================
# 2. LLM backends behind one tiny interface
# =====================================================================================
@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    cost_usd: float = 0.0
    from_cache: bool = False


CATEGORIES = ["billing", "shipping", "returns", "product_fault", "account_access", "other"]
PRIORITIES = ["low", "medium", "high"]

KEYWORDS = {
    "billing": ["charged twice", "invoice", "overcharged", "payment failed", "receipt", "billing"],
    "shipping": ["delivery", "tracking", "courier", "parcel", "shipped", "delayed"],
    "returns": ["return", "exchange", "wrong size", "send it back", "return label"],
    "product_fault": ["broken", "stopped working", "faulty", "cracked", "defective", "won't turn on"],
    "account_access": ["password", "locked out", "login", "verification code", "reset link"],
}
HIGH_WORDS = ["urgent", "immediately", "second time", "chargeback"]
MEDIUM_WORDS = ["still waiting", "no reply", "again"]
REFUND_WORDS = ["refund", "money back"]


def keyword_hits(text: str) -> dict:
    t = text.lower()
    return {c: sum(1 for k in kws if k in t) for c, kws in KEYWORDS.items()}


def _stable_pct(text: str, salt: str) -> int:
    return int(hashlib.sha256((salt + text).encode()).hexdigest(), 16) % 100


class MockLLM:
    """Rule-based stand-in for a ticket-triage model. Deterministic. NOT a real model.

    tier='cheap'  counts keywords over the whole text (fails on mixed tickets, reports low confidence when mixed)
                  and is confidently wrong on 5% of tickets.
    tier='strong' weights the first sentence 3x and is wrong on 3% of tickets.
    Tokens are estimated from text length; cost uses the price of the class the tier stands in for.
    """

    def __init__(self, tier: str = "cheap"):
        assert tier in ("cheap", "strong")
        self.tier = tier
        self.model = f"mock-{tier}"
        self.calls = 0

    def complete(self, system: str, user: str, max_tokens: int = 200) -> LLMResult:
        self.calls += 1
        text = user
        if self.tier == "cheap":
            hits = keyword_hits(text)
        else:
            first, _, rest = text.partition(".")
            h1, h2 = keyword_hits(first), keyword_hits(rest)
            hits = {c: 3 * h1[c] + h2[c] for c in h1}
        total = sum(hits.values())
        if total == 0:
            cat, conf = "other", 0.9
        else:
            cat = max(hits, key=lambda c: (hits[c], -list(hits).index(c)))
            conf = round(hits[cat] / total, 2)
        wrong_pct = 5 if self.tier == "cheap" else 3
        if _stable_pct(text, self.model) < wrong_pct:  # a confident mistake that routing cannot catch
            others = [c for c in CATEGORIES if c != cat]
            cat, conf = others[_stable_pct(text, "pick") % len(others)], 0.95
        low = text.lower()
        pri = "high" if any(w in low for w in HIGH_WORDS) else "medium" if any(w in low for w in MEDIUM_WORDS) else "low"
        out = json.dumps({"category": cat, "priority": pri,
                          "refund_requested": any(w in low for w in REFUND_WORDS), "confidence": conf})
        i, o = approx_tokens(system + user), approx_tokens(out)
        return LLMResult(out, i, o, self.model, estimate_cost(self.model, i, o))


class OllamaLLM:
    """Local model through Ollama's REST API (default http://localhost:11434). Zero API cost.
    Written from the Ollama API docs, NOT tested against a running server here."""

    def __init__(self, model: str = "llama3.2", host: str = "http://localhost:11434", timeout: int = 120):
        self.model, self.host, self.timeout = model, host.rstrip("/"), timeout

    def complete(self, system: str, user: str, max_tokens: int = 200) -> LLMResult:
        body = {"model": self.model, "stream": False, "format": "json",
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "options": {"temperature": 0, "num_predict": max_tokens}}
        req = urllib.request.Request(self.host + "/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read())
        return LLMResult(data["message"]["content"], data.get("prompt_eval_count", 0),
                         data.get("eval_count", 0), self.model, 0.0)


class AnthropicLLM:
    """Claude API with prompt caching on the system prompt. Needs `pip install anthropic` and ANTHROPIC_API_KEY.
    Written from the official docs, NOT run here. The system prompt must be >= 512 tokens on the 5.5 models
    or it is not cached (no error is raised). Check usage.cache_read_input_tokens to confirm caching works."""

    def __init__(self, model: str = "claude-haiku-5-5"):
        import anthropic  # imported late so the rest of the kit works without it
        self.client, self.model = anthropic.Anthropic(), model

    def complete(self, system: str, user: str, max_tokens: int = 200) -> LLMResult:
        r = self.client.messages.create(
            model=self.model, max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}])
        u = r.usage
        cr = getattr(u, "cache_read_input_tokens", 0) or 0
        cw = getattr(u, "cache_creation_input_tokens", 0) or 0
        cost = estimate_cost(self.model, u.input_tokens, u.output_tokens, cache_write_tokens=cw, cache_read_tokens=cr)
        return LLMResult(r.content[0].text, u.input_tokens + cr + cw, u.output_tokens, self.model, cost)


def build_batch_requests(items: dict, model: str, system: str, max_tokens: int = 200) -> list:
    """items: {custom_id: user_text}. Returns the request list for client.messages.batches.create(requests=...).
    custom_id must be 1-64 chars of [a-zA-Z0-9_-]. Results arrive in any order, so match on custom_id.
    Batch = 50% off, most batches finish in under an hour, hard limit 24 hours. Not run here."""
    return [{"custom_id": cid, "params": {"model": model, "max_tokens": max_tokens, "system": system,
                                          "messages": [{"role": "user", "content": txt}]}}
            for cid, txt in items.items()]


# =====================================================================================
# 3. Wrappers: cache, budget guard, router
# =====================================================================================
class BudgetExceeded(RuntimeError):
    pass


class GuardedLLM:
    """Refuses to make a call once the money budget is spent."""

    def __init__(self, inner, limit_usd: float):
        self.inner, self.limit, self.spent = inner, limit_usd, 0.0
        self.model = inner.model

    def complete(self, system, user, max_tokens=200):
        if self.spent >= self.limit:
            raise BudgetExceeded(f"budget ${self.limit:.4f} reached (spent ${self.spent:.4f})")
        res = self.inner.complete(system, user, max_tokens)
        self.spent += res.cost_usd
        return res


class CachedLLM:
    """Exact-match cache in SQLite. A repeated (model, prompt version, system, user) costs nothing.
    Put the prompt VERSION in the key so editing a prompt never serves stale answers."""

    def __init__(self, inner, path: str = ":memory:", prompt_version: str = "v1"):
        self.inner, self.version, self.model = inner, prompt_version, inner.model
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, text TEXT, i INT, o INT, model TEXT)")
        self.hits = self.misses = 0

    def _key(self, system, user):
        return hashlib.sha256(json.dumps([self.model, self.version, system, user]).encode()).hexdigest()

    def complete(self, system, user, max_tokens=200):
        k = self._key(system, user)
        row = self.db.execute("SELECT text,i,o,model FROM cache WHERE k=?", (k,)).fetchone()
        if row:
            self.hits += 1
            return LLMResult(row[0], row[1], row[2], row[3], 0.0, True)
        self.misses += 1
        res = self.inner.complete(system, user, max_tokens)
        self.db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?,?)", (k, res.text, res.input_tokens, res.output_tokens, res.model))
        self.db.commit()
        return res


def parse_json_loose(text: str) -> Optional[dict]:
    """Models sometimes wrap JSON in prose or code fences. Pull out the first {...} block."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r"\{.*\}", text or "", re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def validate_ticket(obj) -> list:
    """Return a list of problems; empty list means valid. Replace with Pydantic once you know what it checks."""
    if not isinstance(obj, dict):
        return ["not an object"]
    errs = []
    if obj.get("category") not in CATEGORIES:
        errs.append(f"bad category {obj.get('category')!r}")
    if obj.get("priority") not in PRIORITIES:
        errs.append(f"bad priority {obj.get('priority')!r}")
    if not isinstance(obj.get("refund_requested"), bool):
        errs.append("refund_requested must be true or false")
    c = obj.get("confidence")
    if not isinstance(c, (int, float)) or isinstance(c, bool) or not 0 <= c <= 1:
        errs.append("confidence must be a number from 0 to 1")
    return errs


class Router:
    """Try the cheap model; escalate to the strong one when output is invalid or confidence is low."""

    def __init__(self, cheap, strong, threshold: float = 0.8):
        self.cheap, self.strong, self.threshold = cheap, strong, threshold
        self.stats = Counter()

    def route(self, system: str, user: str):
        r1 = self.cheap.complete(system, user)
        obj = parse_json_loose(r1.text)
        ok = obj is not None and not validate_ticket(obj)
        if ok and obj["confidence"] >= self.threshold:
            self.stats["cheap_only"] += 1
            return obj, [r1]
        self.stats["escalated"] += 1
        r2 = self.strong.complete(system, user)
        obj2 = parse_json_loose(r2.text)
        if obj2 is None or validate_ticket(obj2):
            self.stats["failed_validation"] += 1
            return None, [r1, r2]
        return obj2, [r1, r2]


# =====================================================================================
# 4. Privacy: redact before text leaves your machine
# =====================================================================================
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+?61[ -]?|0)[2-478](?:[ -]?\d){8}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,16}(?!\d)")


def redact_pii(text: str):
    """Replace emails, Australian phone numbers and card-like numbers. Returns (clean_text, counts).
    Regex catches only obvious patterns. It will miss names and addresses, so treat it as one layer, not a guarantee."""
    counts = {}
    for name, rx in (("EMAIL", _EMAIL), ("CARD", _CARD), ("PHONE", _PHONE)):
        text, n = rx.subn(f"[{name}]", text)
        counts[name] = n
    return text, counts


# =====================================================================================
# 5. Project 1 pipeline + evaluation
# =====================================================================================
TRIAGE_SYSTEM = ("You triage customer support tickets for a retailer. Reply with JSON only: "
                 '{"category": one of billing|shipping|returns|product_fault|account_access|other, '
                 '"priority": low|medium|high, "refund_requested": true|false, "confidence": 0 to 1}. '
                 "Category is the customer's PRIMARY problem, which is usually named first.")


def norm_text(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().lower())


def triage(tickets: list, router: Router, redact: bool = True) -> dict:
    """tickets: [{'id','text'}]. Deduplicates identical texts BEFORE calling any model."""
    unique, order = {}, []
    for t in tickets:
        clean = redact_pii(t["text"])[0] if redact else t["text"]
        key = hashlib.sha256(norm_text(clean).encode()).hexdigest()
        order.append((t["id"], key))
        unique.setdefault(key, clean)
    answers, spent, calls = {}, 0.0, 0
    for key, clean in unique.items():
        obj, results = router.route(TRIAGE_SYSTEM, clean)
        answers[key] = obj
        spent += sum(r.cost_usd for r in results)
        calls += len(results)
    return {"preds": {tid: answers[k] for tid, k in order}, "cost_usd": spent, "model_calls": calls,
            "unique_texts": len(unique), "tickets": len(tickets)}


def classification_report(y_true: list, y_pred: list) -> dict:
    labels = sorted(set(y_true) | set(y_pred))
    rep = {}
    for lab in labels:
        tp = sum(1 for a, b in zip(y_true, y_pred) if a == lab and b == lab)
        fp = sum(1 for a, b in zip(y_true, y_pred) if a != lab and b == lab)
        fn = sum(1 for a, b in zip(y_true, y_pred) if a == lab and b != lab)
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        rep[lab] = {"precision": round(p, 3), "recall": round(r, 3), "support": tp + fn}
    rep["accuracy"] = round(sum(a == b for a, b in zip(y_true, y_pred)) / len(y_true), 4) if y_true else 0.0
    return rep


# =====================================================================================
# 6. Project 2: retrieval (RAG) building blocks
# =====================================================================================
STOP = set("a an the of to in on at for and or is are was were be do does did i my me you your we our it its "
           "can how what when where which who with from by as this that if not no any".split())


def chunk_text(text: str, size: int = 60, overlap: int = 15) -> list:
    words = text.split()
    if len(words) <= size:
        return [" ".join(words)]
    step = size - overlap
    return [" ".join(words[i:i + size]) for i in range(0, len(words) - overlap, step)]


class HashEmbedder:
    """Bag-of-words 'hashing trick' vectors. Offline, instant, free, and DUMB: it matches words, not meaning.
    Swap for a real embedding model (Ollama /api/embed, sentence-transformers, or a hosted API) in Project 2
    and compare recall - that comparison is the lesson."""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def embed(self, text: str) -> list:
        v = [0.0] * self.dim
        for w in re.findall(r"[a-z0-9']+", text.lower()):
            if w in STOP:
                continue
            h = int(hashlib.md5(w.encode()).hexdigest(), 16)
            sign = 1.0 if (h >> 20) & 1 else -1.0  # signed hashing: collisions partly cancel instead of adding up
            v[h % self.dim] += sign
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]


class OllamaEmbedder:
    """Real embeddings from a local Ollama server (POST /api/embed). Written from the Ollama API docs; NOT run here.
    Run `ollama pull all-minilm` first (or pick another embedding model). Vectors are L2-normalised so cosine works.
    If you change the embedding model you MUST re-embed everything: vectors from different models are not comparable."""

    def __init__(self, model: str = "all-minilm", host: str = "http://localhost:11434", timeout: int = 120):
        self.model, self.host, self.timeout = model, host.rstrip("/"), timeout

    def embed(self, text: str) -> list:
        req = urllib.request.Request(self.host + "/api/embed", data=json.dumps({"model": self.model, "input": text}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            v = json.loads(r.read())["embeddings"][0]
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]


def cosine(a: list, b: list) -> float:
    return sum(x * y for x, y in zip(a, b))  # vectors are already L2-normalised


class VectorStore:
    """Tiny in-memory store. Fine up to a few thousand chunks. Beyond that, try pgvector or DuckDB."""

    def __init__(self, embedder):
        self.embedder, self.rows = embedder, []

    def add(self, doc_id: str, text: str):
        for i, ch in enumerate(chunk_text(text)):
            self.rows.append((doc_id, i, ch, self.embedder.embed(ch)))

    def search(self, query: str, k: int = 3) -> list:
        q = self.embedder.embed(query)
        scored = sorted(((cosine(q, r[3]), r[0], r[1], r[2]) for r in self.rows), reverse=True)
        return scored[:k]


def recall_at_k(store: VectorStore, qa: list, k: int = 3) -> float:
    """qa: [{'question','doc'}]. Share of questions where the right document is in the top k chunks."""
    hit = sum(1 for q in qa if q["doc"] in {r[1] for r in store.search(q["question"], k)})
    return hit / len(qa)


# =====================================================================================
# 7. Project 3: data quality monitor (statistics first, LLM only to explain)
# =====================================================================================
def detect_volume_anomalies(series: list, lo: float = 0.5, hi: float = 2.0, weeks: int = 4) -> list:
    """series: [(date_str, row_count)] oldest first. Compares each day with the median of the same weekday over the
    previous `weeks` weeks. Returns [(date, count, baseline, ratio)] for ratios below lo or above hi."""
    out = []
    for i in range(7 * weeks, len(series)):
        base = statistics.median(series[i - 7 * w][1] for w in range(1, weeks + 1))
        if base <= 0:
            continue
        ratio = series[i][1] / base
        if ratio < lo or ratio > hi:
            out.append((series[i][0], series[i][1], base, round(ratio, 2)))
    return out


def check_freshness(last_loaded: datetime, now: datetime, max_age_hours: float) -> bool:
    return (now - last_loaded) <= timedelta(hours=max_age_hours)


def build_incident_prompt(pipeline: str, anomalies: list, log_lines: list) -> str:
    rows = "\n".join(f"- {d}: {n} rows (typical {b:.0f}, ratio {r})" for d, n, b, r in anomalies)
    logs = "\n".join(log_lines[-20:])
    return (f"Pipeline: {pipeline}\nAnomalies detected by a statistical check (these are facts):\n{rows}\n\n"
            f"Last log lines:\n{logs}\n\nIn 3 bullets: what likely happened, what to check first, and who to tell. "
            "Say 'not enough evidence' if the logs do not explain it. Do not invent causes.")


def summarize_without_llm(pipeline: str, anomalies: list) -> str:
    """The free baseline. If the LLM summary is not clearly better than this, do not pay for it."""
    parts = [f"{d}: {n} rows vs typical {b:.0f} (x{r})" for d, n, b, r in anomalies]
    return f"{pipeline}: {len(anomalies)} volume anomalies. " + "; ".join(parts)


# =====================================================================================
# 8. Project 4: text-to-SQL with guardrails
# =====================================================================================
_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex|truncate|grant)\b", re.I)


class SQLRejected(ValueError):
    pass


def check_sql(sql: str) -> str:
    """Static checks. Conservative on purpose: it also rejects a harmless string literal such as 'Update'."""
    s = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    s = re.sub(r"--[^\n]*", " ", s).strip()
    s = s[:-1].strip() if s.endswith(";") else s
    if ";" in s:
        raise SQLRejected("multiple statements")
    if not re.match(r"(?is)^(select|with)\b", s):
        raise SQLRejected("only SELECT queries are allowed")
    m = _FORBIDDEN.search(s)
    if m:
        raise SQLRejected(f"forbidden keyword: {m.group(1).lower()}")
    return s


def safe_select(db_path: str, sql: str, allowed_tables=None, max_rows: int = 200, timeout_s: float = 3.0):
    """Run a model-written query with four layers: static check, read-only connection, authorizer allowlist,
    time and row limits. Returns (columns, rows, truncated). Raises SQLRejected or sqlite3 errors."""
    s = check_sql(sql)
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        con.execute("PRAGMA query_only = ON")
        allowed_actions = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
        if hasattr(sqlite3, "SQLITE_RECURSIVE"):
            allowed_actions.add(sqlite3.SQLITE_RECURSIVE)

        def authorizer(action, arg1, arg2, dbname, source):
            if action not in allowed_actions:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_READ and allowed_tables is not None and arg1 not in allowed_tables:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        con.set_authorizer(authorizer)
        deadline = time.monotonic() + timeout_s
        con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
        cur = con.execute(s)
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(max_rows + 1)
        return cols, rows[:max_rows], len(rows) > max_rows
    except sqlite3.DatabaseError as e:
        raise SQLRejected(f"database refused the query: {e}") from e
    finally:
        con.close()


def _norm_rows(rows):
    def cell(x):
        return round(x, 2) if isinstance(x, float) else x
    return sorted((tuple(cell(c) for c in r) for r in rows), key=lambda r: [str(c) for c in r])


def execution_accuracy(db_path: str, golden: list, candidates: dict, allowed_tables=None) -> dict:
    """golden: [{'id','question','sql'}]; candidates: {id: sql written by the model}.
    A candidate is correct when it returns the same rows as the reference query (column names are ignored)."""
    result = {"correct": 0, "wrong": 0, "rejected": 0, "detail": {}}
    for g in golden:
        cand = candidates.get(g["id"])
        try:
            want = _norm_rows(safe_select(db_path, g["sql"], allowed_tables, max_rows=10_000)[1])
            got = _norm_rows(safe_select(db_path, cand, allowed_tables, max_rows=10_000)[1]) if cand else None
        except SQLRejected as e:
            result["rejected"] += 1
            result["detail"][g["id"]] = f"rejected: {e}"
            continue
        ok = got == want
        result["correct" if ok else "wrong"] += 1
        result["detail"][g["id"]] = "correct" if ok else "wrong"
    result["accuracy"] = round(result["correct"] / len(golden), 3) if golden else 0.0
    return result


def build_rag_prompt(question: str, hits: list) -> str:
    """hits: output of VectorStore.search. Tags each chunk [doc#n] so the answer can cite it."""
    ctx = "\n\n".join(f"[{doc}#{i}] {text}" for _score, doc, i, text in hits)
    return ("Answer using ONLY the context below. After each claim cite the source tag, like [doc#0]. "
            "If the context does not contain the answer, reply exactly: I don't know.\n\n"
            f"Context:\n{ctx}\n\nQuestion: {question}")


def check_citations(answer: str, hits: list) -> dict:
    """Cheap guard: every cited tag must be one that was actually retrieved. It does NOT prove the claim is true."""
    allowed = {f"{doc}#{i}" for _s, doc, i, _t in hits}
    cited = set(re.findall(r"\[([A-Za-z0-9_\-]+#\d+)\]", answer))
    unknown = cited - allowed
    refused = answer.strip().rstrip(".") == "I don't know"
    return {"cited": sorted(cited), "unknown": sorted(unknown), "ok": refused or (bool(cited) and not unknown)}


# =====================================================================================
# 9. Project 5: a ledger of every model call (cost, latency, cache) and a report on it
# =====================================================================================
class LoggedLLM:
    """Wrap any backend. Every call is written to a SQLite ledger so you can answer: what did this cost, and where?"""

    def __init__(self, inner, ledger_path: str = ":memory:", project: str = "default", prompt_version: str = "v1"):
        self.inner, self.project, self.version, self.model = inner, project, prompt_version, inner.model
        self.db = sqlite3.connect(ledger_path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS calls (ts REAL, project TEXT, model TEXT, prompt_version TEXT,
                           in_tok INT, out_tok INT, cost_usd REAL, cached INT, latency_ms REAL)""")

    def complete(self, system, user, max_tokens=200):
        t0 = time.perf_counter()
        res = self.inner.complete(system, user, max_tokens)
        ms = (time.perf_counter() - t0) * 1000
        self.db.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?)",
                        (time.time(), self.project, res.model, self.version, res.input_tokens, res.output_tokens,
                         res.cost_usd, int(res.from_cache), ms))
        self.db.commit()
        return res


def ledger_report(db: sqlite3.Connection) -> list:
    """Rows of (project, model, calls, cost_usd, cache_share, avg_latency_ms)."""
    q = """SELECT project, model, COUNT(*), ROUND(SUM(cost_usd), 6), ROUND(AVG(cached), 3), ROUND(AVG(latency_ms), 3)
           FROM calls GROUP BY project, model ORDER BY SUM(cost_usd) DESC"""
    return db.execute(q).fetchall()
