#!/usr/bin/env python3
"""gen_ai_data.py - makes ALL the fake data for the five AI x data engineering projects.

Everything is synthetic. Names are invented, emails use example.com, and phone numbers are from the
fictional ranges reserved for TV and film use in Australia. Standard library only.

    python3 gen_ai_data.py                  # writes ./data/
    python3 gen_ai_data.py --seed 11 --out data11 --tickets 2000

Files written
    tickets.jsonl           id, text, true_category, true_priority, true_refund      (Project 1)
    policies/*.md           eight short policy documents                              (Project 2)
    qa_pairs.json           questions with the document that answers each; 'hard' flag (Project 2)
    pipeline_metrics.csv    daily row counts for three pipelines                      (Project 3)
    anomalies_truth.json    the problems that were planted                            (Project 3)
    retail.db               customers, products, orders, order_items, staff_notes     (Project 4)
    golden_sql.json         eight questions with reference SQL                        (Project 4)

Do not open the *_truth.json files or golden_sql.json until you have tried the work.
"""
import argparse
import csv
import json
import os
import random
import sqlite3
from datetime import date, timedelta

from ai_de_kit import keyword_hits

# ----------------------------------------------------------------------------- tickets
PRIMARY = {  # each sentence below contains exactly ONE keyword hit for its own category
    "billing": ["I was charged twice for my order this week.", "The invoice I received does not match what I paid.",
                "There is an overcharged amount on my statement.", "My receipt is missing and I need a copy."],
    "shipping": ["My parcel has not moved for days.", "The courier says it was left but nothing is here.",
                 "The delivery has not shown up yet.", "Tracking has not updated since Monday."],
    "returns": ["I would like to send it back.", "Can I do an exchange for a smaller one?",
                "It is the wrong size for me.", "Please explain how to start a return."],
    "product_fault": ["The blender stopped working after two days.", "The screen arrived cracked.",
                      "The kettle is faulty.", "It is defective out of the box."],
    "account_access": ["I am locked out of my account.", "The reset link never arrives.",
                       "My password is rejected.", "The verification code does not come through."],
    "other": ["Do you have a store in Melbourne?", "Can I change the name on my loyalty card?",
              "What are your opening hours at Christmas?", "Do you sell gift wrapping?"],
}
SECONDARY = {  # each contains TWO or more keyword hits for a different category
    "billing": "Also my invoice shows a payment failed note.",
    "shipping": "Also the courier left a delivery card with no tracking number.",
    "returns": "Also I may need a return label for an exchange.",
    "product_fault": "Also the lid is cracked and looks defective.",
    "account_access": "Also my password reset link and verification code failed.",
}
HIGH = ["This is urgent, please help immediately.", "This is the second time I am writing.", "I will file a chargeback if this continues."]
MEDIUM = ["I am still waiting for a reply.", "I have had no reply so far."]
REFUND = ["I would like my money back.", "Please refund me."]
NAMES = ["Alex", "Sam", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Jamie", "Chris", "Dana"]
FAKE_PHONES = ["0491 570 006", "0491 570 156", "0491 570 157", "0491 570 158", "0491 570 159", "0491 570 110"]


def make_tickets(rng, n):
    out, seen = [], []
    for i in range(n):
        if seen and rng.random() < 0.08:  # exact re-sends: forwarded duplicates, double submissions
            out.append({**rng.choice(seen), "id": f"T{i + 1:05d}"})
            continue
        cat = rng.choices(list(PRIMARY), weights=[22, 22, 16, 14, 14, 12])[0]
        primary = rng.choice(PRIMARY[cat])
        # blended tickets: primary sentence has one hit, a second problem has more hits
        if cat != "other" and rng.random() < 0.15:
            others = [c for c in SECONDARY if c != cat]
            body = [primary, SECONDARY[rng.choice(others)]]
        else:
            body = [primary]
        pr = rng.choices(["low", "medium", "high"], weights=[60, 25, 15])[0]
        if pr == "high":
            body.append(rng.choice(HIGH))
        elif pr == "medium":
            body.append(rng.choice(MEDIUM))
        refund = rng.random() < 0.3 and cat != "other"
        if refund:
            body.append(rng.choice(REFUND))
        name = rng.choice(NAMES)
        if rng.random() < 0.35:
            body.append(f"You can reach me on {rng.choice(FAKE_PHONES)} or {name.lower()}{rng.randint(1, 99)}@example.com.")
        text = f"Hi team, {' '.join(body)} Thanks, {name}"
        rec = {"id": f"T{i + 1:05d}", "text": text, "true_category": cat, "true_priority": pr, "true_refund": refund}
        out.append(rec)
        seen.append(rec)
    # self-check: primary sentences really do have exactly one hit
    for cat, sents in PRIMARY.items():
        for s in sents:
            h = keyword_hits(s)
            assert (cat == "other" and sum(h.values()) == 0) or (h.get(cat, 0) == 1 and sum(h.values()) == 1), (cat, s, h)
    return out


# ----------------------------------------------------------------------------- policies and QA
POLICIES = {
    "returns_policy": "You can return most items within 30 days of delivery. Items must be unused and in original packaging. To start a return, open your order page and choose Return item. We email a prepaid return label within one business day. Sale items marked final sale cannot be returned. Exchanges for a different size are free.",
    "shipping_times": "Standard shipping takes 3 to 7 business days within Australia. Express shipping takes 1 to 3 business days and costs 12 dollars. Orders placed before 2pm on a business day ship the same day. Tracking numbers are emailed once the parcel leaves our warehouse. Remote areas can take up to 10 business days.",
    "refund_timing": "Approved refunds are paid to the original payment method within 5 to 10 business days after we receive the returned item. Refunds for cancelled orders are processed within 3 business days. We do not refund shipping fees unless the item arrived faulty. Store credit refunds are instant.",
    "account_security": "To reset your password choose Forgot password on the login page and we send a reset link valid for 30 minutes. After five failed sign in attempts your account is locked for 15 minutes. Turn on two step verification in Account settings to receive a verification code by SMS or an authenticator app. Never share your verification code with anyone, including our staff.",
    "warranty": "All electrical products carry a 12 month warranty against manufacturing faults. Under Australian Consumer Law you may also be entitled to a remedy for major failures regardless of the warranty period. To claim, send a photo of the fault and your order number to the support team. We repair, replace or refund faulty products.",
    "privacy": "We collect your name, email, delivery address and order history to fulfil orders and provide support. We do not sell personal information. You can ask for a copy of your data or ask us to delete your account by emailing the privacy team. Support tickets are kept for 24 months. If a data breach is likely to cause serious harm we notify affected customers and the OAIC.",
    "gift_cards": "Gift cards are delivered by email within 10 minutes of purchase. They never expire and can be used on any product, but not to buy other gift cards. A lost card can be replaced if you can provide the purchase email. Gift cards cannot be refunded for cash.",
    "store_hours": "Our Sydney store is open 9am to 6pm Monday to Saturday and 10am to 4pm on Sunday. On public holidays the store closes at 3pm and is closed on Christmas Day. Click and collect orders are ready within two hours during opening times. Bring photo identification and your order number to collect.",
}
QA = [
    ("How many days do I have to return an item?", "returns_policy", 0), ("Do I get a prepaid return label?", "returns_policy", 0),
    ("Can I return a sale item?", "returns_policy", 0), ("How long does express shipping take?", "shipping_times", 0),
    ("What is the cut off time for same day dispatch?", "shipping_times", 0), ("When do I get a tracking number?", "shipping_times", 0),
    ("How long until my refund is paid?", "refund_timing", 0), ("Do you refund the shipping fee?", "refund_timing", 0),
    ("How fast are refunds for cancelled orders?", "refund_timing", 0), ("How do I reset my password?", "account_security", 0),
    ("How many failed attempts before my account is locked?", "account_security", 0), ("Where do I get a verification code?", "account_security", 0),
    ("How long is the warranty on electrical products?", "warranty", 0), ("How do I make a warranty claim?", "warranty", 0),
    ("What remedy applies for faulty products?", "warranty", 0), ("How long do you keep support tickets?", "privacy", 0),
    ("Can I ask you to delete my account?", "privacy", 0), ("Do you sell my personal information?", "privacy", 0),
    ("Do gift cards expire?", "gift_cards", 0), ("Can I get cash back for a gift card?", "gift_cards", 0),
    ("How quickly is a gift card delivered?", "gift_cards", 0), ("What are the Sunday opening hours?", "store_hours", 0),
    ("Is the store open on Christmas Day?", "store_hours", 0), ("What do I need to bring for click and collect?", "store_hours", 0),
    # hard: almost no words in common with the answer, so word-matching struggles and real embeddings should help
    ("Is there an extra fee if I want something quicker?", "shipping_times", 1),
    ("Someone I do not know got hold of my details, what happens?", "privacy", 1),
    ("I forgot how to get back into my profile", "account_security", 1),
    ("Can I swap it for something that fits better?", "returns_policy", 1),
    ("The gadget died within a few months, who fixes it?", "warranty", 1),
    ("Could I drop by on a Sunday afternoon?", "store_hours", 1),
]


# ----------------------------------------------------------------------------- metrics
def make_metrics(rng, start, days=90):
    base = {"orders_load": 10_000, "tickets_load": 2_500, "web_events": 80_000}
    planted = [("orders_load", 55, 0.15, "partial load"), ("tickets_load", 70, 0.0, "missing load"),
               ("web_events", 80, 3.2, "duplicate load")]
    rows, truth = [], []
    for name, b in base.items():
        for d in range(days):
            day = start + timedelta(days=d)
            f = 0.6 if day.weekday() >= 5 else 1.0
            n = int(b * f * rng.uniform(0.92, 1.08))
            for pn, pd, mult, kind in planted:
                if pn == name and pd == d:
                    n = int(n * mult)
                    truth.append({"pipeline": name, "date": day.isoformat(), "kind": kind})
            rows.append((name, day.isoformat(), n))
    return rows, truth


# ----------------------------------------------------------------------------- retail db
def make_retail(path, rng):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT, state TEXT, joined_date TEXT);
        CREATE TABLE products (product_id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL);
        CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INT, order_date TEXT, status TEXT);
        CREATE TABLE order_items (order_id INT, product_id INT, qty INT);
        CREATE TABLE staff_notes (note_id INTEGER PRIMARY KEY, staff TEXT, note TEXT);
    """)
    states = ["NSW", "VIC", "QLD", "WA", "SA", "TAS"]
    cats = ["Kitchen", "Audio", "Garden", "Fitness", "Office"]
    for i in range(1, 201):
        con.execute("INSERT INTO customers VALUES (?,?,?,?)",
                    (i, f"Customer {i:03d}", rng.choices(states, weights=[34, 26, 20, 10, 7, 3])[0],
                     (date(2025, 1, 1) + timedelta(days=rng.randint(0, 600))).isoformat()))
    for i in range(1, 41):
        con.execute("INSERT INTO products VALUES (?,?,?,?)", (i, f"Product {i:02d}", cats[i % 5], round(rng.uniform(9, 240), 2)))
    for oid in range(1, 1501):
        cust = rng.randint(1, 170)  # customers 171-200 never order
        d = date(2026, 8, 1) + timedelta(days=rng.randint(0, 70))
        status = rng.choices(["paid", "refunded", "cancelled"], weights=[85, 8, 7])[0]
        con.execute("INSERT INTO orders VALUES (?,?,?,?)", (oid, cust, d.isoformat(), status))
        for pid in rng.sample(range(1, 41), rng.randint(1, 4)):
            con.execute("INSERT INTO order_items VALUES (?,?,?)", (oid, pid, rng.randint(1, 3)))
    con.execute("INSERT INTO staff_notes VALUES (1,'finance','Pretend this is sensitive: salary review notes')")
    con.commit()
    con.close()


GOLDEN = [
    ("q1", "How many customers are in each state?", "SELECT state, COUNT(*) FROM customers GROUP BY state"),
    ("q2", "What was total revenue from paid orders in September 2026?",
     "SELECT ROUND(SUM(oi.qty * p.price), 2) FROM orders o JOIN order_items oi ON oi.order_id = o.order_id JOIN products p ON p.product_id = oi.product_id WHERE o.status = 'paid' AND o.order_date BETWEEN '2026-09-01' AND '2026-09-30'"),
    ("q3", "Which 5 products sold the most units in paid orders?",
     "SELECT p.name, SUM(oi.qty) AS units FROM orders o JOIN order_items oi ON oi.order_id = o.order_id JOIN products p ON p.product_id = oi.product_id WHERE o.status = 'paid' GROUP BY p.name ORDER BY units DESC, p.name LIMIT 5"),
    ("q4", "How many orders were refunded?", "SELECT COUNT(*) FROM orders WHERE status = 'refunded'"),
    ("q5", "Which customers placed more than 10 orders?",
     "SELECT c.name, COUNT(*) AS n FROM customers c JOIN orders o ON o.customer_id = c.customer_id GROUP BY c.name HAVING COUNT(*) > 10"),
    ("q6", "What is the average value of a paid order?",
     "SELECT ROUND(AVG(t), 2) FROM (SELECT SUM(oi.qty * p.price) AS t FROM orders o JOIN order_items oi ON oi.order_id = o.order_id JOIN products p ON p.product_id = oi.product_id WHERE o.status = 'paid' GROUP BY o.order_id)"),
    ("q7", "What is the paid revenue for each product category?",
     "SELECT p.category, ROUND(SUM(oi.qty * p.price), 2) FROM orders o JOIN order_items oi ON oi.order_id = o.order_id JOIN products p ON p.product_id = oi.product_id WHERE o.status = 'paid' GROUP BY p.category"),
    ("q8", "Which customers have never placed an order?",
     "SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id = c.customer_id WHERE o.order_id IS NULL"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="data")
    ap.add_argument("--tickets", type=int, default=600)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    os.makedirs(os.path.join(a.out, "policies"), exist_ok=True)

    with open(os.path.join(a.out, "tickets.jsonl"), "w") as f:
        for t in make_tickets(rng, a.tickets):
            f.write(json.dumps(t) + "\n")
    for name, body in POLICIES.items():
        with open(os.path.join(a.out, "policies", f"{name}.md"), "w") as f:
            f.write(f"# {name.replace('_', ' ').title()}\n\n{body}\n")
    json.dump([{"question": q, "doc": d, "hard": h} for q, d, h in QA], open(os.path.join(a.out, "qa_pairs.json"), "w"), indent=1)
    rows, truth = make_metrics(rng, date(2026, 7, 1))
    with open(os.path.join(a.out, "pipeline_metrics.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["pipeline", "date", "rows_loaded"])
        w.writerows(rows)
    json.dump(truth, open(os.path.join(a.out, "anomalies_truth.json"), "w"), indent=1)
    make_retail(os.path.join(a.out, "retail.db"), rng)
    json.dump([{"id": i, "question": q, "sql": s} for i, q, s in GOLDEN], open(os.path.join(a.out, "golden_sql.json"), "w"), indent=1)
    print(f"wrote data to {a.out}/ (tickets={a.tickets}, seed={a.seed})")


if __name__ == "__main__":
    main()
