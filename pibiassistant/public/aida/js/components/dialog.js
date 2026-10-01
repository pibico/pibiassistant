import { h, trapFocus, focusables } from "../lib/dom.js";

let seq = 0;

export function confirm({ title, message, confirmLabel, cancelLabel, danger = false }) {
  return new Promise((resolve) => {
    const previous = document.activeElement;
    const id = `aida-dialog-${++seq}`;
    let release = () => {};
    const close = (result) => {
      release();
      document.removeEventListener("keydown", onKey, true);
      scrim.remove();
      dialog.remove();
      if (previous && previous.focus) previous.focus();
      resolve(result);
    };
    const onKey = (e) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      e.stopPropagation();
      close(false);
    };
    const cancelBtn = h("button", {
      type: "button", class: "aida-btn aida-btn--outline", onClick: () => close(false),
    }, cancelLabel);
    const okBtn = h("button", {
      type: "button", class: ["aida-btn", danger ? "aida-btn--danger" : "aida-btn--primary"],
      onClick: () => close(true),
    }, confirmLabel);
    const scrim = h("div", { class: "aida-dialog__scrim", onClick: () => close(false) });
    const dialog = h("div", {
      class: "aida-dialog", role: "dialog", "aria-modal": "true", "aria-labelledby": id,
    },
      h("h2", { class: "aida-dialog__title", id }, title),
      h("p", { class: "aida-dialog__message" }, message),
      h("div", { class: "aida-dialog__actions" }, cancelBtn, okBtn));
    const root = document.querySelector(".aida-app") || document.body;
    root.append(scrim, dialog);
    release = trapFocus(dialog);
    document.addEventListener("keydown", onKey, true);
    (focusables(dialog)[0] || dialog).focus();
  });
}
