const PH = {
  chat: "chats",
  desk: "house",
  plus: "plus",
  trash: "trash",
  archive: "archive",
  check: "check",
  x: "x",
  "chevron-down": "caret-down",
  "chevron-up": "caret-up",
  settings: "gear",
  logout: "sign-out",
  paperclip: "paperclip",
  mic: "microphone",
  send: "paper-plane-tilt",
  stop: "stop",
  copy: "copy",
  "arrow-down": "arrow-down",
  "arrow-left": "arrow-left",
  menu: "list",
  bolt: "lightning",
  alert: "warning",
  refresh: "arrows-clockwise",
  file: "file-text",
  mail: "envelope-simple",
  globe: "globe",
  lightbulb: "lightbulb",
  user: "user",
  sun: "sun",
  moon: "moon",
};

export function icon(name, size = 20) {
  const ph = PH[name];
  if (!ph) throw new Error(`Unknown icon: ${name}`);
  const el = document.createElement("i");
  el.className = `ph ph-${ph} aida-icon`;
  el.setAttribute("aria-hidden", "true");
  el.style.fontSize = `${size}px`;
  return el;
}
