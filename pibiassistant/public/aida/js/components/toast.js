import { h } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { icon } from "./icons.js";

const MAX_VISIBLE = 3;
const live = [];

function host() {
  let el = document.getElementById("aida-toasts");
  if (!el) {
    el = h("div", { class: "aida-toasts", id: "aida-toasts", "aria-live": "polite" });
    (document.querySelector(".aida-app") || document.body).appendChild(el);
  }
  return el;
}

export function show({ message, type = "info", timeout = type === "error" ? 8000 : 4000, action } = {}) {
  let timer = null;
  const dismiss = () => {
    clearTimeout(timer);
    const i = live.indexOf(entry);
    if (i >= 0) live.splice(i, 1);
    el.remove();
  };
  const entry = { dismiss };
  const el = h("div", { class: ["aida-toast", `is-${type}`], role: type === "error" ? "alert" : "status" },
    h("span", { class: "aida-toast__text" }, message),
    action && h("button", {
      type: "button", class: "aida-link-btn",
      onClick: () => { action.onClick(); dismiss(); },
    }, action.label),
    h("button", {
      type: "button", class: "aida-icon-btn aida-toast__close",
      "aria-label": __("Dismiss"), title: __("Dismiss"), onClick: dismiss,
    }, icon("x", 16)));
  host().appendChild(el);
  live.push(entry);
  while (live.length > MAX_VISIBLE) live[0].dismiss();
  if (timeout > 0) timer = setTimeout(dismiss, timeout);
  return { dismiss };
}
