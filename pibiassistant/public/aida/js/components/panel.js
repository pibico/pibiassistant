import { h, trapFocus, focusables } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { icon } from "./icons.js";

let seq = 0;

// Right slide panel (pibiCo guideline): backdrop, Esc, focus trap and focus restore.
export function openPanel({ title, body, footer = [], onClose }) {
  const previous = document.activeElement;
  const id = `aida-panel-${++seq}`;
  let release = () => {};
  let closed = false;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const close = () => {
    if (closed) return;
    closed = true;
    release();
    document.removeEventListener("keydown", onKey, true);
    panel.classList.remove("is-open");
    scrim.classList.remove("is-open");
    const finish = () => {
      scrim.remove();
      panel.remove();
      if (previous && previous.isConnected && previous.focus) previous.focus();
      if (onClose) onClose();
    };
    if (reduced) finish();
    else setTimeout(finish, 300);
  };
  const onKey = (e) => {
    if (e.key !== "Escape") return;
    e.preventDefault();
    e.stopPropagation();
    close();
  };

  const closeBtn = h("button", { type: "button", class: "aida-panel__close", "aria-label": __("Close"), onClick: close }, icon("x", 18));
  const scrim = h("div", { class: "aida-panel__scrim", onClick: close });
  const panel = h("div", { class: "aida-panel", role: "dialog", "aria-modal": "true", "aria-labelledby": id, tabindex: "-1" },
    h("div", { class: "aida-panel__header" }, h("h2", { class: "aida-panel__title", id }, title), closeBtn),
    h("div", { class: "aida-panel__body" }, body),
    h("div", { class: "aida-panel__footer" }, footer));
  (document.querySelector(".aida-app") || document.body).append(scrim, panel);
  release = trapFocus(panel);
  document.addEventListener("keydown", onKey, true);
  void panel.offsetWidth;
  panel.classList.add("is-open");
  scrim.classList.add("is-open");
  (focusables(panel.querySelector(".aida-panel__body"))[0] || closeBtn).focus({ preventScroll: true });
  return { close, panel };
}
