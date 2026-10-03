"""Internal chat shape to provider wire formats."""

import json
import unittest

from pibiassistant.pibiassistant_chat.api.chat.providers import messages as M


def call(name, args=None):
    return {"function": {"name": name, "arguments": args or {}}}


def tool(name, content):
    return {"role": "tool", "tool_name": name, "content": content}


SPECS = [{"type": "function", "function": {"name": "t1", "description": "d", "parameters": {"type": "object", "properties": {"a": {"type": "string"}}}}}]


class TestMatching(unittest.TestCase):
    def test_pairs_by_name_then_fifo(self):
        msgs = [{"role": "assistant", "content": "", "tool_calls": [call("a"), call("b"), call("a")]},
                tool("b", "RB"), tool("a", "RA1"), tool("zzz", "RZ")]
        out = M.match_tool_results(msgs)
        calls = out[0]["calls"]
        self.assertEqual([c["result"] for c in calls], ["RA1", "RB", "RZ"])
        self.assertEqual(len({c["id"] for c in calls}), 3)
        self.assertTrue(all(c["id"].startswith("call_") for c in calls))

    def test_unanswered_call_gets_error_result(self):
        out = M.match_tool_results([{"role": "assistant", "content": "x", "tool_calls": [call("a"), call("b")]}, tool("a", "ok")])
        self.assertEqual(out[0]["calls"][0]["result"], "ok")
        self.assertIn("No result was recorded", out[0]["calls"][1]["result"])

    def test_surplus_and_orphans_become_user_text(self):
        out = M.match_tool_results([tool("lonely", "R0"), {"role": "assistant", "content": "", "tool_calls": [call("a")]}, tool("a", "R1"), tool("a", "R2")])
        self.assertEqual(out[0], {"role": "user", "content": "Tool result (lonely): R0", "calls": []})
        self.assertEqual(out[-1]["content"], "Tool result (a): R2")
        self.assertEqual(out[-1]["role"], "user")

    def test_string_arguments_tolerated(self):
        out = M.match_tool_results([{"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "a", "arguments": '{"x":1}'}}, {"function": {"name": "b", "arguments": "oops"}}]}])
        self.assertEqual(out[0]["calls"][0]["arguments"], {"x": 1})
        self.assertEqual(out[0]["calls"][1]["arguments"], {})


class TestOpenAI(unittest.TestCase):
    def test_tool_turn_shape(self):
        out = M.to_openai_messages([
            {"role": "system", "content": "S"}, {"role": "user", "content": "U"},
            {"role": "assistant", "content": "", "tool_calls": [call("a", {"k": "é"}), call("b")]},
            tool("a", "RA"), tool("b", "RB"), {"role": "assistant", "content": "done"}])
        self.assertEqual(out[0], {"role": "system", "content": "S"})
        asst = out[2]
        self.assertIsNone(asst["content"])
        self.assertEqual(asst["tool_calls"][0]["function"]["arguments"], json.dumps({"k": "é"}, ensure_ascii=False))
        self.assertEqual([m["role"] for m in out[3:5]], ["tool", "tool"])
        self.assertEqual([m["tool_call_id"] for m in out[3:5]], [c["id"] for c in asst["tool_calls"]])
        self.assertEqual(out[5], {"role": "assistant", "content": "done"})

    def test_tools(self):
        t = M.to_openai_tools(SPECS + [{"name": "bare"}, {"nothing": 1}])
        self.assertEqual([x["function"]["name"] for x in t], ["t1", "bare"])
        self.assertEqual(t[1]["function"]["parameters"], {"type": "object", "properties": {}})
        self.assertEqual(M.to_openai_tools(None), [])


class TestAnthropic(unittest.TestCase):
    def conv(self, raw=None, extra=()):
        a = {"role": "assistant", "content": "thinking out loud", "tool_calls": [call("a"), call("b")]}
        if raw is not None:
            a["_raw"] = raw
        return [{"role": "system", "content": "S1"}, {"role": "system", "content": "S2"},
                {"role": "user", "content": "U"}, a, tool("a", "RA"), tool("b", "RB"), *extra]

    def test_system_joined_and_tool_results_grouped(self):
        system, msgs = M.to_anthropic(self.conv(extra=[{"role": "user", "content": "next"}]), True)
        self.assertEqual(system, "S1\n\nS2")
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        asst, res = msgs[1], msgs[2]
        uses = [b for b in asst["content"] if b["type"] == "tool_use"]
        self.assertEqual(asst["content"][0], {"type": "text", "text": "thinking out loud"})
        self.assertEqual([b["type"] for b in res["content"]], ["tool_result", "tool_result", "text"])
        self.assertEqual([b["tool_use_id"] for b in res["content"][:2]], [u["id"] for u in uses])
        self.assertTrue(all(u["id"].startswith("toolu_") for u in uses))

    def test_raw_blocks_replayed_unmodified(self):
        raw = [{"type": "thinking", "thinking": "t", "signature": "sig"},
               {"type": "tool_use", "id": "toolu_A", "name": "a", "input": {}},
               {"type": "tool_use", "id": "toolu_B", "name": "b", "input": {}}]
        _, msgs = M.to_anthropic(self.conv(raw=raw), True)
        self.assertEqual(msgs[1]["content"], raw)
        self.assertEqual([b["tool_use_id"] for b in msgs[2]["content"]], ["toolu_A", "toolu_B"])

    def test_invalid_raw_is_ignored(self):
        raw = [{"type": "tool_use", "id": "toolu_A", "name": "a", "input": {}}]  # 1 use, 2 calls
        _, msgs = M.to_anthropic(self.conv(raw=raw), True)
        self.assertEqual(len([b for b in msgs[1]["content"] if b["type"] == "tool_use"]), 2)
        self.assertNotIn("toolu_A", json.dumps(msgs))

    def test_flatten_without_tools(self):
        raw = [{"type": "tool_use", "id": "toolu_A", "name": "a", "input": {}}] * 2
        _, msgs = M.to_anthropic(self.conv(raw=raw), False)
        self.assertNotIn("tool_use", json.dumps(msgs))
        self.assertNotIn("tool_result", json.dumps(msgs))
        self.assertIn("[called a({})]", msgs[1]["content"][0]["text"])
        self.assertIn("Tool result (a): RA", msgs[2]["content"][0]["text"])

    def test_no_empty_text_blocks_and_adjacent_user_merge(self):
        _, msgs = M.to_anthropic([{"role": "user", "content": ""}, {"role": "user", "content": "a"}, {"role": "user", "content": "b"},
                                  {"role": "assistant", "content": ""}], True)
        self.assertEqual(msgs, [{"role": "user", "content": [{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}])

    def test_tools_shape(self):
        self.assertEqual(M.to_anthropic_tools(SPECS), [{"name": "t1", "description": "d", "input_schema": SPECS[0]["function"]["parameters"]}])
