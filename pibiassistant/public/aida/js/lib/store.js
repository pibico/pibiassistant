export function createStore(initial) {
  let state = initial;
  const listeners = new Set();
  return {
    get: () => state,
    set(patch) {
      const changed = Object.keys(patch).filter((k) => patch[k] !== state[k]);
      if (!changed.length) return;
      state = { ...state, ...patch };
      for (const l of [...listeners]) {
        if (l.keys && !l.keys.some((k) => changed.includes(k))) continue;
        try {
          l.fn(state, changed);
        } catch {
          continue;
        }
      }
    },
    subscribe(fn, keys) {
      const entry = { fn, keys };
      listeners.add(entry);
      return () => listeners.delete(entry);
    },
  };
}

export const INITIAL_STATE = Object.freeze({
  user: { id: "", fullName: "", firstName: "", image: null },
  route: { name: "chat", sessionId: null },
  sessions: [],
  sessionsState: "idle",
  activeSessionId: null,
  messages: [],
  historyState: "idle",
  streaming: { active: false, key: null, stopping: false, slow: false },
  models: [],
  modelsState: "idle",
  autoDescription: "",
  selectedModel: "auto",
  prefs: { theme: "auto", density: "comfortable", showTimestamps: false },
  ui: { drawerOpen: false, connection: "connected", announce: "" },
});

export const store = createStore({ ...INITIAL_STATE });

export function setUi(patch) {
  store.set({ ui: { ...store.get().ui, ...patch } });
}
