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

    by_length = sorted(ticket, key=lambda t: len(t['text']),reverse=True)  

    return f'The longest tickets are:\n "{by_length[:5]}\n\n The shortest tickets are:\n {by_length[-5:]}'


# def duplicate_tickers(tickets):
#     texts = []
#     for ticket in tickets:
#         texts.append(ticket["text"])
#     _newtext = Counter(texts)
#     for text, duplicate in _newtext.items() :
#         if duplicate >1:
#             texts.append(text)
#     return Counter(texts).most_common()        

# print(duplicate_tickers(first_test))

texts = []
for ticket in first_test:
    texts.append(ticket["text"])
_newtext = Counter(texts)
for text, duplicate in _newtext.most_common() :
    if duplicate >1:
        print(text,duplicate)