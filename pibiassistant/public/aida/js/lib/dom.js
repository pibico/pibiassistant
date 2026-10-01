const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
const DIRECT_PROPS = new Set(["value", "checked", "disabled", "hidden"]);

function classOf(v) {
  return (Array.isArray(v) ? v : [v]).filter(Boolean).join(" ");
}

function applyAttr(el, key, val) {
  if (val === null || val === undefined || val === false) return;
  if (key === "class") {
    const c = classOf(val);
    if (c) el.setAttribute("class", c);
  } else if (key === "dataset") {
    for (const k of Object.keys(val)) el.dataset[k] = val[k];
  } else if (key === "style") {
    for (const k of Object.keys(val)) {
      if (k.startsWith("--")) el.style.setProperty(k, val[k]);
      else el.style[k] = val[k];
    }
  } else if (key.startsWith("on") && (typeof val === "function" || Array.isArray(val))) {
    const [fn, opts] = Array.isArray(val) ? val : [val];
    el.addEventListener(key.slice(2).toLowerCase(), fn, opts);
  } else if (DIRECT_PROPS.has(key)) {
    el[key] = val;
  } else if (val === true) {
    el.setAttribute(key, "");
  } else {
    el.setAttribute(key, String(val));
  }
}

function appendChild(el, child) {
  if (child === null || child === undefined || typeof child === "boolean") return;
  if (Array.isArray(child)) child.forEach((c) => appendChild(el, c));
  else if (typeof child === "string" || typeof child === "number") el.append(String(child));
  else el.append(child);
}

export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  if (attrs) for (const key of Object.keys(attrs)) applyAttr(el, key, attrs[key]);
  appendChild(el, children);
  return el;
}

export function clear(el) {
  el.replaceChildren();
  return el;
}

export function qs(sel, root = document) {
  return root.querySelector(sel);
}

export function qsa(sel, root = document) {
  return Array.from(root.querySelectorAll(sel));
}

export function focusables(root) {
  return qsa(FOCUSABLE, root).filter((el) => !el.hidden && el.getClientRects().length > 0);
}

export function trapFocus(root) {
  function onKey(e) {
    if (e.key !== "Tab") return;
    const items = focusables(root);
    if (!items.length) {
      e.preventDefault();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (e.shiftKey && (active === first || !root.contains(active))) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && (active === last || !root.contains(active))) {
      e.preventDefault();
      first.focus();
    }
  }
  document.addEventListener("keydown", onKey);
  return () => document.removeEventListener("keydown", onKey);
}

function fallbackCopy(text) {
  const ta = h("textarea", { "aria-hidden": "true", style: { position: "fixed", opacity: "0" } });
  ta.value = text;
  document.body.append(ta);
  ta.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  }
  ta.remove();
  return ok;
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return fallbackCopy(text);
  }
}

export function isCoarse() {
  return window.matchMedia("(hover: none), (pointer: coarse)").matches;
}
