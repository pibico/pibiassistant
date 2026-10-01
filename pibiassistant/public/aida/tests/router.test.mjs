import test from "node:test";
import assert from "node:assert/strict";
import { parse, chatPath, SETTINGS_PATH } from "../js/router.js";

const chat = (canonical, sessionId = null) => ({ name: "chat", sessionId, canonical });

test("chat routes", () => {
  for (const p of ["/aida", "/aida/", "/aida/chat", "/aida/chat/"]) {
    assert.deepEqual(parse(p), chat("/aida/chat"));
  }
  assert.deepEqual(parse("/aida/chat/pao_1_abc"), chat("/aida/chat/pao_1_abc", "pao_1_abc"));
});

test("settings routes", () => {
  assert.deepEqual(parse("/aida/settings"), { name: "settings", sessionId: null, canonical: SETTINGS_PATH });
  assert.equal(parse("/aida/settings/").name, "settings");
});

test("legacy and invalid paths redirect to chat", () => {
  for (const p of ["/aida/knowledge", "/aida/agents", "/aida/analytics", "/aida/settings/profile", "/aida/chat/a/b", "/aida/chat/bad id", "/aida/chat/a.b", "/other", ""]) {
    assert.deepEqual(parse(p), chat("/aida/chat"), p);
  }
});

test("query string and hash are stripped", () => {
  assert.deepEqual(parse("/aida/chat?tab=billing"), chat("/aida/chat"));
  assert.deepEqual(parse("/aida/chat/abc?x=1#h"), chat("/aida/chat/abc", "abc"));
  assert.equal(parse("/aida/settings?x=1").canonical, "/aida/settings");
});

test("chatPath", () => {
  assert.equal(chatPath(), "/aida/chat");
  assert.equal(chatPath("abc"), "/aida/chat/abc");
});
