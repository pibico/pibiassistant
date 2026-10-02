import { h, clear } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { setUi } from "../lib/store.js";
import { argsOf, fieldKind, filterTemplates, labelOf, loadCatalog, renderPrompt, slashQuery } from "../lib/prompts.js";
import { openPanel } from "./panel.js";
import { icon } from "./icons.js";

let seq = 0;

function fieldNode(arg, id) {
  const common = { id, name: arg.name, required: arg.required };
  const kind = fieldKind(arg);
  const placeholder = arg.default ? __("Default: {0}", String(arg.default)) : __("Enter {0}…", labelOf(arg.name).toLowerCase());
  let control;
  if (kind === "select") {
    control = h("select", { ...common, class: "aida-field__input" },
      h("option", { value: "", disabled: true, selected: !arg.default }, __("Select an option…")),
      arg.enum.map((o) => h("option", { value: String(o), selected: String(o) === String(arg.default) }, String(o))));
  } else if (kind === "textarea") {
    control = h("textarea", { ...common, class: "aida-field__input", rows: "3", placeholder });
  } else {
    control = h("input", { ...common, class: "aida-field__input", type: kind, placeholder });
  }
  if (kind !== "select" && arg.default) control.value = String(arg.default);
  return h("div", { class: "aida-field" },
    h("label", { class: "aida-field__label", for: id }, labelOf(arg.name), arg.required ? " *" : null),
    arg.description ? h("p", { class: "aida-field__hint" }, arg.description) : null,
    control);
}

export function collectValues(form, args) {
  const values = {};
  for (const arg of args) {
    const v = form.elements[arg.name] ? form.elements[arg.name].value : "";
    if (v !== "") values[arg.name] = v;
  }
  return values;
}

// "/" at the start of the composer lists the Prompt Templates; a pick lands in the box for review, never auto-sent
export function createPromptPicker({ input, onApply }) {
  const listId = `aida-slash-${++seq}`;
  const list = h("div", { class: "aida-slash__list", role: "listbox", id: listId, "aria-label": __("Prompt templates") });
  const el = h("div", { class: "aida-slash", hidden: true }, list);
  let rows = [];
  let active = 0;
  let open = false;
  let token = 0;

  function setOpen(next) {
    open = next;
    el.hidden = !next;
    input.setAttribute("aria-expanded", next ? "true" : "false");
    if (next) input.setAttribute("aria-controls", listId);
    else input.removeAttribute("aria-activedescendant");
  }

  function mark() {
    [...list.children].forEach((node, i) => node.setAttribute("aria-selected", i === active ? "true" : "false"));
    const cur = list.children[active];
    if (cur) {
      input.setAttribute("aria-activedescendant", cur.id);
      cur.scrollIntoView({ block: "nearest" });
    }
  }

  function render(matches) {
    rows = matches;
    active = 0;
    clear(list);
    matches.forEach((t, i) => {
      list.append(h("div", {
        class: "aida-slash__row", role: "option", id: `${listId}-${i}`, "aria-selected": "false",
        onMousedown: (e) => { e.preventDefault(); choose(i); },
      },
      h("span", { class: "aida-slash__icon", "aria-hidden": "true" }, icon("bolt", 14)),
      h("span", { class: "aida-slash__text" },
        h("span", { class: "aida-slash__title" }, t.title || t.name),
        t.description ? h("span", { class: "aida-slash__desc" }, t.description) : null)));
    });
    if (!matches.length) list.append(h("p", { class: "aida-slash__empty" }, __("No templates match.")));
    mark();
  }

  async function update(text) {
    const query = slashQuery(text);
    const mine = ++token;
    if (query === null) return setOpen(false);
    const catalog = await loadCatalog();
    if (mine !== token) return;
    if (!catalog.templates.length) return setOpen(false);
    render(filterTemplates(catalog, query));
    setOpen(true);
    setUi({ announce: rows.length ? __("{0} templates available", rows.length) : __("No templates match.") });
  }

  function close() {
    token++;
    setOpen(false);
  }

  function choose(i) {
    const template = rows[i];
    if (!template) return;
    close();
    input.value = "";
    onApply("", false);
    pick(template);
  }

  async function pick(template) {
    const args = argsOf(template);
    if (!args.length) return onApply(await renderPrompt(template, {}), true);
    const form = h("form", { class: "aida-template-form" },
      template.description ? h("p", { class: "aida-panel__message" }, template.description) : null,
      args.map((a, i) => fieldNode(a, `${listId}-f${i}`)));
    const use = h("button", { type: "submit", class: "aida-btn aida-btn--primary" }, __("Use"));
    const cancel = h("button", { type: "button", class: "aida-btn aida-btn--outline" }, __("Cancel"));
    form.append(h("div", { class: "aida-template-form__actions" }, cancel, use));
    const panel = openPanel({ title: template.title || template.name, body: form });
    cancel.addEventListener("click", () => panel.close());
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const values = collectValues(form, args);
      use.disabled = true;
      const text = await renderPrompt(template, values);
      panel.close();
      onApply(text, true);
    });
  }

  function handleKey(e) {
    if (!open || e.isComposing) return false;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!rows.length) return false;
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + rows.length) % rows.length;
      mark();
    } else if ((e.key === "Enter" && !e.shiftKey) || e.key === "Tab") {
      if (!rows.length) return false;
      choose(active);
    } else if (e.key === "Escape") {
      close();
    } else return false;
    e.preventDefault();
    return true;
  }

  const onOutside = (e) => {
    if (open && !el.contains(e.target) && e.target !== input) close();
  };
  document.addEventListener("mousedown", onOutside);
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-expanded", "false");

  return { el, update, handleKey, close, isOpen: () => open, destroy: () => document.removeEventListener("mousedown", onOutside) };
}
