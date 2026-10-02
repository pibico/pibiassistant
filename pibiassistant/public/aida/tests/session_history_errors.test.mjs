import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";

const { setMessages } = await import("../js/lib/i18n.js");
setMessages({});
globalThis.window = globalThis;
const { store } = await import("../js/lib/store.js");
const { loadHistory } = await import("../js/lib/session-history.js");

const origError = console.error;

async function historyStateFor(status, body) {
  globalThis.fetch = async () => ({ ok: false, status, json: async () => body });
  store.set({ activeSessionId: "s1", messages: [], streaming: { active: false } });
  console.error = () => {};
  try {
    await loadHistory("s1");
  } finally {
    console.error = origError;
  }
  return store.get().historyState;
}

test("expired session or CSRF 403 shows the error state, not not-found", async () => {
  assert.equal(await historyStateFor(403, { exc_type: "CSRFTokenError" }), "error");
  assert.equal(await historyStateFor(401, null), "error");
});

test("permission 403 is still treated as a missing conversation", async () => {
  assert.equal(await historyStateFor(403, { exc_type: "PermissionError", _server_messages: JSON.stringify([JSON.stringify({ message: "x" })]) }), "notfound");
});

test("stop-race retry requires the 417 busy answer", () => {
  const src = fs.readFileSync(new URL("../js/lib/chat.js", import.meta.url), "utf8");
  assert.match(src, /err\.status === 417 &&\s+LOCK_BUSY\.test\(err\.message\)/);
});
