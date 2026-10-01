import { h } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { store, setUi } from "../lib/store.js";
import { pageTitle } from "../lib/format.js";
import { newChat } from "../lib/chat.js";
import { icon } from "./icons.js";
import { createModelPicker } from "./model-picker.js";

export function mountTopbar(header) {
  const burger = h(
    "button",
    { type: "button", id: "aida-burger", class: "aida-icon-btn aida-topbar__burger", "aria-controls": "aida-nav", "aria-expanded": "false" },
    icon("menu", 20),
  );
  const title = h("p", { class: "aida-topbar__title" });
  const picker = createModelPicker();
  const pickerSlot = h("div", { class: "aida-topbar__model" });
  const newBtn = h(
    "button",
    { type: "button", class: "aida-btn aida-btn--primary aida-topbar__new", "aria-label": __("New chat"), title: __("New chat") },
    icon("plus", 16),
    h("span", { class: "aida-topbar__new-label" }, __("New Chat")),
  );
  header.replaceChildren(burger, title, h("div", { class: "aida-topbar__actions" }, pickerSlot, newBtn));

  function renderTitle() {
    const text = pageTitle(store.get());
    if (title.textContent !== text) title.textContent = text;
  }

  function renderRoute() {
    const onChat = store.get().route.name === "chat";
    if (onChat && !picker.el.parentNode) pickerSlot.append(picker.el);
    if (!onChat && picker.el.parentNode) picker.el.remove();
    renderTitle();
  }

  function renderDrawer() {
    const open = store.get().ui.drawerOpen;
    burger.setAttribute("aria-expanded", String(open));
    const label = open ? __("Close navigation") : __("Open navigation");
    burger.setAttribute("aria-label", label);
    burger.title = label;
  }

  burger.addEventListener("click", () => setUi({ drawerOpen: !store.get().ui.drawerOpen }));
  newBtn.addEventListener("click", newChat);
  const unsubs = [
    store.subscribe(renderRoute, ["route"]),
    store.subscribe(renderTitle, ["messages"]),
    store.subscribe(renderDrawer, ["ui"]),
  ];
  renderRoute();
  renderDrawer();

  return () => {
    unsubs.forEach((u) => u());
    picker.destroy();
  };
}
