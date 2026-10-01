import { __, getLang } from "./i18n.js";

const DAY = 86400000;

export function parseServerTs(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (value instanceof Date) return value.getTime();
  if (typeof value === "string") {
    const iso = /^\d{4}-\d{2}-\d{2} /.test(value) ? value.replace(" ", "T") : value;
    const ms = new Date(iso).getTime();
    if (!Number.isNaN(ms)) return ms;
  }
  return Date.now();
}

export function formatTime(ms, now = Date.now(), lang = getLang()) {
  const d = new Date(ms);
  if (d.toDateString() === new Date(now).toDateString()) {
    return d.toLocaleTimeString(lang, { hour: "numeric", minute: "2-digit" });
  }
  return d.toLocaleDateString(lang, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function isoOf(ms) {
  return new Date(ms).toISOString();
}

export function tokensPerSecond(completionTokens, durationMs) {
  if (!(completionTokens > 0) || !(durationMs > 0)) return null;
  return (completionTokens / (durationMs / 1000)).toFixed(1);
}

export function stripProvider(model) {
  if (!model || model === "auto") return null;
  const i = model.indexOf("/");
  return i >= 0 ? model.slice(i + 1) : model;
}

export function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function truncate(text, max) {
  const t = String(text || "").trim().replace(/\s+/g, " ");
  return t.length > max ? t.slice(0, max - 1).trimEnd() + "…" : t;
}

export function stripStopMarker(content) {
  return String(content || "").replace(/\n*_\(Stopped by user\)_\s*$/, "");
}

function numberOrNull(v) {
  const n = Number(v);
  return n > 0 ? n : null;
}

function contentFromBlocks(raw) {
  if (!raw) return "";
  try {
    const blocks = JSON.parse(raw);
    if (!Array.isArray(blocks)) return "";
    return blocks
      .filter((b) => b && b.type === "text" && !b._abortMarker && typeof b.content === "string")
      .map((b) => b.content)
      .join("");
  } catch {
    return "";
  }
}

export function fromHistoryRow(row) {
  if (!row || (row.role !== "user" && row.role !== "assistant")) return null;
  const attached = new Map();
  for (const a of Array.isArray(row.attachments) ? row.attachments : []) {
    const url = a.file_url || "";
    if (!attached.has(url)) attached.set(url, { name: a.file_name || a.name || "", url });
  }
  const files = [...attached.values()];
  const base = {
    key: "h_" + row.name,
    role: row.role,
    ts: parseServerTs(row.timestamp),
    messageId: row.message_id || null,
    errorText: null,
    retryable: false,
    truncated: false,
    model: null,
    promptTokens: null,
    completionTokens: null,
    durationMs: null,
    files,
    source: "history",
  };
  if (row.role === "user") {
    return { ...base, content: String(row.content || ""), status: "done" };
  }
  const errored = !!row.errored;
  const aborted = !!row.aborted;
  const content = errored ? "" : stripStopMarker(row.content || contentFromBlocks(row.blocks));
  if (!errored && !aborted && !content) return null;
  return {
    ...base,
    content,
    status: errored ? "error" : aborted ? "aborted" : "done",
    errorText: errored ? __("AIDA couldn't finish this answer. Please try again.") : null,
    model: row.model || null,
    promptTokens: numberOrNull(row.prompt_tokens),
    completionTokens: numberOrNull(row.completion_tokens),
    durationMs: numberOrNull(row.duration_ms),
  };
}

export function isStaleShellRow(row, now, graceMs = 60000) {
  if (!row || row.role !== "assistant" || row.errored || row.aborted) return false;
  if (row.content || contentFromBlocks(row.blocks)) return false;
  return now - parseServerTs(row.timestamp) > graceMs;
}

function startOfDay(ms) {
  const d = new Date(ms);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function labelFor(ms, now, lang) {
  const days = Math.round((startOfDay(now) - startOfDay(ms)) / DAY);
  if (days <= 0) return __("Today");
  if (days === 1) return __("Yesterday");
  if (days < 7) return __("This week");
  return new Date(ms).toLocaleDateString(lang, { month: "short", day: "numeric" });
}

export function groupSessions(sessions, now = Date.now()) {
  const lang = getLang();
  const groups = [];
  for (const s of sessions) {
    const label = labelFor(parseServerTs(s.last_activity || s.started), now, lang);
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.items.push(s);
    else groups.push({ label, items: [s] });
  }
  return groups;
}

export function sessionTime(session) {
  return new Date(parseServerTs(session.last_activity || session.started)).toLocaleTimeString(getLang(), {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function titleOf(messages) {
  const first = messages.find((m) => m.role === "user" && m.content.trim());
  return first ? truncate(first.content, 60) : "";
}

export function pageTitle(state) {
  if (state.route.name === "settings") return __("Settings");
  return titleOf(state.messages) || __("Chat");
}

export function documentTitleOf(state) {
  if (state.route.name === "settings") return __("Settings - AIDA");
  const title = titleOf(state.messages);
  return title ? __("{0} - AIDA", title) : __("AIDA");
}

export function newSessionId() {
  const bytes = new Uint8Array(9);
  globalThis.crypto.getRandomValues(bytes);
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `pao_${Date.now()}_${hex}`;
}

export function isValidSessionId(id) {
  return typeof id === "string" && /^[A-Za-z0-9_-]{1,100}$/.test(id);
}
