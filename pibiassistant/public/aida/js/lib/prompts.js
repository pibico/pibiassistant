import * as api from "./api.js";

const MAX_PINNED = 5;
const MAX_OTHERS = 8;
const LONG_TEXT = /description|content|message|text|body/i;

let catalog = null;

export function slashQuery(text) {
  if (!text || text[0] !== "/") return null;
  const rest = text.slice(1);
  return /\s/.test(rest) ? null : rest;
}

export function normalizeCatalog(data) {
  const d = data && typeof data === "object" ? data : {};
  return {
    templates: Array.isArray(d.templates) ? d.templates.filter((t) => t && t.name) : [],
    pinned: Array.isArray(d.pinned) ? d.pinned : [],
  };
}

export async function loadCatalog() {
  if (!catalog) {
    catalog = api
      .get("prompts.get_prompt_templates")
      .then(normalizeCatalog)
      .catch(() => {
        catalog = null;
        return normalizeCatalog(null);
      });
  }
  return catalog;
}

export function filterTemplates({ templates, pinned }, query) {
  const needle = String(query || "").toLowerCase();
  const hit = (t) =>
    !needle || [t.title, t.name, t.description].some((v) => String(v || "").toLowerCase().includes(needle));
  const pins = new Set(pinned);
  return [
    ...templates.filter((t) => pins.has(t.name) && hit(t)).slice(0, MAX_PINNED),
    ...templates.filter((t) => !pins.has(t.name) && hit(t)).slice(0, MAX_OTHERS),
  ];
}

export function argsOf(template) {
  return (Array.isArray(template.arguments) ? template.arguments : []).map((a, i) => ({
    ...a,
    name: a.name || `arg_${i}`,
    required: a.required !== false,
  }));
}

export function labelOf(name) {
  return String(name || "").replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function fieldKind(arg) {
  if (Array.isArray(arg.enum) && arg.enum.length) return "select";
  if (LONG_TEXT.test(arg.name)) return "textarea";
  if (arg.type === "number" || arg.type === "integer") return "number";
  if (arg.type === "email" || arg.type === "url") return arg.type;
  return "text";
}

export function fallbackPrompt(template, values) {
  let text = template.description || template.title || template.name;
  for (const [k, v] of Object.entries(values)) if (v) text += ` (${k}: ${v})`;
  return text;
}

export async function renderPrompt(template, values) {
  try {
    const res = await api.get("prompts.get_rendered_prompt", {
      prompt_name: template.name,
      arguments: JSON.stringify(values || {}),
    });
    if (res && res.success !== false && typeof res.prompt === "string" && res.prompt) return res.prompt;
  } catch {
    /* fall back to a plain sentence so the pick is never lost */
  }
  return fallbackPrompt(template, values || {});
}
