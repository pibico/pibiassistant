import test from "node:test";
import assert from "node:assert/strict";
import { setMessages } from "../js/lib/i18n.js";
import * as f from "../js/lib/format.js";

setMessages({});

test("parseServerTs treats naive strings as local time", () => {
  const ms = f.parseServerTs("2026-10-01 19:08:12.065930");
  const d = new Date(ms);
  assert.deepEqual([d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), d.getMinutes()], [2026, 9, 1, 19, 8]);
  assert.equal(f.parseServerTs("2026-10-01T10:00:00Z"), Date.UTC(2026, 9, 1, 10));
  assert.equal(f.parseServerTs(123), 123);
  assert.ok(Math.abs(f.parseServerTs("garbage") - Date.now()) < 1000);
});

test("parseServerTs converts naive strings from the site time zone", () => {
  f.setSiteTimezone("Europe/Madrid");
  try {
    assert.equal(f.parseServerTs("2026-10-02 15:41:00.123456"), Date.UTC(2026, 9, 2, 13, 41, 0, 123));
    assert.equal(f.parseServerTs("2026-01-15 15:41:00"), Date.UTC(2026, 0, 15, 14, 41));
    assert.equal(f.parseServerTs("2026-03-29 03:30:00"), Date.UTC(2026, 2, 29, 1, 30));
    f.setSiteTimezone("Asia/Tokyo");
    assert.equal(f.parseServerTs("2026-10-02 15:41:00"), Date.UTC(2026, 9, 2, 6, 41));
    f.setSiteTimezone("Not/AZone");
    const d = new Date(f.parseServerTs("2026-10-02 15:41:00"));
    assert.deepEqual([d.getHours(), d.getMinutes()], [15, 41]);
    assert.equal(f.parseServerTs("2026-10-01T10:00:00Z"), Date.UTC(2026, 9, 1, 10));
  } finally {
    f.setSiteTimezone(null);
  }
});

test("formatTime same day vs other day", () => {
  const now = new Date(2026, 9, 1, 12).getTime();
  const same = f.formatTime(new Date(2026, 9, 1, 9, 5).getTime(), now, "en");
  assert.match(same, /9:05/);
  assert.doesNotMatch(same, /Oct/);
  assert.match(f.formatTime(new Date(2026, 8, 20, 9, 5).getTime(), now, "en"), /Sep/);
});

test("tokensPerSecond", () => {
  assert.equal(f.tokensPerSecond(790, 4812), "164.2");
  assert.equal(f.tokensPerSecond(0, 100), null);
  assert.equal(f.tokensPerSecond(10, 0), null);
  assert.equal(f.tokensPerSecond(null, 10), null);
});

test("stripProvider", () => {
  assert.equal(f.stripProvider("ollama/x:y"), "x:y");
  assert.equal(f.stripProvider("gpt-oss:20b"), "gpt-oss:20b");
  assert.equal(f.stripProvider("auto"), null);
  assert.equal(f.stripProvider(""), null);
});

test("formatBytes and truncate", () => {
  assert.equal(f.formatBytes(845), "845 B");
  assert.equal(f.formatBytes(12.3 * 1024), "12.3 KB");
  assert.equal(f.formatBytes(1.2 * 1024 * 1024), "1.2 MB");
  assert.equal(f.truncate("  a   b  ", 10), "a b");
  assert.equal(f.truncate("abcdefghij", 5), "abcd…");
});

test("stripStopMarker", () => {
  assert.equal(f.stripStopMarker("part\n\n_(Stopped by user)_"), "part");
  assert.equal(f.stripStopMarker("plain"), "plain");
});

test("fromHistoryRow", () => {
  const user = f.fromHistoryRow({ name: "M1", role: "user", content: "hi", timestamp: "2026-10-01 10:00:00", attachments: [{ file_name: "a.pdf", file_url: "/files/a.pdf" }] });
  assert.equal(user.key, "h_M1");
  assert.deepEqual(user.files, [{ name: "a.pdf", url: "/files/a.pdf" }]);
  assert.equal(user.status, "done");

  const ok = f.fromHistoryRow({ name: "M2", role: "assistant", content: "ans", message_id: "abc", model: "gpt", prompt_tokens: 5, completion_tokens: 0, duration_ms: 10, timestamp: "2026-10-01 10:00:01" });
  assert.equal(ok.status, "done");
  assert.equal(ok.completionTokens, null);
  assert.equal(ok.promptTokens, 5);
  assert.equal(ok.messageId, "abc");

  assert.equal(f.fromHistoryRow({ name: "M3", role: "assistant", content: "", blocks: "[]" }), null);

  const blocks = JSON.stringify([{ type: "text", content: "A" }, { type: "text", content: "\n\n_(Stopped by user)_", _abortMarker: true }, { type: "text", content: "B" }]);
  const fromBlocks = f.fromHistoryRow({ name: "M4", role: "assistant", content: "", blocks, aborted: 1 });
  assert.equal(fromBlocks.content, "AB");
  assert.equal(fromBlocks.status, "aborted");
  assert.equal(f.fromHistoryRow({ name: "M5", role: "assistant", content: "", blocks: "{bad", aborted: 1 }).content, "");

  const err = f.fromHistoryRow({ name: "M6", role: "assistant", content: "internal trace", errored: 1 });
  assert.equal(err.status, "error");
  assert.equal(err.content, "");
  assert.equal(err.errorText, "AIDA couldn't finish this answer. Please try again.");

  const stopped = f.fromHistoryRow({ name: "M7", role: "assistant", content: "x\n\n_(Stopped by user)_", aborted: 1 });
  assert.equal(stopped.content, "x");
});

test("groupSessions labels", () => {
  const now = new Date(2026, 9, 10, 12).getTime();
  const at = (d, h = 9) => new Date(2026, 9, d, h).getTime();
  const iso = (ms) => new Date(ms).toISOString();
  const groups = f.groupSessions(
    [{ last_activity: iso(at(10)) }, { last_activity: iso(at(10, 8)) }, { last_activity: iso(at(9)) }, { last_activity: iso(at(6)) }, { last_activity: iso(at(1)) }],
    now,
  );
  assert.deepEqual(groups.map((g) => g.label), ["Today", "Yesterday", "This week", groups[3].label]);
  assert.equal(groups[0].items.length, 2);
  assert.match(groups[3].label, /Oct/);
});

test("titles", () => {
  const msgs = [{ role: "user", content: "x".repeat(80) }];
  assert.equal(f.titleOf(msgs).length, 60);
  assert.equal(f.titleOf([]), "");
  assert.equal(f.pageTitle({ route: { name: "settings" }, messages: [] }), "Settings");
  assert.equal(f.pageTitle({ route: { name: "chat" }, messages: [] }), "Chat");
  assert.equal(f.documentTitleOf({ route: { name: "chat" }, messages: [{ role: "user", content: "Hola" }] }), "Hola - AIDA");
  assert.equal(f.documentTitleOf({ route: { name: "chat" }, messages: [] }), "AIDA");
  assert.equal(f.documentTitleOf({ route: { name: "settings" }, messages: [] }), "Settings - AIDA");
});

test("session ids", () => {
  assert.match(f.newSessionId(), /^pao_\d{13}_[0-9a-f]{18}$/);
  assert.equal(f.isValidSessionId("pao_1-a"), true);
  assert.equal(f.isValidSessionId("a b"), false);
  assert.equal(f.isValidSessionId(""), false);
  assert.equal(f.isValidSessionId("x".repeat(101)), false);
});

test("isStaleShellRow flags only old empty unfinished assistant rows", async () => {
  const { isStaleShellRow } = await import("../js/lib/format.js");
  const now = Date.parse("2026-10-01T12:00:00");
  const row = { role: "assistant", content: "", blocks: "[]", timestamp: "2026-10-01 11:50:00" };
  assert.equal(isStaleShellRow(row, now), true);
  assert.equal(isStaleShellRow({ ...row, timestamp: "2026-10-01 11:59:30" }, now), false);
  assert.equal(isStaleShellRow({ ...row, content: "x" }, now), false);
  assert.equal(isStaleShellRow({ ...row, errored: 1 }, now), false);
});
