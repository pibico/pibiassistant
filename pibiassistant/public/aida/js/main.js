import * as preferences from "./lib/preferences.js";
import * as socket from "./lib/socket.js";
import * as handoff from "./lib/handoff.js";
import * as router from "./router.js";
import { h, clear } from "./lib/dom.js";
import { __, getLang } from "./lib/i18n.js";
import { store, setUi } from "./lib/store.js";
import { KEYS, local } from "./lib/storage.js";
import { firstNameOf } from "./lib/greeting.js";
import { documentTitleOf, isValidSessionId } from "./lib/format.js";
import { initChat, refreshSessions } from "./lib/chat.js";
import { loadModels } from "./components/model-picker.js";
import { mountSidebar } from "./components/sidebar.js";
import { mountTopbar } from "./components/topbar.js";
import { mountChat } from "./views/chat.js";
import { mountSettings } from "./views/settings.js";

function buildShell(root) {
  const scrim = h("div", { class: "aida-scrim", id: "aida-scrim" });
  const aside = h("aside", { class: "aida-sidebar", id: "aida-nav", "aria-label": __("Main navigation") });
  const header = h("header", { class: "aida-topbar", id: "aida-topbar" });
  const view = h("main", { class: "aida-view", id: "aida-view", tabindex: "-1" });
  const skip = h("a", { class: "aida-skip", href: "#aida-view" }, __("Skip to conversation"));
  const toasts = h("div", { class: "aida-toasts", id: "aida-toasts", "aria-live": "polite" });
  const main = h("div", { class: "aida-main" }, skip, header, view);
  root.append(h("div", { class: "aida-app" }, scrim, aside, main, toasts));
  return { scrim, aside, header, view };
}

function adoptHandoff() {
  const id = handoff.readHandoff(KEYS.handoffIn, window.user);
  handoff.clearHandoff(KEYS.handoffIn);
  const target = router.parse(location.pathname);
  if (id && isValidSessionId(id) && target.name === "chat" && !target.sessionId) {
    history.replaceState(null, "", router.chatPath(id));
  }
}

function routeController(viewEl) {
  let instance = null;
  let mounted = null;
  let lastKey = null;
  return (route) => {
    store.set({ route });
    if (instance && mounted === route.name && instance.update) {
      instance.update(route);
    } else {
      if (instance) instance.destroy();
      clear(viewEl);
      instance = route.name === "settings" ? mountSettings(viewEl) : mountChat(viewEl, route);
      mounted = route.name;
    }
    setUi({ drawerOpen: false });
    document.title = documentTitleOf(store.get());
    const key = route.name + ":" + (route.sessionId || "");
    if (lastKey !== null && key !== lastKey) viewEl.focus();
    lastKey = key;
  };
}

function boot() {
  const root = document.getElementById("aida-root");
  try {
    preferences.init();
    document.documentElement.lang = getLang();
    document.title = __("AIDA");
    const fullName = window.user_fullname || "";
    store.set({
      user: {
        id: window.user,
        fullName,
        firstName: firstNameOf({ fullName, userId: window.user }) || "",
        image: window.user_image || null,
      },
      selectedModel: local.get(KEYS.model, "auto"),
    });
    const shell = buildShell(root);
    mountSidebar(shell.aside, shell.scrim);
    mountTopbar(shell.header);
    socket.connect();
    initChat();
    adoptHandoff();
    router.onRoute(routeController(shell.view));
    store.subscribe((state) => (document.title = documentTitleOf(state)), ["messages", "route"]);
    router.start();
    refreshSessions();
    loadModels();
  } catch {
    clear(root).append(h("p", { class: "aida-fatal" }, __("AIDA couldn't finish this answer. Please try again.")));
  }
}

boot();
