import * as api from "./api.js";
import * as socket from "./socket.js";
import { store, setUi } from "./store.js";
import { __ } from "./i18n.js";
import { newSessionId, truncate, stripStopMarker } from "./format.js";
import { IDLE_STREAMING, genericError, newMessage, setStreaming, clearTimers, armWatchdog, startCancelFallback } from "./chat-live.js";
import { loadHistory, recover } from "./session-history.js";

export { loadHistory, recover };
import { applyStreamEvent, isTerminal } from "./stream.js";
import * as router from "../router.js";
import { show as showToast } from "../components/toast.js";
import { confirm } from "../components/dialog.js";

const CANCEL_FALLBACK_MS = 4000;
const LOCK_RETRY_WINDOW_MS = 15000;
const LOCK_RETRY_MS = 1500;
const LOCK_RETRIES = 4;

let started = false;
let recoverTimer = null;
let lastCancelAt = 0;

const emit = (name, detail) => document.dispatchEvent(new CustomEvent(name, { detail }));
const arm = () => armWatchdog(onSilence, recover);

function patchLive(patch) {
  const { messages, streaming } = store.get();
  store.set({ messages: messages.map((m) => (m.key === streaming.key ? { ...m, ...patch } : m)) });
}

function finishLive(status) {
  const live = store.get().messages.find((m) => m.key === store.get().streaming.key);
  clearTimers();
  if (live) {
    patchLive(
      status === "error"
        ? { status, errorText: genericError(), ts: Date.now() }
        : { status, content: stripStopMarker(live.content), ts: Date.now() },
    );
  }
  store.set({ streaming: IDLE_STREAMING });
  setUi({ announce: status === "error" ? genericError() : __("Stopped.") });
}

async function onSilence() {
  await recover();
  if (store.get().streaming.active) finishLive("error");
}

function detachLive() {
  clearTimers();
  if (store.get().streaming.active) store.set({ streaming: IDLE_STREAMING });
}

export function openSession(sessionId) {
  const s = store.get();
  if (sessionId === null) {
    if (s.activeSessionId === null && s.historyState === "ready" && !s.messages.length && !s.streaming.active) return;
    detachLive();
    store.set({ activeSessionId: null, messages: [], historyState: "ready" });
    socket.unsubscribe();
    setUi({ announce: "" });
    return;
  }
  if (sessionId === s.activeSessionId && (s.historyState === "ready" || s.streaming.active)) return;
  detachLive();
  store.set({ activeSessionId: sessionId, messages: [], historyState: "loading" });
  setUi({ announce: "" });
  socket.subscribe(sessionId);
  loadHistory(sessionId);
}

function scheduleRecover() {
  clearTimeout(recoverTimer);
  recoverTimer = setTimeout(recover, 300);
}

function handleStream(payload) {
  const s = store.get();
  if (!payload || payload.session_id !== s.activeSessionId) return;
  const terminal = isTerminal(payload.event);
  if (s.streaming.active) {
    arm();
    if (s.streaming.slow) setStreaming({ slow: false });
  }
  const live = store.get().messages.find((m) => m.key === store.get().streaming.key);
  if (!live) {
    if (terminal && store.get().streaming.active) {
      clearTimers();
      store.set({ streaming: IDLE_STREAMING });
    }
    if (payload.event === "stream_start" || terminal) scheduleRecover();
    return;
  }
  const next = applyStreamEvent(live, payload, Date.now());
  if (next === live) return;
  store.set({ messages: store.get().messages.map((m) => (m === live ? next : m)) });
  if (payload.event === "stream_start") setUi({ announce: __("AIDA is responding") });
  if (terminal) {
    clearTimers();
    store.set({ streaming: IDLE_STREAMING });
    setUi({
      announce:
        next.status === "done" ? __("Answer complete") : next.status === "aborted" ? __("Stopped.") : next.errorText,
    });
    refreshSessions();
  }
}

export function initChat() {
  if (started) return;
  started = true;
  socket.on("stream", handleStream);
  socket.on("status", (state) => setUi({ connection: state }));
  socket.on("recover", recover);
}

// After Stop the server may still hold the turn lock for a few seconds.
async function postSend(args) {
  for (let attempt = 0; ; attempt++) {
    try {
      return await api.post("send_message", args);
    } catch (err) {
      const lock =
        err instanceof api.ApiError &&
        err.kind === "validation" &&
        Date.now() - lastCancelAt < LOCK_RETRY_WINDOW_MS &&
        attempt < LOCK_RETRIES;
      if (!lock) throw err;
      await new Promise((r) => setTimeout(r, LOCK_RETRY_MS));
    }
  }
}

export function sendMessage({ text = "", fileUrls = [], files = [] } = {}) {
  const s = store.get();
  const body = text.trim();
  if (s.streaming.active || (!body && !fileUrls.length) || text.length > 20000) return false;
  const now = Date.now();
  let id = s.activeSessionId;
  if (!id) {
    id = newSessionId();
    router.replaceUrl(router.chatPath(id));
    const entry = { session_id: id, preview: truncate(body, 100), last_activity: now, started: now, message_count: 1 };
    store.set({ activeSessionId: id, historyState: "ready", sessions: [entry, ...s.sessions] });
  }
  socket.subscribe(id);
  const user = newMessage({
    role: "user",
    content: body,
    files: files.map((f) => ({ name: f.file_name || f.name, url: f.file_url || f.url, size: f.size || 0 })),
  });
  const bubble = newMessage({ role: "assistant", status: "streaming" });
  store.set({
    messages: [...store.get().messages, user, bubble],
    streaming: { active: true, key: bubble.key, stopping: false, slow: false },
  });
  setUi({ announce: __("AIDA is thinking...") });
  arm();
  emit("aida:scroll-bottom");

  const model = store.get().selectedModel;
  postSend({
    session_id: id,
    message: body,
    ...(model && model !== "auto" ? { model_id: model } : {}),
    ...(fileUrls.length ? { file_urls: JSON.stringify(fileUrls) } : {}),
    client_type: "spa",
  }).catch((err) => {
      if (store.get().streaming.key !== bubble.key) return;
      clearTimers();
      store.set({
        messages: store.get().messages.filter((m) => m.key !== bubble.key && m.key !== user.key),
        streaming: IDLE_STREAMING,
      });
      const isApi = err instanceof api.ApiError;
      const expired = isApi && err.kind === "session";
      showToast({
        message: isApi ? err.message : __("Couldn't send your message. Check your connection and try again."),
        type: "error",
        action: expired ? { label: __("Reload"), onClick: () => location.reload() } : undefined,
      });
      emit("aida:restore-draft", {
        text,
        files: user.files.map((f) => ({ name: f.name, file_name: f.name, file_url: f.url, size: f.size })),
      });
    });
  return true;
}

export async function stopStreaming() {
  const { streaming, messages, activeSessionId } = store.get();
  if (!streaming.active || streaming.stopping) return;
  setStreaming({ stopping: true });
  lastCancelAt = Date.now();
  startCancelFallback(() => {
    if (store.get().streaming.active) finishLive("aborted");
  }, CANCEL_FALLBACK_MS);
  const live = messages.find((m) => m.key === streaming.key);
  try {
    await api.post("cancel_stream", { session_id: activeSessionId, message_id: (live && live.messageId) || null });
  } catch (err) {
    console.error("cancel_stream failed", err);
  }
}

export function retryLast() {
  const { messages, streaming } = store.get();
  if (streaming.active) return false;
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  if (!lastUser) return false;
  const trailing = messages[messages.length - 1];
  const drop = new Set([lastUser.key]);
  if (trailing.role === "assistant" && trailing.status === "error") drop.add(trailing.key);
  store.set({ messages: messages.filter((m) => !drop.has(m.key)) });
  const files = lastUser.files.map((f) => ({ file_name: f.name, file_url: f.url }));
  return sendMessage({ text: lastUser.content, fileUrls: files.map((f) => f.file_url), files });
}

export function newChat() {
  openSession(null);
  router.navigate(router.chatPath());
  emit("aida:focus-composer");
}

export function selectSession(id) {
  router.navigate(router.chatPath(id));
}

export async function archiveSession(id) {
  const { activeSessionId, streaming } = store.get();
  if (id === activeSessionId && streaming.active) {
    const ok = await confirm({
      title: __("Archive conversation"),
      message: __("AIDA is still answering. Stop and archive?"),
      confirmLabel: __("Confirm archive"),
      cancelLabel: __("Cancel"),
      danger: true,
    });
    if (!ok) return false;
  }
  let done = false;
  try {
    const res = await api.post("archive_session", { session_id: id });
    done = !!res && res.success === true;
  } catch (err) {
    console.error("archive_session failed", err);
  }
  if (!done) {
    showToast({ message: __("Couldn't archive the conversation."), type: "error" });
    return false;
  }
  store.set({ sessions: store.get().sessions.filter((s) => s.session_id !== id) });
  if (id === store.get().activeSessionId) newChat();
  return true;
}

export async function refreshSessions() {
  if (store.get().sessionsState === "idle") store.set({ sessionsState: "loading" });
  try {
    const res = await api.get("get_user_sessions", { limit: 20 });
    const rows = Array.isArray(res) ? res : [];
    const { activeSessionId, sessions } = store.get();
    const pending = sessions.find((s) => s.session_id === activeSessionId);
    const merged = pending && !rows.some((r) => r.session_id === activeSessionId) ? [pending, ...rows] : rows;
    store.set({ sessions: merged, sessionsState: "ready" });
  } catch (err) {
    console.error("get_user_sessions failed", err);
    store.set({ sessionsState: "error" });
  }
}
