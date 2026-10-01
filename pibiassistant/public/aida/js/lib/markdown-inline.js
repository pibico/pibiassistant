const MAX_DEPTH = 8;
const SCAN_LIMIT = 4000;
const MAX_INLINE = 50000;
const PUNCT = /[!-/:-@[-`{-~]/;
const ALNUM = /[\p{L}\p{N}]/u;

export function safeHref(url) {
  if (typeof url !== "string") return null;
  const u = url.trim();
  if (!u || /[\u0000- \u007f-\u009f]/.test(u)) return null;
  if (/^https?:\/\/[^/?#]/i.test(u)) {
    try {
      new URL(u);
      return u;
    } catch {
      return null;
    }
  }
  if (/^mailto:[^\s]+$/i.test(u)) return u;
  if (u[0] === "/" && u[1] !== "/" && u[1] !== "\\") return u;
  return null;
}

function pushText(out, text) {
  if (!text) return;
  const last = out[out.length - 1];
  if (last && last.type === "text") last.text += text;
  else out.push({ type: "text", text });
}

function runLength(src, i, ch) {
  let n = 0;
  while (src[i + n] === ch) n++;
  return n;
}

function codeSpan(src, i) {
  const n = runLength(src, i, "`");
  let j = i + n;
  while (j < src.length) {
    const k = src.indexOf("`", j);
    if (k < 0) return null;
    const m = runLength(src, k, "`");
    if (m === n) {
      let text = src.slice(i + n, k).replace(/\n/g, " ");
      if (text.length > 2 && text.startsWith(" ") && text.endsWith(" ")) text = text.slice(1, -1);
      return { node: { type: "code", text }, end: k + m };
    }
    j = k + m;
  }
  return null;
}

function closingBracket(src, i) {
  let depth = 0;
  for (let j = i, end = Math.min(src.length, i + SCAN_LIMIT); j < end; j++) {
    const c = src[j];
    if (c === "\\") j++;
    else if (c === "[") depth++;
    else if (c === "]" && --depth === 0) return j;
  }
  return -1;
}

function linkTarget(src, i) {
  if (src[i] !== "(") return null;
  let depth = 0;
  for (let j = i, end = Math.min(src.length, i + SCAN_LIMIT); j < end; j++) {
    const c = src[j];
    if (c === "\\") j++;
    else if (c === "(") depth++;
    else if (c === ")" && --depth === 0) {
      const raw = src.slice(i + 1, j).trim().replace(/\s+"[^"]*"$/, "");
      const url = raw.startsWith("<") && raw.endsWith(">") ? raw.slice(1, -1) : raw;
      return { url, end: j + 1 };
    }
  }
  return null;
}

function bracketed(src, i, depth) {
  const close = closingBracket(src, i);
  if (close < 0) return null;
  const target = linkTarget(src, close + 1);
  if (!target) return null;
  const label = src.slice(i + 1, close);
  return { label, target, end: target.end, depth };
}

function unlink(nodes) {
  return nodes.flatMap((n) => {
    if (n.type === "link") return unlink(n.children);
    return n.children ? [{ ...n, children: unlink(n.children) }] : [n];
  });
}

function linkOrImage(src, i, depth) {
  const image = src[i] === "!";
  const found = bracketed(src, image ? i + 1 : i, depth);
  if (!found) return null;
  if (image) return { nodes: [{ type: "text", text: found.label || found.target.url }], end: found.end };
  const href = safeHref(found.target.url);
  const children = unlink(parseInline(found.label, depth + 1));
  return { nodes: href ? [{ type: "link", href, children }] : children, end: found.end };
}

function autolink(src, i) {
  const m = /^https?:\/\/[^\s<>]+/i.exec(src.slice(i));
  if (!m) return null;
  let url = m[0];
  for (;;) {
    const last = url[url.length - 1];
    const unbalanced = last === ")" && (url.match(/\)/g) || []).length > (url.match(/\(/g) || []).length;
    if (/[.,;:!?'"\]*_~]/.test(last) || unbalanced) url = url.slice(0, -1);
    else break;
  }
  const href = safeHref(url);
  if (!href) return null;
  return { node: { type: "link", href, children: [{ type: "text", text: url }] }, end: i + url.length };
}

function findCloser(src, from, ch, k) {
  for (let j = from, end = Math.min(src.length, from + SCAN_LIMIT); j < end; j++) {
    const c = src[j];
    if (c === "\\") j++;
    else if (c === "`") {
      const span = codeSpan(src, j);
      j = span ? span.end - 1 : j + runLength(src, j, "`") - 1;
    } else if (c === ch) {
      const m = runLength(src, j, ch);
      const prev = src[j - 1];
      const next = src[j + m];
      const okRun = k === 1 ? m === 1 : m >= k;
      const closes = prev && !/\s/.test(prev) && !(ch === "_" && next && ALNUM.test(next));
      if (j > from && okRun && closes) return j + m - k;
      j += m - 1;
    }
  }
  return -1;
}

function emphasis(src, i, depth, failed) {
  const ch = src[i];
  const n = runLength(src, i, ch);
  const prev = src[i - 1];
  const next = src[i + n];
  const opens = next && !/\s/.test(next) && !(ch === "_" && prev && ALNUM.test(prev));
  if (!opens || (ch === "~" && n < 2)) return { text: ch.repeat(n), end: i + n };
  const k = ch === "~" ? 2 : n >= 3 ? 3 : n;
  const tag = ch + k;
  const close = failed.has(tag) ? -1 : findCloser(src, i + k, ch, k);
  if (close < 0) failed.add(tag);
  if (close < 0) return { text: ch.repeat(n), end: i + n };
  const inner = parseInline(src.slice(i + k, close), depth + 1);
  let node;
  if (ch === "~") node = { type: "del", children: inner };
  else if (k === 3) node = { type: "em", children: [{ type: "strong", children: inner }] };
  else node = { type: k === 2 ? "strong" : "em", children: inner };
  return { node, end: close + k };
}

export function parseInline(src, depth = 0) {
  const out = [];
  if (depth > MAX_DEPTH || src.length > MAX_INLINE) {
    pushText(out, src);
    return out;
  }
  const failed = new Set();
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (c === "\\" && i + 1 < src.length && PUNCT.test(src[i + 1])) {
      pushText(out, src[i + 1]);
      i += 2;
    } else if (c === "\n") {
      out.push({ type: "br" });
      i++;
    } else if (c === "`") {
      const span = codeSpan(src, i);
      if (span) {
        out.push(span.node);
        i = span.end;
      } else {
        const n = runLength(src, i, "`");
        pushText(out, "`".repeat(n));
        i += n;
      }
    } else if (c === "!" && src[i + 1] === "[" || c === "[") {
      const res = linkOrImage(src, i, depth);
      if (res) {
        res.nodes.forEach((n) => (n.type === "text" ? pushText(out, n.text) : out.push(n)));
        i = res.end;
      } else {
        pushText(out, c);
        i++;
      }
    } else if ((c === "h" || c === "H") && !(i > 0 && ALNUM.test(src[i - 1])) && autolink(src, i)) {
      const res = autolink(src, i);
      out.push(res.node);
      i = res.end;
    } else if (c === "*" || c === "_" || c === "~") {
      const res = emphasis(src, i, depth, failed);
      if (res.node) out.push(res.node);
      else pushText(out, res.text);
      i = res.end;
    } else {
      let j = i + 1;
      while (j < src.length && !"\\\n`![*_~hH".includes(src[j])) j++;
      pushText(out, src.slice(i, j));
      i = j;
    }
  }
  return out;
}
