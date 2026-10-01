import test from "node:test";
import assert from "node:assert/strict";
import { readHandoff, writeHandoff, clearHandoff } from "../js/lib/handoff.js";

function fakeStorage() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v), removeItem: (k) => m.delete(k) };
}

test("round trip for the same user", () => {
  globalThis.sessionStorage = fakeStorage();
  assert.equal(writeHandoff("k", "pao_1", "u@x"), true);
  assert.equal(readHandoff("k", "u@x"), "pao_1");
});

test("other user, bare string and bad JSON are rejected", () => {
  globalThis.sessionStorage = fakeStorage();
  writeHandoff("k", "pao_1", "other@x");
  assert.equal(readHandoff("k", "u@x"), null);
  sessionStorage.setItem("k", "pao_2");
  assert.equal(readHandoff("k", "u@x"), null);
  sessionStorage.setItem("k", "{bad");
  assert.equal(readHandoff("k", "u@x"), null);
  sessionStorage.setItem("k", JSON.stringify({ user: "u@x" }));
  assert.equal(readHandoff("k", "u@x"), null);
});

test("write without id is a no-op and clear removes", () => {
  globalThis.sessionStorage = fakeStorage();
  assert.equal(writeHandoff("k", "", "u"), false);
  writeHandoff("k", "a", "u");
  clearHandoff("k");
  assert.equal(readHandoff("k", "u"), null);
});

test("throwing storage never throws", () => {
  globalThis.sessionStorage = {
    getItem() { throw new Error("x"); },
    setItem() { throw new Error("x"); },
    removeItem() { throw new Error("x"); },
  };
  assert.equal(readHandoff("k", "u"), null);
  assert.equal(writeHandoff("k", "a", "u"), false);
  clearHandoff("k");
});
