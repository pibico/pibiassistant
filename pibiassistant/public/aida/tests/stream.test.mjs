import { test } from "node:test";
import assert from "node:assert/strict";
import { applyStreamEvent, isTerminal } from "../js/lib/stream.js";

const base = () => ({ key: "m_1", role: "assistant", content: "", status: "streaming", model: null, messageId: null, ts: 0 });

test("start stores id and model", () => {
  const m = applyStreamEvent(base(), { event: "stream_start", message_id: "abc", model_id: "gpt" }, 1);
  assert.equal(m.messageId, "abc");
  assert.equal(m.model, "gpt");
});

test("chunk prefers accumulated and self-heals", () => {
  let m = applyStreamEvent(base(), { event: "stream_chunk", chunk: "He", accumulated: "He" }, 1);
  m = applyStreamEvent(m, { event: "stream_chunk", chunk: "llo", accumulated: "Hello" }, 1);
  assert.equal(m.content, "Hello");
  m = applyStreamEvent(m, { event: "stream_chunk", chunk: "!" }, 1);
  assert.equal(m.content, "Hello!");
});

test("complete sets stats and ignores later chunks", () => {
  let m = applyStreamEvent(base(), { event: "stream_complete", full_response: "Done", prompt_tokens: 5, completion_tokens: 0, duration_ms: 100, truncated: true }, 9);
  assert.equal(m.status, "done");
  assert.equal(m.promptTokens, 5);
  assert.equal(m.completionTokens, null);
  assert.equal(m.truncated, true);
  assert.equal(m.ts, 9);
  const after = applyStreamEvent(m, { event: "stream_chunk", chunk: "x" }, 10);
  assert.equal(after, m);
});

test("error never exposes server text", () => {
  const m = applyStreamEvent(base(), { event: "stream_error", error: "Traceback secret" }, 2);
  assert.equal(m.status, "error");
  assert.ok(!m.errorText.includes("secret"));
});

test("aborted strips marker", () => {
  const start = { ...base(), content: "part\n\n_(Stopped by user)_" };
  assert.equal(applyStreamEvent(start, { event: "stream_aborted" }, 3).content, "part");
  assert.equal(applyStreamEvent(base(), { event: "stream_aborted", partial_response: "x\n\n_(Stopped by user)_" }, 3).content, "x");
});

test("unknown events ignored", () => {
  const m = base();
  assert.equal(applyStreamEvent(m, { event: "stream_cancel_requested" }, 1), m);
  assert.ok(isTerminal("stream_error"));
  assert.ok(!isTerminal("stream_chunk"));
});
