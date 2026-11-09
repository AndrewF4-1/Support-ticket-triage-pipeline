import json

def load_jsonl_file(file_path):
    ticket= []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            ticket.append(json.loads(line.strip()))
    return ticket
first_test = load_jsonl_file("C:/Users/nguye/OneDrive/projects/Project 1/data/tickets.jsonl")
print(first_test)
# ticket= []
# with open("C:/Users/nguye/OneDrive/projects/Project 1/data/tickets.jsonl", 'r', encoding='utf-8') as f:
#     for line in f:
#         ticket.append(json.loads(line.strip()))
#         print(ticket)