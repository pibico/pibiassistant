import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const WIDGET = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../chat/widget");
const files = (ext) => fs.readdirSync(WIDGET).filter((f) => f.endsWith(ext)).map((f) => [f, fs.readFileSync(path.join(WIDGET, f), "utf8")]);
const stripComments = (s) => s.replace(/\/\*[\s\S]*?\*\//g, "");

test("widget CSS keeps guideline line-height (no declaration above 1.2)", () => {
  const bad = [];
  for (const [f, s] of files(".css")) {
    for (const m of stripComments(s).matchAll(/line-height:\s*(\d+(?:\.\d+)?)\s*;/g)) if (Number(m[1]) > 1.2) bad.push(`${f}: ${m[0]}`);
  }
  assert.deepEqual(bad, []);
});

test("widget CSS has no hex or rgb fallback inside --pao tokens and no undefined tokens", () => {
  const bad = [];
  for (const [f, s] of files(".css")) {
    for (const m of s.matchAll(/var\(--pao-[a-z0-9-]+,\s*(?:#|rgb)/g)) bad.push(`${f}: ${m[0]}`);
    for (const m of s.matchAll(/var\(--pao-(?:hover-bg|text-color|text|bg|accent)[,)]/g)) bad.push(`${f}: ${m[0]}`);
  }
  assert.deepEqual(bad, []);
});

test("widget CSS has no off-palette dark green and no duplicate keyframes", () => {
  const seen = new Map();
  for (const [f, s] of files(".css")) {
    assert.ok(!/094539/i.test(s), `${f} uses #094539`);
    for (const m of s.matchAll(/@keyframes\s+([\w-]+)/g)) seen.set(m[1], (seen.get(m[1]) || 0) + 1);
  }
  assert.deepEqual([...seen].filter(([, n]) => n > 1), []);
});

test("widget JS uses PAOCore.escape_html, never the frappe one, and no italic inline styles", () => {
  const bad = [];
  for (const [f, s] of files(".js")) {
    if (/frappe\.utils\.escape_html/.test(s)) bad.push(`${f}: frappe.utils.escape_html`);
    if (/style="[^"]*font-style:\s*italic/.test(s)) bad.push(`${f}: inline italic`);
  }
  assert.deepEqual(bad, []);
});

test("the widget has a Stop control wired to cancel_stream and ignores IME Enter", () => {
  const w = fs.readFileSync(path.join(WIDGET, "widget.js"), "utf8");
  assert.match(w, /api\.cancel_stream/);
  assert.match(w, /isComposing/);
  assert.match(fs.readFileSync(path.join(WIDGET, "widget_streaming.js"), "utf8"), /case "stream_aborted"/);
  assert.match(fs.readFileSync(path.join(WIDGET, "widget_slash_menu.js"), "utf8"), /isComposing/);
});

test("PA Cloud routing chips are gone from the widget", () => {
  for (const [f, s] of [...files(".js"), ...files(".css")]) {
    assert.ok(!/render_routing_chip|PAOWidgetRouting|pao-routing-chip/.test(s), `${f} still references routing chips`);
  }
});

test("template placeholders are translatable", () => {
  const s = fs.readFileSync(path.join(WIDGET, "widget_templates.js"), "utf8");
  assert.match(s, /__\("Default: \{0\}"/);
  assert.match(s, /__\("Enter \{0\}…"/);
});

test("widget frappe.call sites are silent (no centered msgprint over the widget)", () => {
  const bad = [];
  for (const [f, s] of files(".js")) {
    if (f === "widget_browser_tools.js") continue;
    for (const m of s.matchAll(/frappe\.call\(\{\s*\n(\s*)([^\n]*)/g)) if (!/^silent: true,/.test(m[2])) bad.push(`${f}: ${m[2]}`);
  }
  assert.deepEqual(bad, []);
});

test("widget CSS drops off-palette status colours and the routing asset is gone", () => {
  const bad = [];
  for (const [f, s] of files(".css")) {
    for (const m of s.matchAll(/#(?:ef4444|dc2626|16a34a|22c55e|10b981|f59e0b|6e6e76)\b/gi)) bad.push(`${f}: ${m[0]}`);
  }
  assert.deepEqual(bad, []);
  assert.ok(!fs.existsSync(path.join(WIDGET, "widget_routing.js")));
});

test("widget send error reason avoids HTML parsing and slash menu delegates escaping", () => {
  const w = fs.readFileSync(path.join(WIDGET, "widget.js"), "utf8");
  assert.ok(!/\$\("<div>"\)\.html\(/.test(w));
  assert.match(w, /PAOCore\.server_error_text\(error\)/);
  const sm = fs.readFileSync(path.join(WIDGET, "widget_slash_menu.js"), "utf8");
  assert.match(sm, /return PAOCore\.escape_html\(s\)/);
});

test("widget CSS has no off-palette Tailwind hexes, no mic-spin duplicate and a reduced-motion blanket", () => {
  const all = files(".css").map(([, s]) => s).join("\n");
  assert.equal(/#(92400e|065f46|166534|991b1b|78350f|fef3c7|f87171|fca5a5|fcd34d|6ee7b7|86efac)\b/i.test(all), false);
  assert.equal(all.includes("pao-mic-spin"), false);
  assert.match(all, /prefers-reduced-motion: reduce\)\s*\{\s*\.pao-widget,\s*\.pao-widget \*/);
});
