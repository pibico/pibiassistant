import { h, focusables } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { store } from "../lib/store.js";
import { logout } from "../lib/api.js";
import { initialOf } from "../lib/greeting.js";
import { icon } from "./icons.js";

export function createUserMenu() {
  const { user } = store.get();
  const name = user.fullName || user.id;
  const menuId = "aida-user-menu";

  const logoutBtn = h("button", { type: "button", class: "aida-menu__item", role: "menuitem" }, icon("logout", 16), __("Log out"));
  const menu = h(
    "div",
    { class: "aida-menu aida-user__menu", id: menuId, role: "menu", "aria-label": __("User menu"), hidden: true },
    h("div", { class: "aida-user__who" }, h("p", { class: "aida-user__who-name" }, name), user.fullName ? h("p", { class: "aida-user__who-id" }, user.id) : null),
    h("div", { class: "aida-menu__divider", role: "separator" }),
    h("a", { class: "aida-menu__item", href: "/aida/settings", role: "menuitem" }, icon("settings", 16), __("Settings")),
    h("div", { class: "aida-menu__divider", role: "separator" }),
    logoutBtn,
  );
  const trigger = h(
    "button",
    { type: "button", class: "aida-user__trigger", "aria-haspopup": "menu", "aria-expanded": "false", "aria-controls": menuId, "aria-label": __("User menu") },
    h("span", { class: "aida-user__avatar", "aria-hidden": "true" }, initialOf({ fullName: user.fullName, userId: user.id })),
    h("span", { class: "aida-user__name" }, name),
    icon("chevron-down", 16),
  );
  const el = h("div", { class: "aida-user" }, menu, trigger);

  const isOpen = () => !menu.hidden;

  function setOpen(open, returnFocus = false) {
    menu.hidden = !open;
    el.classList.toggle("is-open", open);
    trigger.setAttribute("aria-expanded", String(open));
    if (open) focusables(menu)[0]?.focus();
    else if (returnFocus) trigger.focus();
  }

  function onKeydown(e) {
    if (!isOpen()) return;
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false, true);
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const items = focusables(menu);
    const i = items.indexOf(document.activeElement);
    const step = e.key === "ArrowDown" ? 1 : -1;
    items[(i + step + items.length) % items.length]?.focus();
  }

  const onPointerDown = (e) => {
    if (isOpen() && !el.contains(e.target)) setOpen(false);
  };

  trigger.addEventListener("click", () => setOpen(!isOpen()));
  menu.addEventListener("click", (e) => {
    if (e.target.closest(".aida-menu__item")) setOpen(false);
  });
  logoutBtn.addEventListener("click", () => logout());
  document.addEventListener("keydown", onKeydown);
  document.addEventListener("pointerdown", onPointerDown);

  return {
    el,
    destroy() {
      document.removeEventListener("keydown", onKeydown);
      document.removeEventListener("pointerdown", onPointerDown);
    },
  };
}
