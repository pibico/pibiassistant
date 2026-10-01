import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ES_CSV = path.resolve(ROOT, "../../translations/es.csv");

function walk(dir, ext) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) return walk(p, ext);
    return p.endsWith(ext) ? [p] : [];
  });
}

const jsFiles = walk(path.join(ROOT, "js"), ".js");
const cssFiles = walk(path.join(ROOT, "css"), ".css");
const read = (f) => fs.readFileSync(f, "utf8");
const rel = (f) => path.relative(ROOT, f);

function offenders(files, regex) {
  return files.filter((f) => regex.test(read(f))).map(rel);
}

test("js has no unsafe DOM or code execution APIs", () => {
  const banned = [
    /\.innerHTML\b/, /\.outerHTML\b/, /insertAdjacentHTML/, /document\.write/, /\beval\s*\(/,
    /new\s+Function\b/, /set(?:Timeout|Interval)\s*\(\s*["'`]/, /<[a-z][^>]*\son[a-z]+\s*=/i,
  ];
  for (const re of banned) assert.deepEqual(offenders(jsFiles, re), [], String(re));
});

test("css rules: no serif, no !important, no 100vh, no external urls, no foreign fonts", () => {
  const serif = cssFiles.filter((f) => /(?<!sans-)serif/i.test(read(f)) || /Georgia|Times|Playfair/.test(read(f)));
  assert.deepEqual(serif.map(rel), []);
  assert.deepEqual(offenders(cssFiles, /!important/), []);
  assert.deepEqual(offenders(cssFiles, /100vh/), []);
  assert.deepEqual(offenders(cssFiles, /https?:\/\//), []);
});

test("js contains no hard-coded http urls", () => {
  assert.deepEqual(offenders(jsFiles, /["'`]https?:\/\/(?!www\.w3\.org\/2000\/svg)[^"'`]/), []);
});

test("every var(--aida-*) used in css is defined in tokens.css", () => {
  const defined = new Set([...read(path.join(ROOT, "css/tokens.css")).matchAll(/(--aida-[\w-]+)\s*:/g)].map((m) => m[1]));
  const missing = [];
  for (const f of cssFiles) {
    for (const m of read(f).matchAll(/var\((--aida-[\w-]+)/g)) {
      if (!defined.has(m[1])) missing.push(`${rel(f)} ${m[1]}`);
    }
  }
  assert.deepEqual([...new Set(missing)], []);
});

test("css class names are aida- prefixed", () => {
  const bad = [];
  for (const f of cssFiles.filter((x) => !x.endsWith("tokens.css") && !x.endsWith("fonts.css"))) {
    const stripped = read(f).replace(/\{[^{}]*\}/g, "{}").replace(/\([^)]*\)/g, "");
    for (const m of stripped.matchAll(/\.([A-Za-z_][\w-]*)/g)) {
      if (!m[1].startsWith("aida-") && !m[1].startsWith("is-")) bad.push(`${rel(f)} .${m[1]}`);
    }
  }
  assert.deepEqual([...new Set(bad)], []);
});

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        field += '"';
        i++;
      } else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else field += c;
  }
  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

test("every __() source string has a Spanish row (or is an identity word)", () => {
  const sources = new Set(parseCsv(read(ES_CSV)).map((r) => r[0]));
  const identity = new Set(["AIDA", "Chat"]);
  const missing = [];
  for (const f of jsFiles) {
    for (const m of read(f).matchAll(/\b__\(\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g)) {
      const text = m[1][0] === '"' ? JSON.parse(m[1]) : m[1].slice(1, -1).replace(/\\'/g, "'");
      if (!identity.has(text) && !sources.has(text)) missing.push(`${rel(f)}: ${text}`);
    }
  }
  assert.deepEqual(missing, []);
});

test("every relative import resolves to an existing file", () => {
  const broken = [];
  for (const f of jsFiles) {
    for (const m of read(f).matchAll(/(?:from|import)\s*\(?\s*["'](\.[^"']+)["']/g)) {
      if (!fs.existsSync(path.resolve(path.dirname(f), m[1]))) broken.push(`${rel(f)} -> ${m[1]}`);
    }
  }
  assert.deepEqual(broken, []);
});
