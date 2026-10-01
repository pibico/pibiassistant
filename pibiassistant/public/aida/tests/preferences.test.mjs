import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { store } from "../js/lib/store.js";
import { init, setPref, getPrefs } from "../js/lib/preferences.js";
import { resolve } from "../js/lib/theme.js";

function fakeStorage(data = {}, throws = false) {
  return {
    getItem: (k) => { if (throws) throw new Error("x"); return k in data ? data[k] : null; },
    setItem: (k, v) => { if (throws) throw new Error("x"); data[k] = String(v); },
    removeItem: (k) => { delete data[k]; },
  };
}
beforeEach(() => { delete globalThis.theme; globalThis.localStorage = fakeStorage(); });

test("defaults", () => {
  init();
  assert.deepEqual(getPrefs(), { theme: "auto", density: "comfortable", showTimestamps: false });
});
test("boot theme", () => {
  globalThis.theme = "dark"; init(); assert.equal(getPrefs().theme, "dark");
  globalThis.theme = "automatic"; init(); assert.equal(getPrefs().theme, "auto");
});
test("stored values and invalid ignored", () => {
  globalThis.localStorage = fakeStorage({ aida_theme: "light", aida_density: "bogus", aida_show_timestamps: "1" });
  init();
  assert.deepEqual(getPrefs(), { theme: "light", density: "comfortable", showTimestamps: true });
});
test("setPref validates and persists", () => {
  const data = {};
  globalThis.localStorage = fakeStorage(data);
  init();
  setPref("density", "compact");
  setPref("theme", "nope");
  setPref("showTimestamps", true);
  assert.equal(getPrefs().density, "compact");
  assert.equal(getPrefs().theme, "auto");
  assert.equal(data.aida_density, "compact");
  assert.equal(data.aida_show_timestamps, "1");
});
test("storage throwing", () => {
  globalThis.localStorage = fakeStorage({}, true);
  init();
  setPref("density", "compact");
  assert.equal(getPrefs().density, "compact");
  assert.ok(store.get().prefs);
});
test("theme resolve", () => {
  globalThis.matchMedia = () => ({ matches: true });
  assert.equal(resolve("auto"), "dark");
  assert.equal(resolve("light"), "light");
  globalThis.matchMedia = () => ({ matches: false });
  assert.equal(resolve("auto"), "light");
  delete globalThis.matchMedia;
  assert.equal(resolve("auto"), "light");
});
