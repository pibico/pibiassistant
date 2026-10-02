import * as api from "./api.js";
import { store, setUi } from "./store.js";
import { __ } from "./i18n.js";
import { fromHistoryRow, isStaleShellRow } from "./format.js";
import { expireApprovals } from "./activity.js";
import { IDLE_STREAMING, clearTimers } from "./chat-live.js";
import { show as showToast } from "../components/toast.js";

const PAGE = 100;
export const NO_HISTORY = Object.freeze({ hasMore: false, loadingMore: false, offset: 0 });

async function fetchPage(id, offset) {
  const res = await api.get("get_session_history", { session_id: id, limit: PAGE, ...(offset ? { offset } : {}) });
  const rows = Array.isArray(res) ? res : (res && res.messages) || [];
  return { rows, hasMore: !!(res && !Array.isArray(res) && res.has_more) };
}

async function fetchRows(id, { flagStale = false } = {}) {
  const { rows, hasMore } = await fetchPage(id, 0);
  const messages = rows.map(fromHistoryRow).filter(Boolean);
  const tail = rows[rows.length - 1];
  if (flagStale && tail && isStaleShellRow(tail, Date.now())) {
    messages.push({ ...fromHistoryRow({ ...tail, errored: 1 }), retryable: true });
  }
  return { messages: expireApprovals(messages), hasMore, count: rows.length };
}

// Earlier pages loaded on demand stay put when a recover refetches only the newest page
export function mergeEarlier(current, rows) {
  const keys = new Set(rows.map((r) => r.key));
  const first = rows.length ? rows[0].ts : Infinity;
  const kept = current.filter((m) => m.source === "history" && !keys.has(m.key) && m.ts < first);
  return kept.length ? [...kept, ...rows] : rows;
}

export function prependEarlier(current, older) {
  const keys = new Set(current.map((m) => m.key));
  return [...older.filter((m) => !keys.has(m.key)), ...current];
}

export async function loadEarlier() {
  const { activeSessionId: id, history, messages } = store.get();
  if (!id || !history.hasMore || history.loadingMore) return;
  store.set({ history: { ...history, loadingMore: true } });
  try {
    const { rows, hasMore } = await fetchPage(id, history.offset);
    if (store.get().activeSessionId !== id) return;
    const older = expireApprovals(rows.map(fromHistoryRow).filter(Boolean));
    store.set({
      messages: prependEarlier(store.get().messages, older),
      history: { hasMore: hasMore && rows.length > 0, loadingMore: false, offset: history.offset + rows.length },
    });
  } catch (err) {
    console.error("load earlier failed", err);
    if (store.get().activeSessionId === id) store.set({ history: { ...store.get().history, loadingMore: false } });
    showToast({ message: __("Couldn't load earlier messages."), type: "error" });
  }
}

function applyServerRows(page, initial = false) {
  const { messages, streaming } = store.get();
  const rows = initial ? page.messages : mergeEarlier(messages, page.messages);
  const live = streaming.active ? messages.find((m) => m.key === streaming.key) : null;
  if (initial || rows.length === page.messages.length) {
    store.set({ history: { hasMore: page.hasMore, loadingMore: false, offset: page.count } });
  }
  if (!live) {
    store.set({ messages: rows, historyState: "ready" });
    return;
  }
  const known = new Set(messages.map((m) => m.messageId).filter(Boolean));
  const last = rows[rows.length - 1];
  const adopted = live.messageId
    ? rows.find((r) => r.role === "assistant" && r.messageId === live.messageId)
    : last && last.role === "assistant" && last.messageId && !known.has(last.messageId)
      ? last
      : null;
  if (adopted) {
    clearTimers();
    store.set({ messages: rows, historyState: "ready", streaming: IDLE_STREAMING });
    setUi({ announce: __("Answer complete") });
    return;
  }
  const prev = messages[messages.indexOf(live) - 1];
  const lastUser = [...rows].reverse().find((r) => r.role === "user");
  const keepUser = prev && prev.role === "user" && (!lastUser || lastUser.content !== prev.content);
  const earlier = rows.filter((r) => r.messageId !== live.messageId || !live.messageId);
  store.set({ messages: [...earlier, ...(keepUser ? [prev] : []), live], historyState: "ready" });
}

export async function loadHistory(id) {
  store.set({ historyState: "loading" });
  try {
    const page = await fetchRows(id, { flagStale: true });
    const now = store.get();
    if (now.activeSessionId !== id) return;
    if (!page.count && !now.messages.length && !now.streaming.active) {
      store.set({ historyState: "notfound" });
      return;
    }
    applyServerRows(page, true);
  } catch (err) {
    console.error("get_session_history failed", err);
    if (store.get().activeSessionId !== id) return;
    const gone = err instanceof api.ApiError && (err.kind === "validation" || (err.status === 403 && err.kind !== "session"));
    store.set({ historyState: gone ? "notfound" : "error" });
  }
}

export async function recover() {
  const id = store.get().activeSessionId;
  if (!id) return;
  try {
    const page = await fetchRows(id);
    if (store.get().activeSessionId === id) applyServerRows(page);
  } catch (err) {
    console.error("recover failed", err);
  }
}
