import { isValidSessionId } from "./lib/format.js";

export const SETTINGS_PATH = "/aida/settings";
const CHAT_PATH = "/aida/chat";

const listeners = new Set();
let route = { name: "chat", sessionId: null, canonical: CHAT_PATH };

export function chatPath(id) {
  return id ? `${CHAT_PATH}/${id}` : CHAT_PATH;
}

export function parse(pathname) {
  const path = String(pathname || "").split(/[?#]/)[0];
  const seg = path.split("/").filter(Boolean);
  if (seg[0] === "aida" && seg.length === 2 && seg[1] === "settings") {
    return { name: "settings", sessionId: null, canonical: SETTINGS_PATH };
  }
  if (seg[0] === "aida" && seg.length === 3 && seg[1] === "chat" && isValidSessionId(seg[2])) {
    return { name: "chat", sessionId: seg[2], canonical: chatPath(seg[2]) };
  }
  return { name: "chat", sessionId: null, canonical: CHAT_PATH };
}

export function onRoute(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify() {
  for (const fn of [...listeners]) {
    try {
      fn(route);
    } catch {
      continue;
    }
  }
}

export function navigate(path, { replace = false } = {}) {
  route = parse(path);
  const same = location.pathname === route.canonical && !location.search && !location.hash;
  if (replace || same) history.replaceState(null, "", route.canonical);
  else history.pushState(null, "", route.canonical);
  notify();
}

export function replaceUrl(path) {
  route = parse(path);
  history.replaceState(null, "", route.canonical);
}

function onClick(e) {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = e.target instanceof Element ? e.target.closest("a[href]") : null;
  if (!a || (a.target && a.target !== "_self") || a.hasAttribute("download")) return;
  const url = new URL(a.href, location.href);
  if (url.origin !== location.origin) return;
  if (url.pathname !== "/aida" && !url.pathname.startsWith("/aida/")) return;
  e.preventDefault();
  navigate(url.pathname);
}

export function start() {
  route = parse(location.pathname);
  if (location.pathname !== route.canonical || location.search || location.hash) {
    history.replaceState(null, "", route.canonical);
  }
  document.addEventListener("click", onClick);
  window.addEventListener("popstate", () => {
    route = parse(location.pathname);
    notify();
  });
  notify();
}
