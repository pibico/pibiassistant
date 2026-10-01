export const KEYS = {
  theme: "aida_theme",
  density: "aida_density",
  timestamps: "aida_show_timestamps",
  model: "aida_selected_model",
  handoffIn: "pao_active_session",
  handoffOut: "pao_widget_session",
};

function wrap(name) {
  return {
    get(key, fallback = null) {
      try {
        const v = globalThis[name].getItem(key);
        return v === null ? fallback : v;
      } catch {
        return fallback;
      }
    },
    set(key, value) {
      try {
        globalThis[name].setItem(key, String(value));
        return true;
      } catch {
        return false;
      }
    },
    remove(key) {
      try {
        globalThis[name].removeItem(key);
      } catch {
        /* storage unavailable */
      }
    },
  };
}

export const local = wrap("localStorage");
export const session = wrap("sessionStorage");
