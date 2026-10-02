import { h } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { icon } from "./icons.js";

export function tiles() {
  return [
    { icon: "file", title: __("Create a purchase invoice from a PDF"), sub: __("Attach the supplier invoice"), prompt: __("Create a purchase invoice from the PDF I will attach.") },
    { icon: "mail", title: __("Who owes us money?"), sub: __("Overdue receivables by customer"), prompt: __("Show me the overdue sales invoices grouped by customer.") },
    { icon: "globe", title: __("Check stock levels"), sub: __("Items running low"), prompt: __("Which items are below their reorder level?") },
    { icon: "lightbulb", title: __("Summarise my hours"), sub: __("Timesheets this week"), prompt: __("Summarise the hours logged in my timesheets this week.") },
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
