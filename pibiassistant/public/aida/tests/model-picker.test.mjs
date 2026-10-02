import test from "node:test";
import assert from "node:assert/strict";

const mem = new Map();
globalThis.localStorage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, v), removeItem: (k) => mem.delete(k) };
globalThis.document = { addEventListener() {}, removeEventListener() {} };
const { setMessages } = await import("../js/lib/i18n.js");
setMessages({});
const { store } = await import("../js/lib/store.js");
const { loadModels } = await import("../js/components/model-picker.js");
const { tiles } = await import("../js/components/suggestions.js");

const reply = (models) => async () => ({
  ok: true, status: 200, headers: { get: () => "application/json" },
  json: async () => ({ message: { models, auto_mode: { description: "" } } }),
  text: async () => JSON.stringify({ message: { models, auto_mode: { description: "" } } }),
});

test("a failed model list keeps the saved model", async () => {
  mem.set("aida_selected_model", "gpt-5-mini");
  store.set({ selectedModel: "gpt-5-mini" });
  globalThis.fetch = async () => { throw new TypeError("network"); };
  const err = console.error; console.error = () => {};
  await loadModels();
  console.error = err;
  assert.equal(store.get().modelsState, "error");
  assert.equal(store.get().selectedModel, "gpt-5-mini");
  assert.equal(mem.get("aida_selected_model"), "gpt-5-mini");
});

test("a successful list without the model resets to auto", async () => {
  globalThis.fetch = reply([{ model_id: "other", display_name: "Other", provider: "x" }]);
  await loadModels();
  assert.equal(store.get().modelsState, "ready");
  assert.equal(store.get().selectedModel, "auto");
});

test("welcome tiles are ERP starters with prompts", () => {
  const t = tiles();
  assert.equal(t.length, 4);
  assert.ok(t.every((x) => x.prompt && x.title && x.icon));
});
