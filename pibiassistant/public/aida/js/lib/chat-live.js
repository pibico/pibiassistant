import * as socket from "./socket.js";
import { store } from "./store.js";
import { __ } from "./i18n.js";

const SLOW_MS = 90000;
const DEAD_MS = 180000;
const POLL_MS = 3000;
export const IDLE_STREAMING = Object.freeze({ active: false, key: null, stopping: false, slow: false });

let counter = 0;
let slowTimer = null;
let deadTimer = null;
let cancelTimer = null;
let pollTimer = null;

export const genericError = () => __("AIDA couldn't finish this answer. Please try again.");

export function newMessage(fields) {
  return {
    key: "m_" + ++counter,
    role: "user",
    content: "",
    ts: Date.now(),
    messageId: null,
    status: "done",
    errorText: null,
    retryable: false,
    truncated: false,
    model: null,
    promptTokens: null,
    completionTokens: null,
    durationMs: null,
    files: [],
    source: "live",
    ...fields,
  };
}

export function setStreaming(patch) {
  store.set({ streaming: { ...store.get().streaming, ...patch } });
}

export function clearTimers() {
  clearTimeout(slowTimer);
  clearTimeout(deadTimer);
  clearTimeout(cancelTimer);
  clearInterval(pollTimer);
  slowTimer = deadTimer = cancelTimer = pollTimer = null;
}

export function armWatchdog(onSilence, onDisconnected) {
  clearTimeout(slowTimer);
  clearTimeout(deadTimer);
  slowTimer = setTimeout(() => setStreaming({ slow: true }), SLOW_MS);
  deadTimer = setTimeout(onSilence, DEAD_MS);
  if (!pollTimer) {
    pollTimer = setInterval(() => {
      if (store.get().streaming.active && !socket.isConnected()) onDisconnected();
    }, POLL_MS);
  }
}

export function startCancelFallback(fn, ms) {
  clearTimeout(cancelTimer);
  cancelTimer = setTimeout(fn, ms);
}
