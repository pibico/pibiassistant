import { test } from "node:test";
import assert from "node:assert/strict";
import { resolve } from "../js/lib/theme.js";

test("resolve explicit and auto", () => {
  globalThis.matchMedia = () => ({ matches: true });
  assert.equal(resolve("dark"), "dark");
  assert.equal(resolve("auto"), "dark");
  globalThis.matchMedia = () => ({ matches: false });
  assert.equal(resolve("auto"), "light");
  delete globalThis.matchMedia;
});
