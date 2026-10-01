import test from "node:test";
import assert from "node:assert/strict";
import { createStore } from "../js/lib/store.js";

test("set merges shallowly and notifies with changed keys", () => {
  const s = createStore({ a: 1, b: 2 });
  const calls = [];
  s.subscribe((st, keys) => calls.push([st.a, keys]));
  s.set({ a: 5 });
  assert.deepEqual(s.get(), { a: 5, b: 2 });
  assert.deepEqual(calls, [[5, ["a"]]]);
});

test("no notification when nothing changed", () => {
  const s = createStore({ a: 1 });
  let n = 0;
  s.subscribe(() => n++);
  s.set({ a: 1 });
  assert.equal(n, 0);
});

test("keys filter and unsubscribe", () => {
  const s = createStore({ a: 1, b: 1 });
  let n = 0;
  const off = s.subscribe(() => n++, ["b"]);
  s.set({ a: 2 });
  assert.equal(n, 0);
  s.set({ b: 2 });
  assert.equal(n, 1);
  off();
  s.set({ b: 3 });
  assert.equal(n, 1);
});

test("a throwing listener does not stop others", () => {
  const s = createStore({ a: 1 });
  const orig = console.error;
  console.error = () => {};
  let ok = false;
  s.subscribe(() => {
    throw new Error("boom");
  });
  s.subscribe(() => (ok = true));
  s.set({ a: 2 });
  console.error = orig;
  assert.equal(ok, true);
});
