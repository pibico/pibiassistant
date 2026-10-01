import * as api from "./api.js";
import { store, setUi } from "./store.js";
import { __ } from "./i18n.js";
import { fromHistoryRow, isStaleShellRow } from "./format.js";
import { expireApprovals } from "./activity.js";
import { IDLE_STREAMING, clearTimers } from "./chat-live.js";

async function fetchRows(id, { flagStale = false } = {}) {
  const res = await api.get("get_session_history", { session_id: id, limit: 100 });
  const rows = Array.isArray(res) ? res : (res && res.messages) || [];
  const messages = rows.map(fromHistoryRow).filter(Boolean);
  const tail = rows[rows.length - 1];
  if (flagStale && tail && isStaleShellRow(tail, Date.now())) {
    messages.push({ ...fromHistoryRow({ ...tail, errored: 1 }), retryable: true });
  }
  return expireApprovals(messages);
}

function applyServerRows(rows) {
  const { messages, streaming } = store.get();
  const live = streaming.active ? messages.find((m) => m.key === streaming.key) : null;
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
    const rows = await fetchRows(id, { flagStale: true });
    if (store.get().activeSessionId !== id) return;
    applyServerRows(rows);
  } catch (err) {
    console.error("get_session_history failed", err);
    if (store.get().activeSessionId !== id) return;
    const gone = err instanceof api.ApiError && (err.kind === "validation" || err.status === 403);
    store.set({ historyState: gone ? "notfound" : "error" });
  }
}

export async function recover() {
  const id = store.get().activeSessionId;
  if (!id) return;
  try {
    const rows = await fetchRows(id);
    if (store.get().activeSessionId === id) applyServerRows(rows);
  } catch (err) {
    console.error("recover failed", err);
  }
}
