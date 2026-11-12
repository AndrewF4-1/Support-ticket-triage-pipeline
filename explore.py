import json
from collections import Counter
def load_jsonl_file(file_path):
    ticket= []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            ticket.append(json.loads(line.strip()))
    return ticket
first_test = load_jsonl_file("C:/Users/nguye/OneDrive/projects/Project 1/data/tickets.jsonl")

def classify_tickets(tickets):
    ticket = [ticket['true_category'] for ticket in tickets]
    return Counter(ticket)
classified_tickets = classify_tickets(first_test)
print(classified_tickets)