let override = null;

export function setMessages(dict) {
  override = dict;
}

function dictionary() {
  return override || globalThis.aida_messages || null;
}

export function __(text, ...args) {
  const dict = dictionary();
  let out = (dict && dict[text]) || text;
  out = out.replace(/\{(\d+)\}/g, (m, n) => (args[n] !== undefined ? String(args[n]) : m));
  return out;
}

export function getLang() {
  return globalThis.aida_lang || "en";
}
