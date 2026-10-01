import { h } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { store, setUi } from "../lib/store.js";
import { groupSessions, sessionTime } from "../lib/format.js";
import { archiveSession, newChat } from "../lib/chat.js";
import { chatPath } from "../router.js";
import { icon } from "./icons.js";

const COLLAPSED_COUNT = 5;

export function createConversations() {
  let confirmingId = null;
  let deletingId = null;
  let showAll = false;
  let focusConfirm = false;

  const list = h("ul", { class: "aida-recent__list" });
  const more = h("button", { type: "button", class: "aida-recent__more", hidden: true });
  const newBtn = h(
    "button",
    { type: "button", class: "aida-icon-btn aida-recent__new", "aria-label": __("New chat"), title: __("New chat") },
    icon("plus", 18),
  );
  const el = h(
    "section",
    { class: "aida-recent", "aria-labelledby": "aida-recent-title" },
    h("div", { class: "aida-recent__head" }, h("h2", { class: "aida-recent__title", id: "aida-recent-title" }, __("Recent Chats")), newBtn),
    list,
    more,
  );

  function item(s, activeId) {
    const active = s.session_id === activeId;
    const title = s.preview || __("New conversation");
    if (s.session_id === deletingId) {
      return h(
        "li",
        { class: "aida-chat-item is-deleting", "aria-busy": "true" },
        h("span", { class: "aida-chat-item__title" }, title),
        h("span", { class: "aida-spinner", role: "status", "aria-label": __("Archiving...") }),
      );
    }
    if (s.session_id === confirmingId) {
      focusConfirm = true;
      return h(
        "li",
        { class: "aida-chat-item is-confirming" },
        h("span", { class: "aida-chat-item__ask" }, __("Archive?")),
        h(
          "button",
          { type: "button", class: "aida-icon-btn aida-chat-item__confirm", "aria-label": __("Confirm archive"), title: __("Confirm archive"), onClick: () => doArchive(s.session_id) },
          icon("check", 16),
        ),
        h(
          "button",
          { type: "button", class: "aida-icon-btn aida-chat-item__cancel", "aria-label": __("Cancel"), title: __("Cancel"), onClick: () => setConfirming(null) },
          icon("x", 16),
        ),
      );
    }
    return h(
      "li",
      { class: ["aida-chat-item", active && "is-active"] },
      h(
        "a",
        { class: "aida-chat-item__main", href: chatPath(s.session_id), "aria-current": active ? "page" : null },
        h("span", { class: "aida-chat-item__title" }, title),
        h("span", { class: "aida-chat-item__time aida-num" }, sessionTime(s)),
      ),
      h(
        "button",
        { type: "button", class: "aida-chat-item__delete", "aria-label": __("Archive conversation"), title: __("Archive conversation"), onClick: () => setConfirming(s.session_id) },
        icon("trash", 16),
      ),
    );
  }

  function render() {
    const { sessions, sessionsState, activeSessionId } = store.get();
    focusConfirm = false;
    if (!sessions.length) {
      const loading = sessionsState === "idle" || sessionsState === "loading";
      list.replaceChildren(
        loading
          ? h("li", { class: "aida-recent__state" }, h("span", { class: "aida-spinner", role: "status", "aria-label": __("Loading conversation...") }))
          : h(
              "li",
              { class: "aida-recent__state aida-recent__empty" },
              h("p", { class: "aida-recent__empty-title" }, __("No conversations yet")),
              h("p", { class: "aida-recent__empty-hint" }, __("Start a new chat to begin")),
            ),
      );
      more.hidden = true;
      return;
    }
    const visible = showAll ? sessions : sessions.slice(0, COLLAPSED_COUNT);
    list.replaceChildren(
      ...groupSessions(visible).flatMap((group) => [
        h("li", { class: "aida-recent__group", "aria-hidden": "true" }, group.label),
        ...group.items.map((s) => item(s, activeSessionId)),
      ]),
    );
    more.hidden = sessions.length <= COLLAPSED_COUNT;
    more.textContent = showAll ? __("Show Less") : __("Show All ({0})", sessions.length);
    if (focusConfirm) list.querySelector(".aida-chat-item__cancel")?.focus();
  }

  function setConfirming(id) {
    confirmingId = id;
    render();
    if (id === null) list.querySelector(".aida-chat-item__delete")?.focus();
  }

  async function doArchive(id) {
    confirmingId = null;
    deletingId = id;
    render();
    await archiveSession(id);
    deletingId = null;
    render();
  }

  newBtn.addEventListener("click", () => {
    newChat();
    setUi({ drawerOpen: false });
  });
  more.addEventListener("click", () => {
    showAll = !showAll;
    render();
  });

  const unsubscribe = store.subscribe(render, ["sessions", "sessionsState", "activeSessionId"]);
  render();

  return { el, destroy: unsubscribe };
}
