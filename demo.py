#!/usr/bin/env python3
"""demo.py - one command that exercises the plumbing of all five projects with the MOCK models.

    python3 gen_ai_data.py && python3 demo.py

Numbers printed for the triage experiment describe the MOCK models only. Replace MockLLM with a real model
(OllamaLLM or AnthropicLLM), keep everything else, and compare. That comparison is Project 1.
"""
import csv
import json
import os
import sys
from collections import defaultdict

from ai_de_kit import (CachedLLM, GuardedLLM, MockLLM, Router, TRIAGE_SYSTEM, classification_report, cost_scenarios,
                       detect_volume_anomalies, parse_json_loose, recall_at_k, safe_select, triage, VectorStore,
                       HashEmbedder, execution_accuracy, SQLRejected, redact_pii)

D = sys.argv[1] if len(sys.argv) > 1 else "data"


def load_tickets():
    return [json.loads(l) for l in open(os.path.join(D, "tickets.jsonl"))]


def p1():
    print("\n=== Project 1: ticket triage (MOCK models) ===")
    tickets = load_tickets()
    truth = {t["id"]: t["true_category"] for t in tickets}
    results = {}
    for name in ("cheap only", "strong only", "routed (threshold 0.8)"):
        cheap, strong = MockLLM("cheap"), MockLLM("strong")
        if name == "cheap only":
            router = Router(cheap, cheap, threshold=0.0)
        elif name == "strong only":
            router = Router(strong, strong, threshold=0.0)
        else:
            router = Router(cheap, strong, 0.8)
        out = triage(tickets, router)
        y_true = [truth[t["id"]] for t in tickets]
        y_pred = [(out["preds"][t["id"]] or {}).get("category", "FAILED") for t in tickets]
        acc = classification_report(y_true, y_pred)["accuracy"]
        results[name] = (acc, out["cost_usd"], out["model_calls"], out["unique_texts"], dict(router.stats))
        print(f"{name:26s} accuracy={acc:.3f}  simulated cost=${out['cost_usd']:.5f}  model calls={out['model_calls']}  "
              f"unique texts={out['unique_texts']}/{out['tickets']}  router={dict(router.stats)}")
    return results


def p2():
    print("\n=== Project 2: retrieval with hashing embeddings (offline stand-in) ===")
    store = VectorStore(HashEmbedder())
    for f in sorted(os.listdir(os.path.join(D, "policies"))):
        store.add(f[:-3], open(os.path.join(D, "policies", f)).read())
    qa = json.load(open(os.path.join(D, "qa_pairs.json")))
    easy = [q for q in qa if not q["hard"]]
    hard = [q for q in qa if q["hard"]]
    r = (recall_at_k(store, easy, 3), recall_at_k(store, hard, 3), recall_at_k(store, easy, 1), recall_at_k(store, hard, 1))
    print(f"recall@3 easy={r[0]:.2f} (n={len(easy)})  hard={r[1]:.2f} (n={len(hard)})   recall@1 easy={r[2]:.2f} hard={r[3]:.2f}")
    return r


def p3():
    print("\n=== Project 3: volume anomaly detection ===")
    series = defaultdict(list)
    for row in csv.DictReader(open(os.path.join(D, "pipeline_metrics.csv"))):
        series[row["pipeline"]].append((row["date"], int(row["rows_loaded"])))
    truth = {(t["pipeline"], t["date"]) for t in json.load(open(os.path.join(D, "anomalies_truth.json")))}
    found = set()
    for name, s in series.items():
        for d, n, b, r in detect_volume_anomalies(s):
            found.add((name, d))
            print(f"  flagged {name} {d}: {n} rows, typical {b:.0f}, ratio {r}")
    print(f"planted={len(truth)} found={len(found & truth)} false alarms={len(found - truth)}")
    return truth, found


def p4():
    print("\n=== Project 4: text-to-SQL guardrails ===")
    db = os.path.join(D, "retail.db")
    golden = json.load(open(os.path.join(D, "golden_sql.json")))
    allowed = {"customers", "products", "orders", "order_items"}
    # pretend these came from a model: some right, some wrong, some dangerous
    cand = {g["id"]: g["sql"] for g in golden}
    cand["q1"] = "SELECT state, COUNT(customer_id) AS n FROM customers GROUP BY 1"
    cand["q4"] = "SELECT COUNT(*) FROM orders WHERE status <> 'paid'"                       # wrong: includes cancelled
    cand["q5"] = "SELECT * FROM staff_notes"                                                 # outside the allowlist
    cand["q8"] = "SELECT name FROM customers; DROP TABLE orders"                             # two statements
    res = execution_accuracy(db, golden, cand, allowed)
    print(res)
    for sql in ["DELETE FROM orders", "SELECT * FROM staff_notes", "WITH x AS (SELECT 1) UPDATE orders SET status='paid'"]:
        try:
            safe_select(db, sql, allowed)
            print("  NOT BLOCKED:", sql)
        except SQLRejected as e:
            print(f"  blocked: {sql[:50]!r} -> {e}")
    return res


def p5():
    print("\n=== Project 5: what 100,000 tickets a month could cost (assumptions in the PDF) ===")
    rows = cost_scenarios()
    for name, usd in rows:
        print(f"  {name:75s} ${usd:10.2f}")
    return rows


if __name__ == "__main__":
    p1(); p2(); p3(); p4(); p5()
    print("\nredaction example:", redact_pii("Call me on 0491 570 006 or alex@example.com, card 4111 1111 1111 1111"))
