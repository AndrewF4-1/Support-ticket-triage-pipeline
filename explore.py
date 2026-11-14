import json
from collections import Counter
def load_jsonl_file(file_path):
    ticket= []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            ticket.append(json.loads(line.strip()))
    return ticket
first_test = load_jsonl_file("C:/Users/nguye/OneDrive/projects/Project 1/data/tickets.jsonl")

def count_categoreie(tickets):
    category = [tickets['true_category'] for tickets in tickets ]
    return Counter(category)
classified_tickets = count_categoreie(first_test)

def order_dict(ticket):

    by_length = sorted(first_test, key=lambda t: len(t['text']),reverse=True)  

    return f'The longest tickets are:\n "{by_length[:5]}\n\n The shortest tickets are:\n {by_length[-5:]}'
print(order_dict(first_test)) 
