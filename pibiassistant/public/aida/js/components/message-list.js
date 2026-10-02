import { h } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { store } from "../lib/store.js";
import { loadHistory, loadEarlier, retryLast } from "../lib/chat.js";
import { chatPath } from "../router.js";
import { icon } from "./icons.js";
import { createTurn } from "./message.js";

const FOLLOW_THRESHOLD = 120;
const SMOOTH_LOCK_MS = 600;

function skeletonTurn() {
  return h(
    "div",
    { class: "aida-turn aida-turn--skeleton", "aria-hidden": "true" },
    h("div", { class: "aida-turn__avatar" }, h("div", { class: "aida-skeleton aida-avatar aida-avatar--ai" })),
    h(
      "div",
      { class: "aida-turn__content" },
      h("div", { class: "aida-skeleton aida-turn__bar aida-turn__bar--short" }),
      h("div", { class: "aida-skeleton aida-turn__bar" }),
      h("div", { class: "aida-skeleton aida-turn__bar aida-turn__bar--mid" }),
    ),
  );
}

function stateView(historyState, messages) {
  if (historyState === "loading" && !messages.length) {
    return [
      skeletonTurn(),
      skeletonTurn(),
      h("p", { class: "aida-chat-empty" }, __("Loading conversation...")),
    ];
  }
  if (historyState !== "error" && historyState !== "notfound") return [];
  const gone = historyState === "notfound";
  const id = store.get().activeSessionId;
  return [
    h(
      "div",
      { class: "aida-chat-empty aida-notice is-error", role: "alert" },
      icon("alert", 16),
      h("span", null, gone ? __("We couldn't find this conversation.") : __("Couldn't load this conversation.")),
      gone ? null : h("button", { type: "button", class: "aida-link-btn", onClick: () => id && loadHistory(id) }, __("Try again")),
      h("a", { class: "aida-link-btn", href: chatPath() }, __("Start a new chat")),
    ),
  ];
}

export function createMessageList() {
  const col = h("div", { class: "aida-thread__col" });
  const thread = h("div", { class: "aida-thread", role: "log", "aria-live": "off", "aria-label": __("Conversation"), tabindex: "0" }, col);
  const latestLabel = h("span", null, __("Latest"));
  const latest = h(
    "button",
    { type: "button", class: "aida-latest", "aria-hidden": "true", tabindex: "-1" },
    icon("arrow-down", 14),
    latestLabel,
  );
  const status = h("div", { class: "aida-status aida-sr-only", role: "status", "aria-live": "polite" });
  const el = h("div", { class: "aida-chat" }, thread, latest, status);
  const stateEl = h("div", { class: "aida-thread__state" });
  const earlierBtn = h("button", { type: "button", class: "aida-link-btn aida-earlier", onClick: onEarlier }, __("Load earlier messages"));
  const earlierEl = h("div", { class: "aida-thread__earlier", hidden: true }, earlierBtn);
  col.append(earlierEl, stateEl);

  const turns = new Map();
  let following = true;
  let lockUntil = 0;
  let lastSession = store.get().activeSessionId;

  const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function scrollToBottom(smooth = false) {
    thread.scrollTo({ top: thread.scrollHeight, behavior: smooth && !reduceMotion() ? "smooth" : "auto" });
  }

  function updateLatest() {
    const { messages, streaming } = store.get();
    const show = !following && messages.length > 0;
    latest.classList.toggle("is-visible", show);
    latest.tabIndex = show ? 0 : -1;
    latest.setAttribute("aria-hidden", show ? "false" : "true");
    latestLabel.textContent = streaming.active ? __("Latest · responding") : __("Latest");
  }

  function onScroll() {
    if (Date.now() < lockUntil) return;
    const dist = thread.scrollHeight - thread.scrollTop - thread.clientHeight;
    following = dist <= FOLLOW_THRESHOLD;
    updateLatest();
  }

  function jumpLatest() {
    following = true;
    lockUntil = Date.now() + SMOOTH_LOCK_MS;
    scrollToBottom(true);
    updateLatest();
  }

  async function onEarlier() {
    const before = thread.scrollHeight;
    const top = thread.scrollTop;
    following = false;
    await loadEarlier();
    thread.scrollTop = top + (thread.scrollHeight - before);
  }

  function renderEarlier() {
    const { history, messages } = store.get();
    earlierEl.hidden = !(history.hasMore && messages.length);
    earlierBtn.disabled = history.loadingMore;
    earlierBtn.textContent = history.loadingMore ? __("Loading...") : __("Load earlier messages");
  }

  function renderMessages() {
    const { messages, activeSessionId } = store.get();
    if (activeSessionId !== lastSession) {
      lastSession = activeSessionId;
      following = true;
    }
    const keep = new Set(messages.map((m) => m.key));
    for (const [key, entry] of turns) {
      if (!keep.has(key)) {
        entry.turn.destroy();
        entry.turn.el.remove();
        turns.delete(key);
      }
    }
    let ref = earlierEl.nextSibling;
    messages.forEach((msg, i) => {
      let entry = turns.get(msg.key);
      if (!entry) {
        entry = { turn: createTurn(msg, { onRetry: retryLast }), msg };
        turns.set(msg.key, entry);
      } else if (entry.msg !== msg) {
        entry.turn.update(msg);
        entry.msg = msg;
      }
      if (entry.turn.el === ref) ref = ref.nextSibling;
      else col.insertBefore(entry.turn.el, ref);
      entry.turn.el.classList.toggle("is-last", i === messages.length - 1);
    });
    renderState();
    renderEarlier();
    updateLatest();
    if (following) scrollToBottom();
  }

  function renderState() {
    const { historyState, messages } = store.get();
    stateEl.replaceChildren(...stateView(historyState, messages));
  }

  function renderStatus() {
    const text = store.get().ui.announce;
    if (status.textContent !== text) status.textContent = text;
  }

  const onScrollBottom = () => {
    following = true;
    scrollToBottom();
  };
  const resizer = typeof ResizeObserver === "function" ? new ResizeObserver(() => following && scrollToBottom()) : null;

  thread.addEventListener("scroll", onScroll, { passive: true });
  latest.addEventListener("click", jumpLatest);
  document.addEventListener("aida:scroll-bottom", onScrollBottom);
  if (resizer) resizer.observe(col);
  const unsubscribe = store.subscribe(renderMessages, ["messages", "historyState", "activeSessionId", "streaming", "history"]);
  const unsubscribeUi = store.subscribe(renderStatus, ["ui"]);
  renderMessages();
  renderStatus();

  return {
    el,
    scrollToBottom,
    destroy() {
      unsubscribe();
      unsubscribeUi();
      document.removeEventListener("aida:scroll-bottom", onScrollBottom);
      if (resizer) resizer.disconnect();
      for (const entry of turns.values()) entry.turn.destroy();
      turns.clear();
    },
  };
}
