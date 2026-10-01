import { h } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { store } from "../lib/store.js";
import { setPref } from "../lib/preferences.js";
import { icon } from "../components/icons.js";

function segmented(label, options, key) {
  const buttons = options.map(([value, text]) => h("button", {
    type: "button", class: "aida-seg__btn", role: "radio", dataset: { value },
    onClick: () => setPref(key, value),
  }, text));
  const el = h("div", { class: "aida-seg", role: "radiogroup", "aria-label": label }, buttons);
  el.addEventListener("keydown", (e) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const i = buttons.findIndex((b) => b.getAttribute("aria-checked") === "true");
    const next = buttons[(i + step + buttons.length) % buttons.length];
    setPref(key, next.dataset.value);
    next.focus();
  });
  const sync = (value) => buttons.forEach((b) => {
    const on = b.dataset.value === value;
    b.setAttribute("aria-checked", String(on));
    b.tabIndex = on ? 0 : -1;
    b.classList.toggle("is-active", on);
  });
  return { el, sync };
}

function row(title, hint, control, id) {
  return h("div", { class: "aida-row" },
    h("div", { class: "aida-row__text" },
      h("div", { class: "aida-row__label", id }, title),
      h("p", { class: "aida-row__hint" }, hint)),
    control);
}

export function mountSettings(container) {
  const theme = segmented(__("Theme"),
    [["light", __("Light")], ["dark", __("Dark")], ["auto", __("Auto")]], "theme");
  const density = segmented(__("Density"),
    [["comfortable", __("Comfortable")], ["compact", __("Compact")]], "density");
  const stamps = h("button", {
    type: "button", class: "aida-switch", role: "switch", "aria-labelledby": "aida-pref-stamps",
    onClick: () => setPref("showTimestamps", !store.get().prefs.showTimestamps),
  }, h("span", { class: "aida-switch__thumb" }));

  const root = h("section", { class: "aida-settings" },
    h("a", { class: "aida-back", href: "/aida/chat" }, icon("arrow-left", 18), __("Back to chat")),
    h("div", { class: "aida-card" },
      h("h2", { class: "aida-card__title" }, __("Appearance")),
      h("p", { class: "aida-card__desc" },
        __("Personalise how AIDA looks. These settings apply to this browser only.")),
      row(__("Theme"), __("Auto follows your device setting."), theme.el),
      row(__("Density"), __("Compact reduces spacing in the conversation."), density.el),
      row(__("Show message timestamps"),
        __("Show the time under your own messages. Replies always show it."), stamps, "aida-pref-stamps")));

  const render = ({ prefs }) => {
    theme.sync(prefs.theme);
    density.sync(prefs.density);
    stamps.setAttribute("aria-checked", String(prefs.showTimestamps));
    stamps.classList.toggle("is-on", prefs.showTimestamps);
  };
  render(store.get());
  const off = store.subscribe(render, ["prefs"]);
  container.appendChild(root);
  return { destroy() { off(); root.remove(); } };
}
