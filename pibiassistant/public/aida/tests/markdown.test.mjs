import test from "node:test";
import assert from "node:assert/strict";
import { parse, safeHref, render } from "../js/lib/markdown.js";
import { parseInline } from "../js/lib/markdown-inline.js";

const types = (nodes) => nodes.map((n) => n.type);

test("headings, hr, paragraphs", () => {
  const b = parse("# Title\n\ntext line\nsecond\n\n---\n\n###### six");
  assert.deepEqual(types(b), ["heading", "paragraph", "hr", "heading"]);
  assert.equal(b[0].level, 1);
  assert.equal(b[3].level, 6);
  assert.deepEqual(types(b[1].children), ["text", "br", "text"]);
});

test("inline emphasis, code, strike", () => {
  const n = parseInline("**b** *i* ~~s~~ `c` __b2__ _i2_");
  assert.deepEqual(types(n).filter((t) => t !== "text"), ["strong", "em", "del", "code", "strong", "em"]);
  assert.equal(n.find((x) => x.type === "code").text, "c");
});

test("nested emphasis and intraword underscores", () => {
  const n = parseInline("**bold *em* x**");
  assert.equal(n[0].type, "strong");
  assert.ok(n[0].children.some((c) => c.type === "em"));
  const snake = parseInline("snake_case_name");
  assert.deepEqual(types(snake), ["text"]);
  const triple = parseInline("***both***");
  assert.equal(triple[0].type, "em");
  assert.equal(triple[0].children[0].type, "strong");
});

test("unmatched delimiters stay literal", () => {
  assert.deepEqual(parseInline("2 * 3 = 6 and **open"), [{ type: "text", text: "2 * 3 = 6 and **open" }]);
});

test("fenced code keeps language, raw content and survives unterminated fences", () => {
  const b = parse("```js\nconst a = <b>1</b>;\n```\nafter");
  assert.equal(b[0].type, "code");
  assert.equal(b[0].lang, "js");
  assert.equal(b[0].text, "const a = <b>1</b>;");
  assert.equal(b[1].type, "paragraph");
  const open = parse("```py\nprint(1)\nmore");
  assert.equal(open.length, 1);
  assert.equal(open[0].text, "print(1)\nmore");
  assert.deepEqual(parse("```")[0], { type: "code", lang: "", text: "" });
});

test("lists", () => {
  const ul = parse("- a\n- b\n* c")[0];
  assert.equal(ul.type, "list");
  assert.equal(ul.ordered, false);
  assert.equal(ul.items.length, 3);
  const ol = parse("3. x\n4. y")[0];
  assert.equal(ol.ordered, true);
  assert.equal(ol.start, 3);
  const nested = parse("- a\n  - b\n- c")[0];
  assert.equal(nested.items.length, 3);
  assert.deepEqual(types(parse("intro:\n- a\n- b")), ["paragraph", "list"]);
});

test("blockquote", () => {
  const q = parse("> quote **x**\n> more")[0];
  assert.equal(q.type, "quote");
  assert.equal(q.children[0].type, "paragraph");
});

test("tables with alignment", () => {
  const t = parse("| a | b | c |\n|:--|:-:|--:|\n| 1 | 2 | 3 |\n| 4 | 5 |")[0];
  assert.equal(t.type, "table");
  assert.deepEqual(t.align, ["left", "center", "right"]);
  assert.equal(t.head.length, 3);
  assert.equal(t.rows.length, 2);
  assert.equal(t.rows[1].length, 3);
});

test("links and autolinks", () => {
  const n = parseInline("[site](https://example.com/a) and https://example.org/x, done.");
  const links = n.filter((x) => x.type === "link");
  assert.equal(links[0].href, "https://example.com/a");
  assert.equal(links[1].href, "https://example.org/x");
  assert.equal(n[n.length - 1].text, ", done.");
});

test("a link inside a link label does not nest anchors", () => {
  const n = parseInline("[https://a.com](https://a.com)");
  assert.equal(n.length, 1);
  assert.deepEqual(types(n[0].children), ["text"]);
});

test("safeHref allow and deny lists", () => {
  for (const ok of ["https://a.com/x?y=1", "http://a.com", "mailto:a@b.com", "/aida/chat", "/x#y"]) {
    assert.equal(safeHref(ok), ok, ok);
  }
  for (const bad of [
    "javascript:alert(1)", "JaVaScRiPt:alert(1)", " javascript:alert(1)", "java\tscript:alert(1)", "java\nscript:alert(1)",
    "data:text/html,<script>alert(1)</script>", "vbscript:x", "//evil.com", "/\\evil.com", "\\\\evil.com", "file:///etc/passwd",
    "ftp://a.com", "relative/path", "https://", "http:evil.com", "", null, undefined, "https://a.com/ b",
  ]) {
    assert.equal(safeHref(bad), null, String(bad));
  }
});

test("XSS corpus stays inert text", () => {
  const payloads = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "[x](javascript:alert(1))",
    "[x](data:text/html;base64,PHNjcmlwdD4=)",
    "[x](//evil.com)",
    '[x](https://a.com" onmouseover="alert(1))',
    "<a href=\"javascript:alert(1)\">x</a>",
    "<div onclick=alert(1)>x</div>",
  ];
  for (const p of payloads) {
    const links = [];
    const walk = (nodes) => nodes.forEach((n) => {
      if (n.type === "link") links.push(n.href);
      if (n.children) walk(n.children);
    });
    parse(p).forEach((b) => b.children && walk(b.children));
    for (const href of links) assert.ok(safeHref(href), href);
    assert.ok(!links.some((h) => /javascript|data:|^\/\//i.test(h)), p);
  }
  const html = parse("<script>alert(1)</script>")[0];
  assert.equal(html.children[0].text, "<script>alert(1)</script>");
});

test("images are never emitted", () => {
  const n = parseInline("![alt text](https://x.com/a.png) ![](data:image/png;base64,AAAA)");
  assert.ok(n.every((x) => x.type === "text"));
  assert.match(n[0].text, /alt text/);
});

test("escapes", () => {
  assert.deepEqual(parseInline("\\*not em\\*"), [{ type: "text", text: "*not em*" }]);
});

test("pathological input terminates", () => {
  const t0 = Date.now();
  parse("*".repeat(4000));
  parse("[".repeat(3000) + "](" + "(".repeat(3000));
  parse("`".repeat(3000));
  assert.ok(Date.now() - t0 < 3000);
});

class FakeNode {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attrs = {};
    this.style = { setProperty() {} };
  }
  append(...items) {
    for (const i of items) this.children.push(typeof i === "string" ? { text: i } : i);
  }
  replaceChildren() {
    this.children = [];
  }
  setAttribute(k, v) {
    this.attrs[k] = v;
  }
  addEventListener() {}
}
const ser = (n) => {
  if (n.text !== undefined) return n.text.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const a = Object.entries(n.attrs).map(([k, v]) => ` ${k}="${v}"`).join("");
  return `<${n.tag}${a}>${n.children.map(ser).join("")}</${n.tag}>`;
};

test("render emits only whitelisted tags with safe links", () => {
  globalThis.document = {
    createElement: (t) => new FakeNode(t),
    createDocumentFragment: () => new FakeNode("#frag"),
  };
  globalThis.location = { origin: "https://demo.pibico.es" };
  const out = render("# T\n\n[a](https://other.com) [b](/aida/chat) [c](javascript:x) <script>x</script>\n\n```js\n<b>\n```\n\n| h |\n|---|\n| c |");
  const html = out.children.map(ser).join("");
  assert.match(html, /<a href="https:\/\/other.com" rel="noopener noreferrer" target="_blank">a<\/a>/);
  assert.match(html, /<a href="\/aida\/chat" rel="noopener noreferrer">b<\/a>/);
  assert.doesNotMatch(html, /javascript:/);
  assert.match(html, /&lt;script>x&lt;\/script>/);
  const tags = [...html.matchAll(/<([a-z0-9]+)[ >]/g)].map((m) => m[1]);
  const allowed = new Set(["h1","p","a","br","div","pre","code","table","thead","tbody","tr","th","td"]);
  assert.ok(tags.every((t) => allowed.has(t)), tags.join());
  assert.match(html, /<div class="aida-md__table-wrap">/);
  delete globalThis.document;
  delete globalThis.location;
});

test("pathological input stays bounded", async () => {
  const { parse } = await import("../js/lib/markdown.js");
  const t = Date.now();
  parse(">".repeat(5000) + "a");
  parse("*a ".repeat(16000));
  parse("[a](".repeat(12000));
  parse("x".repeat(200000));
  assert.ok(Date.now() - t < 2000);
});
