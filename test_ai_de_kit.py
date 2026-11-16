"""Tests for ai_de_kit.py. Run:  python3 -m unittest test_ai_de_kit -v

These tests check the PLUMBING (caching, budgets, routing, guards, detectors). They cannot tell you how good a
real language model is. For that you need a golden set and a real model (Project 1)."""
import os
import random
import tempfile
import time
import unittest
from datetime import date
from collections import defaultdict

from ai_de_kit import (BudgetExceeded, CachedLLM, GuardedLLM, HashEmbedder, MockLLM, Router, SQLRejected, TRIAGE_SYSTEM,
                       VectorStore, build_batch_requests, check_sql, chunk_text, classification_report, cost_scenarios,
                       detect_volume_anomalies, estimate_cost, execution_accuracy, parse_json_loose, recall_at_k,
                       redact_pii, safe_select, triage, validate_ticket, build_rag_prompt, check_citations, LoggedLLM, ledger_report)
import gen_ai_data as gen

AMBIGUOUS = "Hi team, My parcel has not moved for days. Also my invoice shows a payment failed note. Thanks, Sam"
CLEAR = "Hi team, I am locked out of my account. Thanks, Sam"


class Money(unittest.TestCase):
    def test_haiku_hand_calculation(self):
        # 1000 in * $0.10/M + 100 out * $0.50/M = 0.0001 + 0.00005
        self.assertAlmostEqual(estimate_cost("claude-haiku-5-5", 1000, 100), 0.00015, places=9)

    def test_batch_is_half(self):
        a = estimate_cost("claude-sonnet-5-5", 5000, 500)
        b = estimate_cost("claude-sonnet-5-5", 5000, 500, batch=True)
        self.assertAlmostEqual(b, a / 2, places=12)

    def test_cache_read_is_cheaper_than_fresh_input(self):
        fresh = estimate_cost("claude-sonnet-5-5", 10_000, 0)
        read = estimate_cost("claude-sonnet-5-5", 0, 0, cache_read_tokens=10_000)
        self.assertAlmostEqual(read, fresh * 0.05, places=12)

    def test_cache_write_costs_more_than_fresh(self):
        self.assertGreater(estimate_cost("claude-haiku-5-5", 0, 0, cache_write_tokens=1000), estimate_cost("claude-haiku-5-5", 1000, 0))

    def test_scenarios_order(self):
        s = dict(cost_scenarios())
        names = list(s)
        self.assertGreater(s[names[0]], s[names[1]])      # Sonnet > Haiku
        self.assertGreater(s[names[1]], s[names[2]])      # standard > batch
        self.assertGreater(s[names[2]], s[names[3]])      # batch > batch + cache
        self.assertLess(s[names[4]], s[names[5]])         # routed < Sonnet batch + cache
        self.assertGreater(s[names[4]], s[names[3]])      # routing costs more than Haiku alone

    def test_local_model_has_no_api_cost(self):
        self.assertEqual(estimate_cost("llama3.2", 10_000, 1000), 0.0)

    def test_batch_request_shape(self):
        reqs = build_batch_requests({"t1": "hello"}, "claude-haiku-5-5", "sys")
        self.assertEqual(reqs[0]["custom_id"], "t1")
        self.assertEqual(reqs[0]["params"]["messages"][0]["content"], "hello")


class Wrappers(unittest.TestCase):
    def test_cache_hit_is_free_and_skips_the_model(self):
        inner = MockLLM("strong")
        c = CachedLLM(inner)
        r1 = c.complete(TRIAGE_SYSTEM, CLEAR)
        r2 = c.complete(TRIAGE_SYSTEM, CLEAR)
        self.assertFalse(r1.from_cache)
        self.assertTrue(r2.from_cache)
        self.assertEqual(r2.cost_usd, 0.0)
        self.assertEqual(inner.calls, 1)
        self.assertEqual((c.hits, c.misses), (1, 1))

    def test_prompt_version_invalidates_cache(self):
        inner = MockLLM("strong")
        c1 = CachedLLM(inner, prompt_version="v1")
        c1.complete(TRIAGE_SYSTEM, CLEAR)
        c2 = CachedLLM(inner, path=":memory:", prompt_version="v2")
        c2.complete(TRIAGE_SYSTEM, CLEAR)
        self.assertEqual(inner.calls, 2)

    def test_budget_guard_stops_spending(self):
        g = GuardedLLM(MockLLM("strong"), limit_usd=0.0001)
        with self.assertRaises(BudgetExceeded):
            for i in range(1000):
                g.complete(TRIAGE_SYSTEM, CLEAR + str(i))
        self.assertGreaterEqual(g.spent, 0.0001)
        self.assertLess(g.spent, 0.01)  # it stopped long before 1000 calls were paid for

    def test_router_escalates_only_when_unsure(self):
        r = Router(MockLLM("cheap"), MockLLM("strong"), 0.8)
        obj, results = r.route(TRIAGE_SYSTEM, CLEAR)
        self.assertEqual(len(results), 1)
        self.assertEqual(obj["category"], "account_access")
        obj, results = r.route(TRIAGE_SYSTEM, AMBIGUOUS)
        self.assertEqual(len(results), 2)                     # cheap was unsure, strong was asked
        self.assertEqual(obj["category"], "shipping")         # the first-named problem
        self.assertEqual(dict(r.stats), {"cheap_only": 1, "escalated": 1})

    def test_mock_is_deterministic(self):
        a = MockLLM("cheap").complete(TRIAGE_SYSTEM, AMBIGUOUS).text
        b = MockLLM("cheap").complete(TRIAGE_SYSTEM, AMBIGUOUS).text
        self.assertEqual(a, b)


class Parsing(unittest.TestCase):
    def test_parse_json_loose(self):
        self.assertEqual(parse_json_loose('{"a": 1}'), {"a": 1})
        self.assertEqual(parse_json_loose('Sure! Here you go:\n```json\n{"a": 2}\n```'), {"a": 2})
        self.assertIsNone(parse_json_loose("no json here"))
        self.assertIsNone(parse_json_loose(None))

    def test_validate_ticket(self):
        good = {"category": "billing", "priority": "low", "refund_requested": False, "confidence": 0.9}
        self.assertEqual(validate_ticket(good), [])
        self.assertTrue(validate_ticket({**good, "category": "banana"}))
        self.assertTrue(validate_ticket({**good, "refund_requested": "yes"}))
        self.assertTrue(validate_ticket({**good, "confidence": 1.5}))
        self.assertTrue(validate_ticket({**good, "confidence": True}))
        self.assertTrue(validate_ticket("text"))

    def test_redaction(self):
        t, n = redact_pii("Call 0491 570 006 or +61 491 570 006, mail a.b@example.com, card 4111 1111 1111 1111.")
        self.assertEqual(n, {"EMAIL": 1, "CARD": 1, "PHONE": 2})
        self.assertNotIn("570", t)
        self.assertNotIn("@", t)
        self.assertEqual(redact_pii("Order 12345 arrived")[1], {"EMAIL": 0, "CARD": 0, "PHONE": 0})


class Triage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tickets = gen.make_tickets(random.Random(7), 600)
        cls.truth = {t["id"]: t["true_category"] for t in cls.tickets}

    def run_variant(self, cheap, strong, thr):
        router = Router(cheap, strong, thr)
        out = triage(self.tickets, router)
        pred = [(out["preds"][t["id"]] or {}).get("category") for t in self.tickets]
        acc = classification_report([self.truth[t["id"]] for t in self.tickets], pred)["accuracy"]
        return acc, out

    def test_dedup_before_calling(self):
        tickets = [{"id": str(i), "text": "My parcel has not moved for days."} for i in range(3)] + [{"id": "x", "text": CLEAR}]
        r = Router(MockLLM("cheap"), MockLLM("strong"))
        out = triage(tickets, r)
        self.assertEqual(out["unique_texts"], 2)
        self.assertEqual(out["model_calls"], 2)

    def test_routing_beats_cheap_on_accuracy_and_strong_on_cost(self):
        c = MockLLM("cheap")
        s = MockLLM("strong")
        acc_cheap, out_cheap = self.run_variant(c, c, 0.0)
        acc_strong, out_strong = self.run_variant(s, s, 0.0)
        acc_route, out_route = self.run_variant(MockLLM("cheap"), MockLLM("strong"), 0.8)
        self.assertGreater(acc_route, acc_cheap + 0.05)
        self.assertLess(out_route["cost_usd"], out_strong["cost_usd"] / 3)
        self.assertGreaterEqual(acc_strong, acc_route)         # routing is not free of accuracy cost

    def test_pii_never_reaches_the_model(self):
        seen = []

        class Spy(MockLLM):
            def complete(self, system, user, max_tokens=200):
                seen.append(user)
                return super().complete(system, user, max_tokens)
        triage(self.tickets[:200], Router(Spy("cheap"), Spy("strong")))
        joined = " ".join(seen)
        self.assertNotIn("@example.com", joined)
        self.assertNotIn("0491", joined)
        self.assertIn("[EMAIL]", joined)

    def test_report_math(self):
        rep = classification_report(["a", "a", "b", "b"], ["a", "b", "b", "b"])
        self.assertEqual(rep["accuracy"], 0.75)
        self.assertEqual(rep["a"], {"precision": 1.0, "recall": 0.5, "support": 2})
        self.assertAlmostEqual(rep["b"]["precision"], 0.667, places=3)


class Retrieval(unittest.TestCase):
    def setUp(self):
        self.store = VectorStore(HashEmbedder())
        for name, body in gen.POLICIES.items():
            self.store.add(name, body)
        self.qa = [{"question": q, "doc": d, "hard": h} for q, d, h in gen.QA]

    def test_easy_questions_are_found(self):
        easy = [q for q in self.qa if not q["hard"]]
        self.assertGreaterEqual(recall_at_k(self.store, easy, 3), 0.9)

    def test_word_matching_is_weaker_on_paraphrases(self):
        easy = [q for q in self.qa if not q["hard"]]
        hard = [q for q in self.qa if q["hard"]]
        self.assertLess(recall_at_k(self.store, hard, 3), recall_at_k(self.store, easy, 3))

    def test_chunking(self):
        words = " ".join(f"w{i}" for i in range(200))
        chunks = chunk_text(words, size=60, overlap=15)
        self.assertTrue(all(len(c.split()) <= 60 for c in chunks))
        self.assertEqual(chunks[1].split()[0], "w45")          # overlap of 15 words
        self.assertIn("w199", chunks[-1])
        self.assertEqual(chunk_text("short text"), ["short text"])


class Quality(unittest.TestCase):
    def test_planted_anomalies_found_without_false_alarms(self):
        rows, truth = gen.make_metrics(random.Random(7), date(2026, 7, 1))
        series = defaultdict(list)
        for p, d, n in rows:
            series[p].append((d, n))
        found = {(p, d) for p, s in series.items() for d, *_ in detect_volume_anomalies(s)}
        want = {(t["pipeline"], t["date"]) for t in truth}
        self.assertEqual(found, want)

    def test_weekend_dip_is_not_an_anomaly(self):
        s = [(f"d{i}", 600 if i % 7 in (5, 6) else 1000) for i in range(60)]
        self.assertEqual(detect_volume_anomalies(s), [])


class SQLGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = os.path.join(cls.tmp.name, "retail.db")
        gen.make_retail(cls.db, random.Random(7))
        cls.allowed = {"customers", "products", "orders", "order_items"}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_valid_select_runs(self):
        cols, rows, trunc = safe_select(self.db, "SELECT COUNT(*) FROM orders", self.allowed)
        self.assertEqual(rows[0][0], 1500)
        self.assertFalse(trunc)

    def test_attacks_are_rejected(self):
        attacks = ["DELETE FROM orders", "DROP TABLE orders", "SELECT 1; DROP TABLE orders", "UPDATE orders SET status='paid'",
                   "INSERT INTO orders VALUES (9999,1,'2026-01-01','paid')", "PRAGMA writable_schema=1",
                   "ATTACH DATABASE '/tmp/x.db' AS x", "WITH x AS (SELECT 1) DELETE FROM orders", "SELECT 1 /* hi */; DROP TABLE orders"]
        for sql in attacks:
            with self.assertRaises(SQLRejected, msg=sql):
                safe_select(self.db, sql, self.allowed)
        self.assertEqual(safe_select(self.db, "SELECT COUNT(*) FROM orders", self.allowed)[1][0][0], 1500)  # still there

    def test_allowlist_blocks_sensitive_table(self):
        with self.assertRaises(SQLRejected):
            safe_select(self.db, "SELECT * FROM staff_notes", self.allowed)
        self.assertEqual(len(safe_select(self.db, "SELECT * FROM staff_notes", None)[1]), 1)  # allowed only when no allowlist

    def test_comment_trick_is_stripped_not_executed(self):
        self.assertEqual(check_sql("SELECT 1 -- ; DROP TABLE orders"), "SELECT 1")

    def test_row_limit(self):
        _, rows, trunc = safe_select(self.db, "SELECT * FROM order_items", self.allowed, max_rows=10)
        self.assertEqual(len(rows), 10)
        self.assertTrue(trunc)

    def test_runaway_query_is_stopped(self):
        t0 = time.monotonic()
        with self.assertRaises(SQLRejected):
            safe_select(self.db, "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT COUNT(*) FROM c",
                        self.allowed, timeout_s=0.5)
        self.assertLess(time.monotonic() - t0, 5)

    def test_execution_accuracy_scoring(self):
        golden = [{"id": g[0], "question": g[1], "sql": g[2]} for g in gen.GOLDEN]
        cand = {g["id"]: g["sql"] for g in golden}
        cand["q1"] = "SELECT state, COUNT(customer_id) AS n FROM customers GROUP BY 1"   # same rows, different SQL: correct
        cand["q4"] = "SELECT COUNT(*) FROM orders WHERE status <> 'paid'"               # plausible but wrong
        cand["q5"] = "SELECT * FROM staff_notes"                                         # blocked
        cand["q8"] = "SELECT name FROM customers; DROP TABLE orders"                     # blocked
        res = execution_accuracy(self.db, golden, cand, self.allowed)
        self.assertEqual((res["correct"], res["wrong"], res["rejected"]), (5, 1, 2))
        self.assertEqual(res["detail"]["q1"], "correct")
        self.assertEqual(res["detail"]["q4"], "wrong")

    def test_golden_queries_all_run_and_return_rows(self):
        for q, _, sql in gen.GOLDEN:
            self.assertTrue(safe_select(self.db, sql, self.allowed, max_rows=10_000)[1], q)


class RagGuards(unittest.TestCase):
    def setUp(self):
        self.store = VectorStore(HashEmbedder())
        for name, body in gen.POLICIES.items():
            self.store.add(name, body)

    def test_prompt_contains_tagged_context_and_refusal_rule(self):
        hits = self.store.search("How many days do I have to return an item?", 2)
        p = build_rag_prompt("How many days do I have to return an item?", hits)
        self.assertIn("[returns_policy#0]", p)
        self.assertIn("I don't know", p)

    def test_citation_check(self):
        hits = self.store.search("How many days do I have to return an item?", 2)
        good = "You have 30 days [returns_policy#0]."
        fake = "You have 90 days [made_up_doc#3]."
        none = "You have 30 days."
        self.assertTrue(check_citations(good, hits)["ok"])
        self.assertFalse(check_citations(fake, hits)["ok"])
        self.assertEqual(check_citations(fake, hits)["unknown"], ["made_up_doc#3"])
        self.assertFalse(check_citations(none, hits)["ok"])
        self.assertTrue(check_citations("I don't know.", hits)["ok"])


class Ledger(unittest.TestCase):
    def test_ledger_totals_match_results(self):
        llm = LoggedLLM(CachedLLM(MockLLM("strong")), project="p1")
        total = 0.0
        for i in range(5):
            total += llm.complete(TRIAGE_SYSTEM, CLEAR + str(i)).cost_usd
        llm.complete(TRIAGE_SYSTEM, CLEAR + "0")                       # repeated: cache hit, free
        rows = ledger_report(llm.db)
        self.assertEqual(len(rows), 1)
        project, model, calls, cost, cache_share, _ = rows[0]
        self.assertEqual((project, model, calls), ("p1", "mock-strong", 6))
        self.assertAlmostEqual(cost, total, places=6)
        self.assertAlmostEqual(cache_share, round(1 / 6, 3), places=3)


if __name__ == "__main__":
    unittest.main()
