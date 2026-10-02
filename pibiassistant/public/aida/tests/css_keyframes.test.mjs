import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const cssDir = fileURLToPath(new URL("../css/", import.meta.url));
const css = readdirSync(cssDir).filter((f) => f.endsWith(".css")).map((f) => readFileSync(join(cssDir, f), "utf8")).join("\n");

test("single 360deg spin keyframes, used by the mic spinner", () => {
  assert.equal(css.includes("aida-mic-spin"), false);
  assert.equal((css.match(/@keyframes aida-spin\b/g) || []).length, 1);
  assert.match(css, /\.aida-mic\.is-transcribing[^\n]*animation: aida-spin/);
});
