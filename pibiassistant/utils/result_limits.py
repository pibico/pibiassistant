"""Keep large tool results usable: trim rows from the longest list and say how many were dropped."""

import json

DEFAULT_HINT = "Result truncated; narrow the filters, add fields or limit, or aggregate instead."


def find_rows(obj, depth=0):
    """(container, key) of the longest list in a result, looking two levels deep."""
    best = None
    items = obj.items() if isinstance(obj, dict) else []
    for key, value in items:
        if isinstance(value, list) and (best is None or len(value) > len(best[0][best[1]])):
            best = (obj, key)
        elif isinstance(value, dict) and depth < 1:
            inner = find_rows(value, depth + 1)
            if inner and (best is None or len(inner[0][inner[1]]) > len(best[0][best[1]])):
                best = inner
    return best


def fit_result(text: str, limit: int, hint: str = DEFAULT_HINT) -> str:
    """Keep a tool result under ``limit`` chars as valid JSON: drop trailing rows, say how many."""
    if len(text) <= limit:
        return text
    try:
        obj = json.loads(text)
    except ValueError:
        return json.dumps({"truncated": True, "preview": text[: limit - 200], "hint": hint}, ensure_ascii=False)
    if isinstance(obj, list):
        obj = {"rows": obj}
    found = find_rows(obj)
    if not found:
        return json.dumps({"truncated": True, "preview": text[: limit - 200], "hint": hint}, ensure_ascii=False)
    holder, key = found
    rows = holder[key]
    total = len(rows)

    def build(keep):
        holder[key] = rows[:keep]
        return json.dumps(
            {**obj, "truncated": True, "rows_shown": keep, "total": total, "hint": hint},
            default=str,
            ensure_ascii=False,
        )

    lo, hi, best = 1, total, None
    while lo <= hi:
        mid = (lo + hi) // 2
        out = build(mid)
        if len(out) <= limit:
            best, lo = out, mid + 1
        else:
            hi = mid - 1
    return best or json.dumps({"truncated": True, "preview": text[: limit - 200], "hint": hint}, ensure_ascii=False)
