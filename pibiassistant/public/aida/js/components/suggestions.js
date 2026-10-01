import { h } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { icon } from "./icons.js";

function tiles() {
  return [
    { icon: "file", title: __("Summarise a document"), sub: __("Paste text or attach a file"), prompt: __("Summarise the document I will share with you.") },
    { icon: "mail", title: __("Draft a professional email"), sub: __("Tell me the context and tone"), prompt: __("Help me draft a professional email.") },
    { icon: "globe", title: __("Translate a text"), sub: __("Between Spanish, English and more"), prompt: __("Translate a text for me.") },
    { icon: "lightbulb", title: __("Explain a concept simply"), sub: __("Step by step, with examples"), prompt: __("Explain a concept to me in simple terms.") },
  ];
}

export function createSuggestions({ onPick }) {
  const grid = h("div", { class: "aida-tiles__grid" }, tiles().map((t, i) =>
    h("button", { type: "button", class: ["aida-tile", i % 2 ? "aida-tile--warm" : null], onClick: () => onPick(t.prompt) },
      h("span", { class: "aida-tile__icon", "aria-hidden": "true" }, icon(t.icon, 14)),
      h("span", { class: "aida-tile__body" },
        h("span", { class: "aida-tile__title" }, t.title),
        h("span", { class: "aida-tile__sub" }, t.sub)))));
  const el = h("section", { class: "aida-tiles" },
    h("p", { class: "aida-tiles__label" }, __("Or try one of these")), grid);
  return { el };
}
