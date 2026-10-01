import { store } from "./store.js";
import { local, KEYS } from "./storage.js";
import { apply } from "./theme.js";

const THEMES = ["light", "dark", "auto"];
const DENSITIES = ["comfortable", "compact"];

function bootTheme() {
  const t = (globalThis.window || globalThis).theme;
  return t === "dark" || t === "light" ? t : "auto";
}

function applyDensity(density) {
  if (typeof document !== "undefined") document.documentElement.dataset.density = density;
}

export function getPrefs() {
  return store.get().prefs;
}

export function init() {
  const theme = local.get(KEYS.theme);
  const density = local.get(KEYS.density);
  const prefs = {
    theme: THEMES.includes(theme) ? theme : bootTheme(),
    density: DENSITIES.includes(density) ? density : "comfortable",
    showTimestamps: local.get(KEYS.timestamps) === "1",
  };
  store.set({ prefs });
  apply(prefs.theme);
  applyDensity(prefs.density);
}

export function setPref(key, value) {
  const prefs = getPrefs();
  if (key === "theme" && THEMES.includes(value)) {
    local.set(KEYS.theme, value);
    apply(value);
  } else if (key === "density" && DENSITIES.includes(value)) {
    local.set(KEYS.density, value);
    applyDensity(value);
  } else if (key === "showTimestamps" && typeof value === "boolean") {
    local.set(KEYS.timestamps, value ? "1" : "0");
  } else return;
  store.set({ prefs: { ...prefs, [key]: value } });
}
