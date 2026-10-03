"""Conversion of the internal chat shape to provider wire formats (pure functions).

Internal messages: {"role": system|user|assistant|tool, "content": str}; an assistant
tool turn adds "tool_calls": [{"function": {"name", "arguments": dict}}] without ids
and, for Anthropic only, an opaque "_raw" list of content blocks; a tool result is
{"role": "tool", "tool_name", "content"}.
"""

import json
import uuid

NO_RESULT = {"error": "No result was recorded for this call."}


def _new_id(prefix):
    return f"{prefix}{uuid.uuid4().hex[:24]}"


def _args(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            v = json.loads(value)
        except ValueError:
            return {}
        return v if isinstance(v, dict) else {}
    return {}


def _norm_calls(tool_calls):
    out = []
    for c in tool_calls or []:
        if not isinstance(c, dict):
            continue
        fn = c.get("function") if isinstance(c.get("function"), dict) else c
        name = fn.get("name")
        if name:
            out.append({"name": str(name), "arguments": _args(fn.get("arguments"))})
    return out


def _text(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _raw_valid(raw, count):
    if not isinstance(raw, list):
        return False
    uses = [b for b in raw if isinstance(b, dict) and b.get("type") == "tool_use"]
    return len(uses) == count and all(b.get("id") for b in uses)


def match_tool_results(messages, anthropic=False):
    """Pair each assistant tool turn with its results, FIFO.

    Returns [{"role", "content", "calls": [{"id","name","arguments","result"}], "raw"?}].
    Tool messages that cannot be paired become plain user messages.
    """
    prefix = "toolu_" if anthropic else "call_"
    out = []
    msgs = list(messages or [])
    i = 0
    while i < len(msgs):
        m = msgs[i]
        i += 1
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            calls = _norm_calls(m.get("tool_calls"))
            raw = m.get("_raw") if anthropic and _raw_valid(m.get("_raw"), len(calls)) else None
            if raw is not None:
                ids = [b["id"] for b in raw if b.get("type") == "tool_use"]
            else:
                ids = [_new_id(prefix) for _ in calls]
            slots = [
                {"id": ids[k], "name": c["name"], "arguments": c["arguments"], "result": None}
                for k, c in enumerate(calls)
            ]
            extra = []
            while i < len(msgs) and msgs[i].get("role") == "tool":
                t = msgs[i]
                i += 1
                free = [s for s in slots if s["result"] is None]
                pick = next((s for s in free if s["name"] == t.get("tool_name")), None) or (free[0] if free else None)
                if pick is None:
                    extra.append(
                        {
                            "role": "user",
                            "content": f"Tool result ({t.get('tool_name') or 'tool'}): {_text(t.get('content'))}",
                            "calls": [],
                        }
                    )
                else:
                    pick["result"] = _text(t.get("content"))
            for s in slots:
                if s["result"] is None:
                    s["result"] = json.dumps(NO_RESULT)
            item = {"role": "assistant", "content": _text(m.get("content")), "calls": slots}
            if raw is not None:
                item["raw"] = raw
            out.append(item)
            out.extend(extra)
        elif role == "tool":
            out.append(
                {
                    "role": "user",
                    "content": f"Tool result ({m.get('tool_name') or 'tool'}): {_text(m.get('content'))}",
                    "calls": [],
                }
            )
        elif role in ("system", "user", "assistant"):
            out.append({"role": role, "content": _text(m.get("content")), "calls": []})
    return out


def to_openai_tools(specs):
    out = []
    for s in specs or []:
        fn = s.get("function") if isinstance(s, dict) and isinstance(s.get("function"), dict) else s
        if not isinstance(fn, dict) or not fn.get("name"):
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": fn["name"],
                    "description": fn.get("description") or "",
                    "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
                },
            }
        )
    return out


def to_anthropic_tools(specs):
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "input_schema": t["function"]["parameters"],
        }
        for t in to_openai_tools(specs)
    ]


def to_openai_messages(messages):
    out = []
    for it in match_tool_results(messages):
        if it["calls"]:
            out.append(
                {
                    "role": "assistant",
                    "content": it["content"] or None,
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {
                                "name": c["name"],
                                "arguments": json.dumps(c["arguments"], ensure_ascii=False),
                            },
                        }
                        for c in it["calls"]
                    ],
                }
            )
            for c in it["calls"]:
                out.append({"role": "tool", "tool_call_id": c["id"], "content": c["result"]})
        else:
            out.append({"role": it["role"], "content": it["content"]})
    return out


def _blocks(content):
    return [{"type": "text", "text": content}] if content else []


def _push_user(out, blocks):
    if not blocks:
        return
    if out and out[-1]["role"] == "user":
        out[-1]["content"].extend(blocks)
    else:
        out.append({"role": "user", "content": list(blocks)})


def to_anthropic(messages, with_tools):
    """Return (system_text, messages) for POST /v1/messages."""
    items = match_tool_results(messages, anthropic=True)
    system = "\n\n".join(it["content"] for it in items if it["role"] == "system" and it["content"])
    out = []
    for it in items:
        role = it["role"]
        if role == "system":
            continue
        if role == "user":
            _push_user(out, _blocks(it["content"]))
        elif it["calls"] and with_tools:
            if "raw" in it:
                blocks = list(it["raw"])
            else:
                blocks = _blocks(it["content"]) + [
                    {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["arguments"]}
                    for c in it["calls"]
                ]
            out.append({"role": "assistant", "content": blocks})
            _push_user(
                out,
                [{"type": "tool_result", "tool_use_id": c["id"], "content": c["result"]} for c in it["calls"]],
            )
        elif it["calls"]:
            lines = [it["content"]] if it["content"] else []
            lines += [
                f"[called {c['name']}({json.dumps(c['arguments'], ensure_ascii=False)})]" for c in it["calls"]
            ]
            out.append({"role": "assistant", "content": _blocks("\n".join(lines))})
            _push_user(
                out, _blocks("\n".join(f"Tool result ({c['name']}): {c['result']}" for c in it["calls"]))
            )
        else:
            blocks = _blocks(it["content"])
            if blocks:
                out.append({"role": "assistant", "content": blocks})
    return system, out
