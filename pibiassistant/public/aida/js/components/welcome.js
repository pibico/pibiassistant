import { h } from "../lib/dom.js";
import { __, getLang } from "../lib/i18n.js";
import { store } from "../lib/store.js";
import { dateLabel, greetingText } from "../lib/greeting.js";
import { createSuggestions } from "./suggestions.js";

const AVATAR_SRC = "/assets/pibiassistant/chat/widget/aida-icon.svg";

export function createWelcome({ composerEl, onPick }) {
  const date = h("p", { class: "aida-welcome__date" });
  const greeting = h("h1", { class: "aida-welcome__greeting" });
  const slot = h("div", { class: "aida-welcome__composer" }, composerEl);
  const suggestions = createSuggestions({ onPick });
  const el = h(
    "section",
    { class: "aida-welcome" },
    h(
      "div",
      { class: "aida-welcome__inner" },
      h(
        "header",
        { class: "aida-welcome__header" },
        h("div", { class: "aida-welcome__text" }, date, greeting, h("p", { class: "aida-welcome__sub" }, __("What should we work through today?"))),
        h("img", { class: "aida-welcome__avatar", src: AVATAR_SRC, alt: "", width: 96, height: 96 }),
      ),
      h("div", { class: "aida-welcome__rule", "aria-hidden": "true" }),
      slot,
      suggestions.el,
    ),
  );

  function refresh() {
    const now = new Date();
    date.textContent = dateLabel(now, getLang());
    greeting.textContent = greetingText(now, store.get().user.firstName || null);
  }

  refresh();
  return { el, slot, refresh, destroy() {} };
}
