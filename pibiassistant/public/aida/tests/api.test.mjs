import test from "node:test";
import assert from "node:assert/strict";
import { decodeError } from "../js/lib/api.js";
import { setMessages } from "../js/lib/i18n.js";

setMessages({});
const GENERIC = "AIDA couldn't finish this answer. Please try again.";
const msgs = (text) => JSON.stringify([JSON.stringify({ message: text, indicator: "red" })]);

test("401 and CSRF 403 are session errors", () => {
  assert.equal(decodeError(401, null).kind, "session");
  assert.equal(decodeError(403, { exc_type: "CSRFTokenError" }).kind, "session");
  assert.equal(decodeError(403, { exception: "frappe.exceptions.SessionStopped" }).kind, "session");
});

test("417 with server message is a validation error with decoded text", () => {
  const r = decodeError(417, { exc_type: "ValidationError", _server_messages: msgs("<b>AIDA is still answering.</b> [HTTP_417] ") });
  assert.equal(r.kind, "validation");
  assert.equal(r.message, "AIDA is still answering. [HTTP_417]");
});

test("leading HTTP marker is stripped", () => {
  const r = decodeError(417, { _server_messages: msgs("[HTTP_417] Wait please") });
  assert.equal(r.message, "Wait please");
});

test("technical messages never leak", () => {
  const traceback = "Traceback (most recent call last): File x.py";
  for (const body of [
    { exc_type: "ImportError", _server_messages: msgs("No module named foo") },
    { exc_type: "ValidationError", _server_messages: msgs("'X' object has no attribute 'y'") },
    { exc_type: "ValidationError", exception: traceback, exc: traceback, _server_messages: msgs(traceback) },
    { exc: traceback },
  ]) {
    const r = decodeError(417, body);
    assert.equal(r.kind, "server");
    assert.equal(r.message, GENERIC);
  }
});

test("tags are stripped to a fixpoint", () => {
  const r = decodeError(417, { _server_messages: msgs("<scr<script>ipt>alert(1)</script>ok") });
  assert.ok(!/<[a-z/]/i.test(r.message));
});

test("429 and unknown errors", () => {
  assert.equal(decodeError(429, null).message, "AIDA is busy right now. Please try again in a moment.");
  assert.equal(decodeError(500, { exception: "boom" }).message, GENERIC);
  assert.equal(decodeError(502, undefined).kind, "server");
});

test("network failures surface as ApiError network", async () => {
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };
  const { get } = await import("../js/lib/api.js");
  const orig = console.error;
  console.error = () => {};
  await assert.rejects(get("x"), (e) => e.kind === "network" && e.name === "ApiError");
  console.error = orig;
});
