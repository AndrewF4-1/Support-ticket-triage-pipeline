import json

def load_jsonl_file(file_path):
    ticket= []
    for file in file_path:
        with open(file, 'r') as f:
            for line in f:
                ticket.append(json.loads(line))
    return ticket
first_test = load_jsonl_file("C:/Users/nguye/OneDrive/projects/Project 1/data/tickets.jsonl")