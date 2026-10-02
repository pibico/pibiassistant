const OPTIONS = {
  withCredentials: true,
  reconnection: true,
  reconnectionAttempts: 20,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  timeout: 60000,
  transports: ["websocket", "polling"],
  path: "/socket.io",
};
const RECONNECTING_DELAY_MS = 3000;

const handlers = { stream: new Set(), status: new Set(), recover: new Set() };
let sock = null;
let connectedOnce = false;
let sessionId = null;
let status = "connected";
let downTimer = null;

function emitLocal(name, ...args) {
  for (const fn of [...handlers[name]]) {
    try {
      fn(...args);
    } catch {
      continue;
    }
  }
}

function setStatus(next) {
  if (next === status) return;
  status = next;
  emitLocal("status", next);
}

function socketUrl() {
  const { protocol, host, hostname } = location;
  const site = globalThis.site_name || host.split(".")[0];
  const local = hostname === "localhost" || hostname === "127.0.0.1";
  const origin = local ? `${protocol}//${hostname}:${globalThis.socketio_port}` : `${protocol}//${host}`;
  return `${origin}/${site}`;
}

function markDown() {
  if (downTimer || status === "lost") return;
  downTimer = setTimeout(() => {
    downTimer = null;
    setStatus("reconnecting");
  }, RECONNECTING_DELAY_MS);
}

function markUp() {
  clearTimeout(downTimer);
  downTimer = null;
  setStatus("connected");
}

export function isConnected() {
  return !!(sock && sock.connected);
}

function onConnect() {
  markUp();
  if (sessionId) sock.emit("task_subscribe", sessionId);
  if (connectedOnce) emitLocal("recover");
  connectedOnce = true;
}

function onVisible() {
  if (document.visibilityState !== "visible" || !sock) return;
  if (sock.connected) emitLocal("recover");
  else sock.connect();
}

export function connect() {
  if (sock) return;
  if (typeof globalThis.io !== "function") {
    setStatus("lost");
    return;
  }
  sock = globalThis.io(socketUrl(), OPTIONS);
  sock.on("connect", onConnect);
  sock.on("connect_error", markDown);
  sock.on("disconnect", markDown);
  sock.on("pao_message_stream", (payload) => emitLocal("stream", payload));
  sock.io.on("reconnect_failed", () => {
    clearTimeout(downTimer);
    downTimer = null;
    setStatus("lost");
  });
  document.addEventListener("visibilitychange", onVisible);
}

export function on(name, fn) {
  handlers[name].add(fn);
  return () => off(name, fn);
}

function off(name, fn) {
  handlers[name].delete(fn);
}

export function subscribe(id) {
  if (sock && sock.connected) {
    if (sessionId && sessionId !== id) sock.emit("task_unsubscribe", sessionId);
    sock.emit("task_subscribe", id);
  }
  sessionId = id;
}

export function unsubscribe() {
  if (sock && sock.connected && sessionId) sock.emit("task_unsubscribe", sessionId);
  sessionId = null;
}

export function retry() {
  if (!sock) return;
  setStatus("reconnecting");
  sock.connect();
}
