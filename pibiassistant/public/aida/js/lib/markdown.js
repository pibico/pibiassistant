import { h, clear } from "./dom.js";
import { parseInline, safeHref } from "./markdown-inline.js";

export { safeHref };

const MAX_QUOTE_DEPTH = 8;
const MAX_SOURCE = 100000;

const FENCE = /^ {0,3}(`{3,}|~{3,})\s*([\w+#.-]*)[^`]*$/;
const HEADING = /^ {0,3}(#{1,6})\s+(.*)$/;
const HR = /^ {0,3}([-*_])(?:\s*\1){2,}\s*$/;
const QUOTE = /^ {0,3}>\s?(.*)$/;
const ITEM = /^( *)([-*+]|\d{1,9}[.)])\s+(.*)$/;
const TABLE_SEP = /^\s*\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?\s*$/;

function headingText(raw) {
  let end = raw.length;
  while (end > 0 && /\s/.test(raw[end - 1])) end--;
  let cut = end;
  while (cut > 0 && raw[cut - 1] === "#") cut--;
  if (cut < end && cut > 0 && /\s/.test(raw[cut - 1])) {
    end = cut;
    while (end > 0 && /\s/.test(raw[end - 1])) end--;
  }
  return raw.slice(0, end);
}

function splitRow(line) {
  let t = line.trim();
  if (t.startsWith("|")) t = t.slice(1);
  if (t.endsWith("|") && !t.endsWith("\\|")) t = t.slice(0, -1);
  return t.split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|"));
}

function alignOf(cell) {
  const left = cell.startsWith(":");
  const right = cell.endsWith(":");
  if (left && right) return "center";
  return right ? "right" : left ? "left" : null;
}

function isTableStart(line, next) {
  return line.includes("|") && next !== undefined && next.includes("-") && TABLE_SEP.test(next);
}

function startsBlock(line, next) {
  return (
    FENCE.test(line) ||
    HEADING.test(line) ||
    HR.test(line) ||
    QUOTE.test(line) ||
    ITEM.test(line) ||
    isTableStart(line, next)
  );
}

function readFence(lines, i, match) {
  const fence = match[1];
  const body = [];
  const closer = new RegExp("^ {0,3}" + fence[0] + "{" + fence.length + ",}\\s*$");
  i++;
  while (i < lines.length && !closer.test(lines[i])) body.push(lines[i++]);
  return { block: { type: "code", lang: match[2], text: body.join("\n") }, next: i + 1 };
}

function readTable(lines, i) {
  const head = splitRow(lines[i]);
  const seps = splitRow(lines[i + 1]);
  if (head.length !== seps.length) return null;
  const rows = [];
  let j = i + 2;
  while (j < lines.length && lines[j].trim() && lines[j].includes("|")) {
    const cells = splitRow(lines[j++]);
    while (cells.length < head.length) cells.push("");
    rows.push(cells.slice(0, head.length).map((c) => parseInline(c)));
  }
  return {
    block: { type: "table", align: seps.map(alignOf), head: head.map((c) => parseInline(c)), rows },
    next: j,
  };
}

const MAX_LIST_DEPTH = 6;
const indentOf = (line) => /^ */.exec(line)[0].length;

function readList(lines, i, depth = 0) {
  const first = ITEM.exec(lines[i]);
  const base = first[1].length;
  const ordered = /\d/.test(first[2]);
  const items = [];
  const subs = [];
  let sub = [];
  const flush = () => {
    if (!sub.length) return;
    const cut = indentOf(sub[0]);
    const body = sub.map((l) => l.slice(Math.min(cut, indentOf(l))));
    subs[subs.length - 1] = readList(body, 0, depth + 1).block;
    sub = [];
  };
  let j = i;
  while (j < lines.length) {
    const m = ITEM.exec(lines[j]);
    const indent = m ? m[1].length : indentOf(lines[j]);
    if (m && indent > base && depth < MAX_LIST_DEPTH) {
      sub.push(lines[j++]);
    } else if (m && indent > base) {
      items[items.length - 1] += "\n" + lines[j++].trim();
    } else if (m) {
      if (/\d/.test(m[2]) !== ordered && indent === base) break;
      flush();
      items.push(m[3]);
      subs.push(null);
      j++;
    } else if (lines[j].trim() === "") {
      let k = j + 1;
      while (k < lines.length && lines[k].trim() === "") k++;
      const nextItem = k < lines.length && ITEM.exec(lines[k]);
      if (!nextItem || (nextItem[1].length <= base && /\d/.test(nextItem[2]) !== ordered)) break;
      if (sub.length) sub.push(...lines.slice(j, k));
      j = k;
    } else if (sub.length && indent > base) {
      sub.push(lines[j++]);
    } else if (/^\s{2,}\S/.test(lines[j]) && !startsBlock(lines[j].trim(), lines[j + 1])) {
      items[items.length - 1] += "\n" + lines[j].trim();
      j++;
    } else break;
  }
  flush();
  const start = ordered ? parseInt(first[2], 10) : 1;
  return { block: { type: "list", ordered, start, items: items.map((t) => parseInline(t)), subs }, next: j };
}

function readQuote(lines, i, depth) {
  const inner = [];
  let j = i;
  while (j < lines.length && QUOTE.test(lines[j])) inner.push(QUOTE.exec(lines[j++])[1]);
  return { block: { type: "quote", children: parseLines(inner, depth + 1) }, next: j };
}

function readParagraph(lines, i) {
  const text = [lines[i]];
  let j = i + 1;
  while (j < lines.length && lines[j].trim() && !startsBlock(lines[j], lines[j + 1])) text.push(lines[j++]);
  return { block: { type: "paragraph", children: parseInline(text.map((l) => l.trim()).join("\n")) }, next: j };
}

function readBlock(lines, i, depth) {
  const line = lines[i];
  let m = FENCE.exec(line);
  if (m) return readFence(lines, i, m);
  m = HEADING.exec(line);
  if (m) return { block: { type: "heading", level: m[1].length, children: parseInline(headingText(m[2])) }, next: i + 1 };
  if (HR.test(line)) return { block: { type: "hr" }, next: i + 1 };
  if (depth < MAX_QUOTE_DEPTH && QUOTE.test(line)) return readQuote(lines, i, depth);
  if (ITEM.test(line)) return readList(lines, i);
  if (isTableStart(line, lines[i + 1])) {
    const table = readTable(lines, i);
    if (table) return table;
  }
  return readParagraph(lines, i);
}

function parseLines(lines, depth = 0) {
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    if (!lines[i].trim()) {
      i++;
      continue;
    }
    const { block, next } = readBlock(lines, i, depth);
    blocks.push(block);
    i = next;
  }
  return blocks;
}

function plainBlocks(text) {
  return text
    .split(/\n{2,}/)
    .filter((p) => p.trim())
    .map((p) => ({ type: "paragraph", children: [{ type: "text", text: p }] }));
}

export function parse(src) {
  const text = String(src || "").replace(/\r\n?/g, "\n");
  if (text.length > MAX_SOURCE) return plainBlocks(text);
  return parseLines(text.split("\n"));
}

function isExternal(href) {
  if (!/^https?:/i.test(href)) return false;
  try {
    return new URL(href).origin !== globalThis.location.origin;
  } catch {
    return true;
  }
}

function inlineNode(n) {
  switch (n.type) {
    case "text":
      return n.text;
    case "br":
      return h("br");
    case "code":
      return h("code", null, n.text);
    case "strong":
    case "em":
    case "del":
      return h(n.type, null, n.children.map(inlineNode));
    case "link": {
      const attrs = { href: n.href, rel: "noopener noreferrer" };
      if (isExternal(n.href)) attrs.target = "_blank";
      return h("a", attrs, n.children.map(inlineNode));
    }
    default:
      return null;
  }
}

function inlines(list) {
  return list.map(inlineNode);
}

function tableNode(b) {
  const cell = (tag, c, i) => h(tag, b.align[i] ? { style: { textAlign: b.align[i] } } : null, inlines(c));
  return h(
    "div",
    { class: "aida-md__table-wrap" },
    h(
      "table",
      null,
      h("thead", null, h("tr", null, b.head.map((c, i) => cell("th", c, i)))),
      h("tbody", null, b.rows.map((r) => h("tr", null, r.map((c, i) => cell("td", c, i))))),
    ),
  );
}

function blockNode(b) {
  switch (b.type) {
    case "heading":
      return h("h" + b.level, null, inlines(b.children));
    case "paragraph":
      return h("p", null, inlines(b.children));
    case "hr":
      return h("hr");
    case "quote":
      return h("blockquote", null, b.children.map(blockNode));
    case "list": {
      const attrs = b.ordered && b.start !== 1 ? { start: b.start } : null;
      return h(b.ordered ? "ol" : "ul", attrs, b.items.map((it, i) => h("li", null, inlines(it), b.subs[i] ? blockNode(b.subs[i]) : null)));
    }
    case "code":
      return h(
        "div",
        { class: "aida-md__code" },
        b.lang ? h("div", { class: "aida-md__code-head" }, b.lang) : null,
        h("pre", null, h("code", null, b.text)),
      );
    case "table":
      return tableNode(b);
    default:
      return null;
  }
}

export function render(src) {
  const frag = document.createDocumentFragment();
  for (const b of parse(src)) frag.append(blockNode(b));
  return frag;
}

export function renderInto(container, src) {
  clear(container);
  try {
    container.append(render(src));
  } catch {
    container.textContent = String(src || "");
  }
  return container;
}
