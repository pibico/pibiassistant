import test from "node:test";
import assert from "node:assert/strict";
import { __, setMessages, getLang } from "../js/lib/i18n.js";

test("translates and falls back to the source", () => {
  setMessages({ Settings: "Ajustes" });
  assert.equal(__("Settings"), "Ajustes");
  assert.equal(__("Unknown"), "Unknown");
});

test("replaces placeholders", () => {
  setMessages({ "Show All ({0})": "Mostrar todos ({0})" });
  assert.equal(__("Show All ({0})", 7), "Mostrar todos (7)");
  assert.equal(__("{0} / {1}", 1, 2), "1 / 2");
  assert.equal(__("{0} and {1}", "a"), "a and {1}");
});

test("reads the boot global when no override is set", () => {
  setMessages(null);
  globalThis.aida_messages = { Dark: "Oscuro" };
  globalThis.aida_lang = "es";
  assert.equal(__("Dark"), "Oscuro");
  assert.equal(getLang(), "es");
  delete globalThis.aida_messages;
  delete globalThis.aida_lang;
  assert.equal(getLang(), "en");
});
