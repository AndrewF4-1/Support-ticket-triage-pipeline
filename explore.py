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

def order_dict(tickets):

    by_length = sorted(tickets, key=lambda t: len(t['text']))  
    
    for longest_text in by_length[-5:]:
         print(f'longest ticket: {longest_text}, {len(longest_text["text"])}')
    print("\n\n\n\n")
    for shortest_ticket in by_length[:5]:
        print(f'shortest text: {shortest_ticket}, {len(shortest_ticket["text"])}')
    return None
    # return f'The longest tickets are:\n "{by_length[:5]},{len(by_length['text'])}\n\n The shortest tickets are:\n {by_length[-5:]}'

print(order_dict(first_test))

def duplicate_tickers(tickets):
    texts = []
    for ticket in tickets:
        texts.append(ticket["text"])
    _newtext = Counter(texts)
    for text, duplicate in _newtext.most_common() :
        if duplicate >1:
            print(text,duplicate)