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
cur.execute("CREATE TABLE IF NOT EXISTS tickets(id interger primary key, text varchar(150), true_category varchar(150), true_priority varchar (30), true_refund interger)")
res = cur.execute('SELECT * FROM sqlite_master')
for ticket in load_jsonl_file("C:/ticket-triage/data/tickets.jsonl"):
    cur.execute("""
    INSERT OR REPLACE INTO tickets
    (id, text, true_category, true_priority, true_refund)
    VALUES (?, ?, ?, ?, ?)
""", (ticket["id"], ticket["text"], ticket["true_category"],
      ticket["true_priority"], int(ticket["true_refund"])))
con.commit()
a = cur.execute("SELECT * FROM tickets").fetchall()
b = cur.execute('SELECT COUNT(*) FROM tickets')
print(b.fetchall())