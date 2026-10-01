import { h } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import * as api from "../lib/api.js";
import { icon } from "./icons.js";
import { show } from "./toast.js";

const MAX_SECONDS = 60;
const MIN_SECONDS = 1;
const TICK_MS = 100;
const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

export function pickMime(isSupported) {
  return MIME_CANDIDATES.find((c) => isSupported(c)) || "audio/webm";
}

const errorText = (code) => ({
  "permission-denied": __("Microphone access denied. Enable it in your browser settings."),
  "no-mic": __("No microphone found."),
  "too-short": __("Didn't catch that."),
  "recorder-error": __("Couldn't start recording. Try again."),
  "transcribe-failed": __("Couldn't transcribe. Try again or type instead."),
})[code];

function formatElapsed(sec) {
  const s = Math.floor(sec);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function createMic({ onText }) {
  let state = "idle";
  let recorder = null;
  let stream = null;
  let chunks = [];
  let startedAt = 0;
  let tick = null;
  let cap = null;
  let mime = "audio/webm";

  const supported = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
  const time = h("span", { class: "aida-mic__time aida-num", hidden: true });
  const glyph = h("span", { class: "aida-mic__icon" }, icon("mic", 18));
  const el = h("button", {
    type: "button", class: "aida-mic", hidden: !supported,
    title: __("Voice input (Ctrl+Shift+Space)"), "aria-label": __("Voice input (Ctrl+Shift+Space)"),
    onClick: () => toggle(),
  }, glyph, time);

  function fail(code) {
    show({ type: "error", message: errorText(code) });
  }

  function paint() {
    el.classList.toggle("is-recording", state === "recording");
    el.classList.toggle("is-transcribing", state === "transcribing");
    el.disabled = state === "transcribing" || state === "requesting";
    time.hidden = state !== "recording";
    const label = state === "recording" ? __("Tap to stop") : state === "transcribing" ? __("Transcribing...") : __("Voice input (Ctrl+Shift+Space)");
    el.title = label;
    el.setAttribute("aria-label", label);
  }

  function setState(next) {
    state = next;
    paint();
  }

  function cleanup() {
    clearInterval(tick);
    clearTimeout(cap);
    tick = cap = null;
    document.removeEventListener("visibilitychange", onHidden);
    if (stream) stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }

  function onHidden() {
    if (document.hidden && state === "recording") cancel();
  }

  function cancel() {
    chunks = [];
    if (recorder && recorder.state !== "inactive") recorder.stop();
    cleanup();
    setState("idle");
  }

  async function start() {
    setState("requesting");
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      setState("idle");
      fail(err.name === "NotAllowedError" ? "permission-denied" : "no-mic");
      return;
    }
    mime = pickMime((c) => MediaRecorder.isTypeSupported(c));
    try {
      recorder = new MediaRecorder(stream, { mimeType: mime });
    } catch (err) {
      cleanup();
      setState("idle");
      fail("recorder-error");
      return;
    }
    chunks = [];
    recorder.ondataavailable = (e) => { if (e.data && e.data.size > 0) chunks.push(e.data); };
    recorder.onstop = finish;
    recorder.onerror = () => { cleanup(); setState("idle"); fail("recorder-error"); };
    startedAt = Date.now();
    recorder.start();
    time.textContent = formatElapsed(0);
    setState("recording");
    tick = setInterval(() => { time.textContent = formatElapsed((Date.now() - startedAt) / 1000); }, TICK_MS);
    cap = setTimeout(stop, MAX_SECONDS * 1000);
    document.addEventListener("visibilitychange", onHidden);
  }

  function stop() {
    if (recorder && recorder.state !== "inactive") recorder.stop();
  }

  async function finish() {
    cleanup();
    if (state !== "recording") return;
    const durationMs = Date.now() - startedAt;
    if (durationMs / 1000 < MIN_SECONDS || chunks.length === 0) {
      setState("idle");
      fail("too-short");
      return;
    }
    setState("transcribing");
    try {
      const fd = new FormData();
      fd.append("audio", new Blob(chunks, { type: mime }), "audio.webm");
      fd.append("duration_ms", String(Math.round(durationMs)));
      fd.append("language", String(window.aida_lang || navigator.language || "en").slice(0, 2));
      const res = await api.upload("voice.transcribe", fd);
      const text = res && typeof res.text === "string" ? res.text.trim() : "";
      setState("idle");
      if (!text) fail("too-short");
      else onText(text);
    } catch (err) {
      console.error("voice.transcribe failed", err);
      setState("idle");
      fail("transcribe-failed");
    }
  }

  function toggle() {
    if (state === "idle") return start();
    if (state === "recording") stop();
  }

  paint();
  return { el, toggle, isBusy: () => state !== "idle", destroy: cancel };
}
