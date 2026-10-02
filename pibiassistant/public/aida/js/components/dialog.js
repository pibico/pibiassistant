import { h } from "../lib/dom.js";
import { openPanel } from "./panel.js";

export function confirm({ title, message, confirmLabel, cancelLabel, danger = false }) {
  return new Promise((resolve) => {
    const decide = (value) => {
      resolve(value);
      handle.close();
    };
    const footer = [
      h("button", { type: "button", class: "aida-btn aida-btn--outline", onClick: () => decide(false) }, cancelLabel),
      h("button", {
        type: "button", class: ["aida-btn", danger ? "aida-btn--danger" : "aida-btn--primary"], onClick: () => decide(true),
      }, confirmLabel),
    ];
    const handle = openPanel({
      title,
      body: h("p", { class: "aida-panel__message" }, message),
      footer,
      onClose: () => resolve(false),
    });
  });
}
