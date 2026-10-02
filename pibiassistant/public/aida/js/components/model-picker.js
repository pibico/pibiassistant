import { h, clear } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { store } from "../lib/store.js";
import { local, KEYS } from "../lib/storage.js";
import * as api from "../lib/api.js";
import { icon } from "./icons.js";

function setSelectedModel(id) {
  local.set(KEYS.model, id);
  store.set({ selectedModel: id });
}

export async function loadModels() {
  store.set({ modelsState: "loading" });
  try {
    const res = await api.get("get_available_models");
    const models = res && Array.isArray(res.models) ? res.models : null;
    if (!models || !models.length) throw new Error("no models");
    store.set({
      models, modelsState: "ready",
      autoDescription: (res.auto_mode && res.auto_mode.description) || "",
    });
    const sel = store.get().selectedModel;
    if (sel !== "auto" && !models.some((m) => m.model_id === sel)) setSelectedModel("auto");
  } catch (err) {
    console.error("get_available_models failed", err);
    store.set({ models: [], modelsState: "error" });
  }
}

function labelOf(state) {
  if (state.selectedModel === "auto") return __("Auto");
  const m = state.models.find((x) => x.model_id === state.selectedModel);
  if (m) return m.display_name;
  return state.modelsState === "ready" ? __("Auto") : state.selectedModel;
}

export function createModelPicker() {
  let open = false;
  let active = 0;
  let options = [];
  const uid = `aida-model-${Math.random().toString(36).slice(2, 8)}`;

  const label = h("span", { class: "aida-model__label" });
  const trigger = h("button", {
    type: "button", class: "aida-model__trigger", "aria-haspopup": "listbox", "aria-expanded": "false",
    "aria-controls": uid, title: __("Select model"), onClick: () => toggle(!open), onKeydown: onTriggerKey,
  }, icon("bolt", 16), label, icon("chevron-down", 16));
  const panel = h("div", { class: "aida-model__panel", hidden: true });
  const el = h("div", { class: "aida-model" }, trigger, panel);

  function toggle(next) {
    open = next;
    trigger.setAttribute("aria-expanded", String(open));
    panel.hidden = !open;
    if (open) {
      const st = store.get();
      if (st.modelsState === "idle" || st.modelsState === "error") loadModels();
      render();
      active = Math.max(0, options.findIndex((o) => o.id === st.selectedModel));
      highlight();
    } else {
      trigger.removeAttribute("aria-activedescendant");
    }
  }

  function choose(id) {
    setSelectedModel(id);
    toggle(false);
    trigger.focus();
  }

  function option(id, name, sub, selected, idx, withBolt) {
    return h("li", {
      id: `${uid}-${idx}`, role: "option", class: ["aida-model__option", selected ? "is-selected" : null],
      "aria-selected": String(selected), onClick: () => choose(id),
    },
      withBolt ? icon("bolt", 16) : null,
      h("span", { class: "aida-model__text" },
        h("span", { class: "aida-model__name" }, name),
        sub ? h("span", { class: "aida-model__sub" }, sub) : null),
      selected ? icon("check", 18) : null);
  }

  function render() {
    const st = store.get();
    label.textContent = labelOf(st);
    options = [];
    clear(panel);
    if (!open) return;
    if (st.modelsState === "loading") {
      panel.appendChild(h("div", { class: "aida-model__state", role: "status" },
        h("span", { class: "aida-spinner", "aria-hidden": "true" }), __("Loading models...")));
      return;
    }
    const list = h("ul", { class: "aida-model__list", id: uid, role: "listbox", "aria-label": __("Select model") });
    options.push({ id: "auto" });
    list.appendChild(option("auto", __("Auto"), st.autoDescription || __("Automatically selects the best model"),
      st.selectedModel === "auto", 0, true));
    const groups = new Map();
    st.models.forEach((m) => groups.set(m.provider, [...(groups.get(m.provider) || []), m]));
    groups.forEach((items, provider) => {
      list.appendChild(h("li", { class: "aida-model__group", role: "presentation" }, provider));
      items.forEach((m) => {
        options.push({ id: m.model_id });
        list.appendChild(option(m.model_id, m.display_name, "", st.selectedModel === m.model_id, options.length - 1, false));
      });
    });
    panel.appendChild(list);
    if (st.modelsState === "error") {
      panel.appendChild(h("div", { class: "aida-model__state is-error", role: "alert" },
        h("span", null, __("Couldn't load the models.")),
        h("button", { type: "button", class: "aida-btn aida-btn--outline", onClick: () => loadModels() }, __("Retry"))));
    } else if (!st.models.length) {
      panel.appendChild(h("div", { class: "aida-model__state" }, __("No models available")));
    }
    if (open) highlight();
  }

  function highlight() {
    const items = panel.querySelectorAll("[role=option]");
    items.forEach((li, i) => li.classList.toggle("is-active", i === active));
    const cur = items[active];
    if (cur) {
      trigger.setAttribute("aria-activedescendant", cur.id);
      cur.scrollIntoView({ block: "nearest" });
    }
  }

  function onTriggerKey(e) {
    if (!open) {
      if (["ArrowDown", "ArrowUp"].includes(e.key)) { e.preventDefault(); toggle(true); }
      return;
    }
    const last = options.length - 1;
    if (e.key === "Escape") { e.preventDefault(); toggle(false); }
    else if (e.key === "ArrowDown") { e.preventDefault(); active = Math.min(last, active + 1); highlight(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); active = Math.max(0, active - 1); highlight(); }
    else if (e.key === "Home") { e.preventDefault(); active = 0; highlight(); }
    else if (e.key === "End") { e.preventDefault(); active = last; highlight(); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (options[active]) choose(options[active].id); }
    else if (e.key === "Tab") toggle(false);
  }

  const onOutside = (e) => { if (open && !el.contains(e.target)) toggle(false); };
  document.addEventListener("pointerdown", onOutside);
  const unsub = store.subscribe(render, ["models", "modelsState", "selectedModel", "autoDescription"]);
  render();

  return {
    el,
    destroy() {
      unsub();
      document.removeEventListener("pointerdown", onOutside);
    },
  };
}
