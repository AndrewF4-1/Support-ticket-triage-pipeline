# Day 2 – loading and describing tickets

## Tools I used

**sorted()** — a built-in function (always there, no import).
Returns a NEW sorted list; the original is unchanged.
    sorted(items)                          # smallest first
    sorted(items, reverse=True)            # biggest first
    sorted(items, key=lambda t: len(t["text"]))   # sort by something I choose

**lambda** — a tiny one-line function with no name.
    lambda t: len(t["text"])   means "given t, give back the length of its text"

**Counter** — a class from the collections module.
    from collections import Counter
    counts = Counter(some_list)
It's a special kind of dictionary: key = the thing, value = how many times.
    counts.most_common()      # (thing, count) pairs, biggest first
    counts.most_common(5)     # top 5 only
    counts.items()            # (thing, count) pairs, in no particular order
    len(counts)               # how many DIFFERENT things

**json.loads(text)** — one line of text → one dictionary. ("s" = string)
**json.load(f)** — a whole file → one object. Not for JSONL.

## Mistakes I made, and the rule
- `return a, b` returns a tuple (a fixed pair), not two separate things.
- After a loop ends, the loop variable keeps only the LAST value.
- Don't reuse one name for two things (the list and the loop item).
- sorted() on a dict sorts only the keys. Counts are lost. Use .items().
- Check totals add up (my categories summed to 600).

## The data
- 600 tickets.
- Categories: shipping 146, billing 131, returns 95,
  product_fault 86, account_access 72, other 70.
- Shortest ticket: __ characters. Longest: __ characters.
- __ messages were sent more than once. __ extra copies in total.
- Many tickets contain phone numbers and emails (personal data).


## Five longest text:
longest ticket: {'id': 'T00018', 'text': 'Hi team, Please explain how to start a return. Also my invoice shows a payment failed note. This is the second time I am writing. Please refund me. You can reach me on 0491 570 006 or dana73@example.com. Thanks, Dana', 'true_category': 'returns', 'true_priority': 'high', 'true_refund': True}, 216
longest ticket: {'id': 'T00152', 'text': 'Hi team, I was charged twice for my order this week. Also the courier left a delivery card with no tracking number. I have had no reply so far. You can reach me on 0491 570 110 or jordan27@example.com. Thanks, Jordan', 'true_category': 'billing', 'true_priority': 'medium', 'true_refund': False}, 216
longest ticket: {'id': 'T00520', 'text': 'Hi team, Tracking has not updated since Monday. Also my password reset link and verification code failed. This is urgent, please help immediately. You can reach me on 0491 570 156 or casey18@example.com. Thanks, Casey', 'true_category': 'shipping', 'true_priority': 'high', 'true_refund': False}, 217
longest ticket: {'id': 'T00480', 'text': 'Hi team, I would like to send it back. Also the courier left a delivery card with no tracking number. I am still waiting for a reply. Please refund me. You can reach me on 0491 570 157 or casey19@example.com. Thanks, Casey', 'true_category': 'returns', 'true_priority': 'medium', 'true_refund': True}, 222
longest ticket: {'id': 'T00237', 'text': 'Hi team, Tracking has not updated since Monday. Also my password reset link and verification code failed. This is the second time I am writing. Please refund me. You can reach me on 0491 570 157 or taylor5@example.com. Thanks, Taylor', 'true_category': 'shipping', 'true_priority': 'high', 'true_refund': True}, 233.


## Shortest text:
shortest text: {'id': 'T00371', 'text': 'Hi team, The kettle is faulty. Thanks, Jamie', 'true_category': 'product_fault', 'true_priority': 'low', 'true_refund': False}, 44
shortest text: {'id': 'T00367', 'text': 'Hi team, The kettle is faulty. Thanks, Jordan', 'true_category': 'product_fault', 'true_priority': 'low', 'true_refund': False}, 45
shortest text: {'id': 'T00179', 'text': 'Hi team, My password is rejected. Thanks, Riley', 'true_category': 'account_access', 'true_priority': 'low', 'true_refund': False}, 47
shortest text: {'id': 'T00206', 'text': 'Hi team, Do you sell gift wrapping? Thanks, Sam', 'true_category': 'other', 'true_priority': 'low', 'true_refund': False}, 47
shortest text: {'id': 'T00044', 'text': 'Hi team, Do you sell gift wrapping? Thanks, Dana', 'true_category': 'other', 'true_priority': 'low', 'true_refund': False}, 48

## Text repeated:
Hi team, The courier says it was left but nothing is here. Thanks, Sam 7
Hi team, My parcel has not moved for days. Thanks, Riley 5
Hi team, My parcel has not moved for days. Thanks, Taylor 5
Hi team, Tracking has not updated since Monday. Also my invoice shows a payment failed note. I will file a chargeback if this continues. Thanks, Alex 4
Hi team, My receipt is missing and I need a copy. Thanks, Jordan 4
Hi team, The reset link never arrives. Also the courier left a delivery card with no tracking number. Thanks, Sam 3
Hi team, My parcel has not moved for days. Thanks, Jordan 3
Hi team, Can I do an exchange for a smaller one? Thanks, Jamie 3
Hi team, It is the wrong size for me. This is urgent, please help immediately. Thanks, Jordan 3
Hi team, My receipt is missing and I need a copy. Thanks, Alex 3
Hi team, The invoice I received does not match what I paid. Thanks, Jamie 3
Hi team, Can I change the name on my loyalty card? Thanks, Dana 3
Hi team, The screen arrived cracked. I would like my money back. Thanks, Casey 3
Hi team, The blender stopped working after two days. Thanks, Jordan 3
Hi team, I was charged twice for my order this week. Thanks, Chris 3
Hi team, I was charged twice for my order this week. Thanks, Taylor 3
Hi team, Please explain how to start a return. You can reach me on 0491 570 156 or morgan90@example.com. Thanks, Morgan 2
Hi team, The delivery has not shown up yet. Thanks, Sam 2
Hi team, What are your opening hours at Christmas? You can reach me on 0491 570 157 or alex17@example.com. Thanks, Alex 2
Hi team, The courier says it was left but nothing is here. Thanks, Jordan 2
Hi team, The blender stopped working after two days. I will file a chargeback if this continues. Thanks, Riley 2
Hi team, There is an overcharged amount on my statement. Please refund me. Thanks, Jordan 2
Hi team, Do you have a store in Melbourne? Thanks, Sam 2
Hi team, I am locked out of my account. I would like my money back. Thanks, Dana 2
Hi team, Can I do an exchange for a smaller one? Please refund me. Thanks, Jordan 2
Hi team, The invoice I received does not match what I paid. I am still waiting for a reply. Thanks, Chris 2
Hi team, I am locked out of my account. Thanks, Chris 2
Hi team, My parcel has not moved for days. Thanks, Jamie 2
Hi team, It is the wrong size for me. Thanks, Taylor 2
Hi team, What are your opening hours at Christmas? I am still waiting for a reply. Thanks, Jordan 2
Hi team, The delivery has not shown up yet. Also I may need a return label for an exchange. Thanks, Casey 2
Hi team, The blender stopped working after two days. Thanks, Casey 2
Hi team, Do you sell gift wrapping? You can reach me on 0491 570 157 or riley16@example.com. Thanks, Riley 2
Hi team, There is an overcharged amount on my statement. Thanks, Alex 2
Hi team, Tracking has not updated since Monday. This is urgent, please help immediately. Thanks, Riley 2
Hi team, Please explain how to start a return. I would like my money back. You can reach me on 0491 570 159 or riley1@example.com. Thanks, Riley 2
Hi team, It is the wrong size for me. Thanks, Morgan 2
Hi team, Tracking has not updated since Monday. Also my password reset link and verification code failed. You can reach me on 0491 570 157 or jamie95@example.com. Thanks, Jamie 2
Hi team, Can I do an exchange for a smaller one? Thanks, Alex 2
Hi team, It is the wrong size for me. Also the lid is cracked and looks defective. I will file a chargeback if this continues. Thanks, Sam 2
Hi team, I would like to send it back. I am still waiting for a reply. Thanks, Sam 2
Hi team, The delivery has not shown up yet. Please refund me. Thanks, Riley 2
Hi team, I was charged twice for my order this week. Thanks, Jamie 2
Hi team, Can I change the name on my loyalty card? I am still waiting for a reply. Thanks, Morgan 2
Hi team, Do you have a store in Melbourne? Thanks, Riley 2
Hi team, The delivery has not shown up yet. You can reach me on 0491 570 159 or jamie96@example.com. Thanks, Jamie 2
Hi team, Please explain how to start a return. This is urgent, please help immediately. I would like my money back. You can reach me on 0491 570 156 or riley8@example.com. Thanks, Riley 2
Hi team, My parcel has not moved for days. Thanks, Chris 2
Hi team, There is an overcharged amount on my statement. Thanks, Riley 2
Hi team, Can I do an exchange for a smaller one? Thanks, Morgan 2
Hi team, The reset link never arrives. Please refund me. Thanks, Jordan 2
Hi team, The reset link never arrives. I would like my money back. You can reach me on 0491 570 158 or casey52@example.com. Thanks, Casey 2
Hi team, What are your opening hours at Christmas? I will file a chargeback if this continues. You can reach me on 0491 570 157 or sam92@example.com. Thanks, Sam 2
Hi team, The verification code does not come through. This is the second time I am writing. Please refund me. Thanks, Dana 2
Hi team, It is defective out of the box. I have had no reply so far. You can reach me on 0491 570 157 or dana8@example.com. Thanks, Dana 2
Hi team, There is an overcharged amount on my statement. You can reach me on 0491 570 157 or chris99@example.com. Thanks, Chris 2
Hi team, The blender stopped working after two days. Thanks, Chris 2
Hi team, There is an overcharged amount on my statement. Thanks, Morgan 2
Hi team, The reset link never arrives. Thanks, Jamie 2
Hi team, My password is rejected. I have had no reply so far. You can reach me on 0491 570 157 or jamie38@example.com. Thanks, Jamie 2
Hi team, Can I do an exchange for a smaller one? Please refund me. Thanks, Morgan 2
Hi team, The courier says it was left but nothing is here. I would like my money back. Thanks, Chris 2
Hi team, I would like to send it back. Also the lid is cracked and looks defective. I will file a chargeback if this continues. Thanks, Alex 2
Hi team, There is an overcharged amount on my statement. Also my password reset link and verification code failed. I would like my money back. Thanks, Chris 2
Hi team, The courier says it was left but nothing is here. Thanks, Riley 2
Hi team, The blender stopped working after two days. Also I may need a return label for an exchange. Thanks, Morgan 2
Hi team, Can I change the name on my loyalty card? Thanks, Jordan 2
Hi team, It is the wrong size for me. You can reach me on 0491 570 158 or sam32@example.com. Thanks, Sam 2
Hi team, What are your opening hours at Christmas? Thanks, Jamie 2
Hi team, My parcel has not moved for days. Also my password reset link and verification code failed. Thanks, Jamie 2
Hi team, Do you sell gift wrapping? Thanks, Alex 2
Hi team, The delivery has not shown up yet. Thanks, Alex 2
Hi team, The invoice I received does not match what I paid. Also I may need a return label for an exchange. I would like my money back. Thanks, Riley 2
Hi team, What are your opening hours at Christmas? Thanks, Riley 2
Hi team, The kettle is faulty. You can reach me on 0491 570 159 or casey58@example.com. Thanks, Casey 2
Hi team, I am locked out of my account. Please refund me. You can reach me on 0491 570 158 or morgan34@example.com. Thanks, Morgan 2
Hi team, Tracking has not updated since Monday. Thanks, Alex 2