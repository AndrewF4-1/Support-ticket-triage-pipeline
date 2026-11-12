import json
import copy
# def load_jsonl_file(file_path):
#     ticket= []
#     with open(file_path, 'r', encoding='utf-8') as f:
#         for line in f:
#             ticket.append(json.loads(line.strip()))
#     return ticket
# first_test = load_jsonl_file("C:/Users/nguye/OneDrive/projects/Project 1/data/tickets.jsonl")
# print(first_test[0])

a = [
    [1,2,3],
    [4,5,4]
]
b = a[1].copy()
a[1]= [8,9,10]
print(b)