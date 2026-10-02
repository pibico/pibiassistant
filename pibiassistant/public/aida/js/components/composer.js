import { h, isCoarse } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { store, setUi } from "../lib/store.js";
import * as chat from "../lib/chat.js";
import { createAttachments } from "./attachments.js";
import { createMic } from "./mic.js";
import { icon } from "./icons.js";

const MAX_CHARS = 20000;
const COUNTER_FROM = 18000;
const MAX_HEIGHT = 240;

export function createComposer({ variant = "dock" } = {}) {
  const attachments = createAttachments({ onChange: refresh });
  const mic = createMic({ onText: appendDictation });
  const input = h("textarea", {
    class: "aida-composer__input", rows: "1", enterkeyhint: "send",
    "aria-label": __("Message"), onInput: () => { grow(); refresh(); }, onKeydown, onPaste,
  });
  const counter = h("span", { class: "aida-composer__counter aida-num", hidden: true });
  const hint = h("span", { class: "aida-composer__hint" });
  const attach = h("button", {
    type: "button", class: "aida-composer__btn", title: __("Attach files"), "aria-label": __("Attach files"),
    onClick: () => attachments.openPicker(),
  }, icon("paperclip", 18));
  const send = h("button", { type: "button", class: "aida-composer__send", onClick: onSendClick }, icon("send", 16));
  const el = h("div", { class: ["aida-composer", variant === "hero" ? "aida-composer--hero" : null], role: "group", "aria-label": __("Message") },
    attachments.el,
    h("div", { class: "aida-composer__box" },
      input,
      h("div", { class: "aida-composer__bar" },
        h("div", { class: "aida-composer__tools" }, attach, mic.el),
        h("div", { class: "aida-composer__end" }, counter, hint, send))));

  function grow() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, MAX_HEIGHT)}px`;
  }

  function canSend() {
    const text = input.value.trim();
    return (text.length > 0 || attachments.getReady().length > 0) && input.value.length <= MAX_CHARS && !attachments.isBusy();
  }

  function refresh() {
    const { streaming } = store.get();
    const len = input.value.length;
    const recording = mic.el.classList.contains("is-recording");
    counter.hidden = len < COUNTER_FROM;
    counter.textContent = __("{0} / {1}", len, MAX_CHARS);
    counter.classList.toggle("is-over", len > MAX_CHARS);
    input.placeholder = streaming.active ? __("AIDA is responding. Press Stop to interrupt.")
      : recording ? __("Listening...") : __("Ask me anything...");
    const label = streaming.active ? (streaming.stopping ? __("Stopping...") : __("Stop generating")) : __("Send message");
    send.replaceChildren(icon(streaming.active ? "stop" : "send", 16));
    send.title = label;
    send.setAttribute("aria-label", label);
    send.classList.toggle("is-stop", streaming.active);
    send.disabled = streaming.active ? streaming.stopping : !canSend();
    hint.textContent = streaming.active ? __("Wait for the answer or press Stop")
      : `${__("{0} send", "⏎")} · ${__("{0} new line", "⇧⏎")}`;
  }

  function submit() {
    const text = input.value;
    if (store.get().streaming.active || !canSend()) return;
    const files = attachments.getReady();
    const accepted = chat.sendMessage({ text, fileUrls: files.map((f) => f.file_url), files: files.map((f) => ({ name: f.file_name, url: f.file_url })) });
    if (accepted === true) {
      input.value = "";
      grow();
      attachments.clear();
      refresh();
    }
  }

  function onSendClick() {
    if (store.get().streaming.active) chat.stopStreaming();
    else submit();
  }

  function onKeydown(e) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  function onPaste(e) {
    const files = Array.from(e.clipboardData?.files || []);
    if (!files.length || (e.clipboardData.getData("text/plain") || "").trim()) return;
    e.preventDefault();
    attachments.addFiles(files);
  }

  function onShortcut(e) {
    if (!(e.ctrlKey && e.shiftKey && e.code === "Space")) return;
    const t = e.target;
    if (t !== input && t instanceof Element && t.closest("input, textarea, select, [contenteditable]")) return;
    e.preventDefault();
    mic.toggle();
  }

  const onFocus = () => { if (!isCoarse()) input.focus(); };
  const onRestore = (e) => {
    const d = e.detail || {};
    if (!input.value && d.text) { setText(d.text); }
    if (d.files && d.files.length) attachments.restore(d.files);
  };

  function setText(text) {
    input.value = text;
    grow();
    refresh();
  }

  // Dictation never sends: it lands in the box so it can be corrected or extended, and sending stays manual
  function appendDictation(text) {
    const current = input.value;
    const joined = current && !/\s$/.test(current) ? `${current} ${text}` : `${current}${text}`;
    setText(joined.slice(0, MAX_CHARS));
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
    setUi({ announce: __("Transcription added. Review it and press send.") });
  }

  document.addEventListener("keydown", onShortcut);
  document.addEventListener("aida:focus-composer", onFocus);
  document.addEventListener("aida:restore-draft", onRestore);
  const unsub = store.subscribe(refresh, ["streaming"]);
  const micWatch = new MutationObserver(refresh);
  micWatch.observe(mic.el, { attributes: true, attributeFilter: ["class"] });
  refresh();

  return {
    el,
    setVariant: (v) => el.classList.toggle("aida-composer--hero", v === "hero"),
    focus: () => input.focus(),
    setText,
    getText: () => input.value,
    clear: () => { setText(""); attachments.clear(); },
    destroy() {
      unsub();
      micWatch.disconnect();
      mic.destroy();
      document.removeEventListener("keydown", onShortcut);
      document.removeEventListener("aida:focus-composer", onFocus);
      document.removeEventListener("aida:restore-draft", onRestore);
    },
  };
}
