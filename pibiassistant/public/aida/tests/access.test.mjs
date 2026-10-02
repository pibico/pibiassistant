import test from "node:test";
import assert from "node:assert/strict";

const { setMessages } = await import("../js/lib/i18n.js");
setMessages({});
const { hasAccess, noAccessMessage } = await import("../js/lib/access.js");
const { defaultMessage } = await import("../js/lib/format.js");
const { newMessage } = await import("../js/lib/chat-live.js");

test("access gate blocks only an explicit false", () => {
  assert.equal(hasAccess({ can_use: false }), false);
  assert.equal(hasAccess({ can_use: true }), true);
  assert.equal(hasAccess({}), true);
  assert.match(noAccessMessage(), /PA User role/);
});

test("live and history messages share defaults", () => {
  const live = newMessage({ role: "assistant" });
  const { key, ts, ...rest } = live;
  const { key: k2, ts: t2, ...base } = defaultMessage("x", { role: "assistant" });
  assert.deepEqual(rest, base);
  assert.match(key, /^m_\d+$/);
  assert.ok(ts > 0);
});
