import { session } from "./storage.js";

export function readHandoff(key, user) {
  const raw = session.get(key);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && parsed.id && parsed.user === user) {
      return String(parsed.id);
    }
  } catch {
    return null;
  }
  return null;
}

export function writeHandoff(key, id, user) {
  if (!id) return false;
  return session.set(key, JSON.stringify({ id, user: user || null }));
}

export function clearHandoff(key) {
  session.remove(key);
}
