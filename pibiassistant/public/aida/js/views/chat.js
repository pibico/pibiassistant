import { h, isCoarse } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { store } from "../lib/store.js";
import { openSession, sendMessage } from "../lib/chat.js";
import { retry } from "../lib/socket.js";
import { icon } from "../components/icons.js";
import { createComposer } from "../components/composer.js";
import { createMessageList } from "../components/message-list.js";
import { createWelcome } from "../components/welcome.js";

const THREAD_STATES = new Set(["loading", "error", "notfound"]);

export function mountChat(container, route) {
  const composer = createComposer({ variant: "hero" });
  const list = createMessageList();
  const welcome = createWelcome({ composerEl: composer.el, onPick: (text) => sendMessage({ text }) });
  const dock = h("div", { class: "aida-dock", hidden: true });
  const dot = h("span", { class: "aida-conn-dot", role: "status", title: __("Reconnecting..."), "aria-label": __("Reconnecting..."), hidden: true });
  const banner = h(
    "div",
    { class: "aida-banner", role: "status", hidden: true },
    icon("alert", 16),
    h("span", null, __("Connection lost. Replies may be delayed.")),
    h("button", { type: "button", class: "aida-link-btn", onClick: () => retry() }, __("Retry")),
  );
  list.el.hidden = true;
  container.append(banner, dot, welcome.el, list.el, dock);

  let mode = null;

  function currentMode() {
    const { messages, historyState } = store.get();
    return messages.length > 0 || THREAD_STATES.has(historyState) ? "thread" : "welcome";
  }

  function applyMode() {
    const next = currentMode();
    if (next === mode) return;
    const first = mode === null;
    mode = next;
    const thread = next === "thread";
    welcome.el.hidden = thread;
    list.el.hidden = !thread;
    dock.hidden = !thread;
    if (thread) {
      dock.append(composer.el);
      composer.setVariant("dock");
      if (!first) {
        dock.classList.add("is-entering");
        dock.addEventListener("animationend", () => dock.classList.remove("is-entering"), { once: true });
      }
    } else {
      welcome.slot.append(composer.el);
      composer.setVariant("hero");
      welcome.refresh();
    }
    if (!first && !isCoarse()) composer.focus();
  }

  function applyConnection() {
    const state = store.get().ui.connection;
    dot.hidden = state !== "reconnecting";
    banner.hidden = state !== "lost";
  }

  const unsubs = [store.subscribe(applyMode, ["messages", "historyState"]), store.subscribe(applyConnection, ["ui"])];

  function update(next) {
    openSession(next.sessionId);
    applyMode();
    if (!next.sessionId && !isCoarse()) composer.focus();
  }

  update(route);
  applyConnection();

  return {
    update,
    destroy() {
      unsubs.forEach((u) => u());
      composer.destroy();
      list.destroy();
      welcome.destroy();
      for (const node of [banner, dot, welcome.el, list.el, dock]) node.remove();
    },
  };
}
