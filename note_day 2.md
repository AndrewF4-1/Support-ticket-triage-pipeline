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