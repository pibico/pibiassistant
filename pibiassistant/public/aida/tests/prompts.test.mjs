import test from "node:test";
import assert from "node:assert/strict";
import { setMessages } from "../js/lib/i18n.js";
import * as p from "../js/lib/prompts.js";

setMessages({});

const templates = [
  { name: "sales", title: "Sales analysis", description: "Revenue by customer", arguments: [{ name: "time_period" }] },
  { name: "hr", title: "HR analysis", description: "Workforce" },
  { name: "docs", title: "Documentation", description: "Describe a DocType" },
];

test("slashQuery only in slash mode at position 0 without whitespace", () => {
  assert.equal(p.slashQuery("/"), "");
  assert.equal(p.slashQuery("/sal"), "sal");
  assert.equal(p.slashQuery("/sal now"), null);
  assert.equal(p.slashQuery("hi /sal"), null);
  assert.equal(p.slashQuery(""), null);
});

test("filterTemplates matches title, name and description with pinned first", () => {
  const cat = p.normalizeCatalog({ templates, pinned: ["docs"] });
  assert.deepEqual(p.filterTemplates(cat, "").map((t) => t.name), ["docs", "sales", "hr"]);
  assert.deepEqual(p.filterTemplates(cat, "REVENUE").map((t) => t.name), ["sales"]);
  assert.deepEqual(p.filterTemplates(cat, "hr").map((t) => t.name), ["hr"]);
  assert.deepEqual(p.filterTemplates(cat, "zzz"), []);
});

test("normalizeCatalog tolerates garbage and error payloads", () => {
  assert.deepEqual(p.normalizeCatalog(null), { templates: [], pinned: [] });
  assert.deepEqual(p.normalizeCatalog({ templates: [null, { title: "x" }], error: "boom" }), { templates: [], pinned: [] });
});

test("argsOf, labelOf and fieldKind", () => {
  const args = p.argsOf({ arguments: [{ name: "doctype_name" }, { description: "x", required: false }] });
  assert.equal(args[0].required, true);
  assert.equal(args[1].name, "arg_1");
  assert.equal(args[1].required, false);
  assert.equal(p.labelOf("time_period"), "Time Period");
  assert.equal(p.fieldKind({ name: "scope", enum: ["a"] }), "select");
  assert.equal(p.fieldKind({ name: "doc_description" }), "textarea");
  assert.equal(p.fieldKind({ name: "n", type: "integer" }), "number");
  assert.equal(p.fieldKind({ name: "mail", type: "email" }), "email");
  assert.equal(p.fieldKind({ name: "x" }), "text");
});

test("fallbackPrompt keeps the pick when the render call fails", () => {
  assert.equal(p.fallbackPrompt(templates[0], { time_period: "Q1", empty: "" }), "Revenue by customer (time_period: Q1)");
});
