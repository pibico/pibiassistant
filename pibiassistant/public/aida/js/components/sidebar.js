import { h, focusables, trapFocus } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { store, setUi } from "../lib/store.js";
import { KEYS } from "../lib/storage.js";
import { writeHandoff } from "../lib/handoff.js";
import { icon } from "./icons.js";
import { createConversations } from "./conversations.js";
import { createUserMenu } from "./user-menu.js";

const DRAWER_QUERY = "(max-width: 1023.98px)";
const LOGO_SRC = "/assets/pibiassistant/chat/widget/aida-icon.svg";

export function mountSidebar(aside, scrim) {
  const chatLink = h("a", { class: "aida-nav__item", href: "/aida/chat" }, icon("chat", 20), h("span", null, __("Chat")));
  const deskLink = h("a", { class: "aida-nav__item", href: "/app" }, icon("desk", 20), h("span", null, __("Back to Desk")));
  const conversations = createConversations();
  const userMenu = createUserMenu();

  const closeBtn = h(
    "button",
    { type: "button", class: "aida-icon-btn aida-sidebar__close", "aria-label": __("Close menu"), title: __("Close menu") },
    icon("x", 20),
  );

  aside.replaceChildren(
    h(
      "div",
      { class: "aida-sidebar__header" },
      h("img", { class: "aida-logo", src: LOGO_SRC, alt: "", width: 32, height: 32 }),
      h("span", { class: "aida-wordmark" }, __("AIDA")),
      closeBtn,
    ),
    h("nav", { class: "aida-nav", "aria-label": __("Navigation") }, chatLink, deskLink),
    conversations.el,
    userMenu.el,
  );

  const mq = window.matchMedia(DRAWER_QUERY);
  const main = document.querySelector(".aida-main");
  let release = null;
  let wasActive = false;

  function renderRoute() {
    const onChat = store.get().route.name === "chat";
    if (onChat) chatLink.setAttribute("aria-current", "page");
    else chatLink.removeAttribute("aria-current");
  }

  function syncDrawer() {
    const open = store.get().ui.drawerOpen;
    const active = open && mq.matches;
    aside.classList.toggle("is-open", active);
    scrim.classList.toggle("is-open", active);
    aside.inert = mq.matches && !open;
    if (main) main.inert = active;
    document.body.classList.toggle("aida-lock", active);
    if (active) {
      aside.setAttribute("role", "dialog");
      aside.setAttribute("aria-modal", "true");
    } else {
      aside.removeAttribute("role");
      aside.removeAttribute("aria-modal");
    }
    if (active && !wasActive) {
      release = trapFocus(aside);
      focusables(aside)[0]?.focus();
    } else if (!active && wasActive) {
      if (release) release();
      release = null;
      document.getElementById("aida-burger")?.focus();
    }
    wasActive = active;
  }

  const close = () => setUi({ drawerOpen: false });
  const onKeydown = (e) => {
    if (e.key === "Escape" && wasActive) close();
  };
  const onViewport = () => {
    if (!mq.matches && store.get().ui.drawerOpen) close();
    else syncDrawer();
  };
  const onDesk = () => {
    const id = store.get().activeSessionId;
    if (id) writeHandoff(KEYS.handoffOut, id, window.user);
  };

  scrim.addEventListener("click", close);
  closeBtn.addEventListener("click", close);
  deskLink.addEventListener("click", onDesk);
  document.addEventListener("keydown", onKeydown);
  mq.addEventListener("change", onViewport);
  const unsubs = [store.subscribe(syncDrawer, ["ui"]), store.subscribe(renderRoute, ["route"])];
  renderRoute();
  syncDrawer();

  return () => {
    unsubs.forEach((u) => u());
    scrim.removeEventListener("click", close);
    closeBtn.removeEventListener("click", close);
    document.removeEventListener("keydown", onKeydown);
    mq.removeEventListener("change", onViewport);
    if (release) release();
    conversations.destroy();
    userMenu.destroy();
  };
}
