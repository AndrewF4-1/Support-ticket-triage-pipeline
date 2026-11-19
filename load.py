import json
import sqlite3

def load_jsonl_file(file_path):
    ticket= []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            ticket.append(json.loads(line.strip()))
    return ticket


con = sqlite3.connect("C:/ticket-triage/data/tickets.db")
cur = con.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS tickets(id text primary key, text text, true_category text, true_priority text, true_refund integer)")
for ticket in load_jsonl_file("C:/ticket-triage/data/tickets.jsonl"):
    cur.execute("""
    INSERT OR REPLACE INTO tickets
    (id, text, true_category, true_priority, true_refund)
    VALUES (?, ?, ?, ?, ?)
""", (ticket["id"], ticket["text"], ticket["true_category"],
      ticket["true_priority"], int(ticket["true_refund"])))

a = cur.execute("SELECT * FROM tickets").fetchall()
b = cur.execute('SELECT COUNT(*) FROM tickets GROUP BY true_category')
con.commit()
print(a)
print(b.fetchall())

con.close()
