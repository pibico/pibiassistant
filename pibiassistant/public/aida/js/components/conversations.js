import { h } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { store, setUi } from "../lib/store.js";
import { groupSessions, sessionTime } from "../lib/format.js";
import { archiveSession, newChat, refreshSessions } from "../lib/chat.js";
import { chatPath } from "../router.js";
import { icon } from "./icons.js";
import { confirm } from "./dialog.js";

const COLLAPSED_COUNT = 5;

export function createConversations() {
  let deletingId = null;
  let showAll = false;

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
        { type: "button", class: "aida-chat-item__delete", "aria-label": __("Archive conversation"), title: __("Archive conversation"), onClick: () => askArchive(s.session_id) },
        icon("trash", 16),
      ),
    );
  }

  function render() {
    const { sessions, sessionsState, activeSessionId } = store.get();
    if (!sessions.length) {
      const loading = sessionsState === "idle" || sessionsState === "loading";
      list.replaceChildren(
        sessionsState === "error"
          ? h(
              "li",
              { class: "aida-recent__state aida-recent__empty", role: "alert" },
              h("p", { class: "aida-recent__empty-title" }, __("Couldn't load your conversations.")),
              h("button", {
                type: "button", class: "aida-btn aida-btn--outline",
                onClick: () => { store.set({ sessionsState: "loading" }); refreshSessions(); },
              }, __("Retry")),
            )
          : loading
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
  }

  async function askArchive(id) {
    const streamingHere = store.get().streaming.active && id === store.get().activeSessionId;
    if (!streamingHere) {
      const ok = await confirm({
        title: __("Archive conversation"),
        message: __("Archive this conversation?"),
        confirmLabel: __("Confirm archive"),
        cancelLabel: __("Cancel"),
        danger: true,
      });
      if (!ok) return;
    }
    doArchive(id);
  }

  async function doArchive(id) {
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
