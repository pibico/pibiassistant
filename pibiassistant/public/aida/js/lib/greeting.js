import { __ } from "./i18n.js";

export function partOfDay(hour) {
  if (hour < 5) return "Good evening";
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export function firstNameOf({ fullName, userId }) {
  const full = (fullName || "").trim();
  if (full && full !== "Guest" && full !== userId) return full.split(/\s+/)[0];
  const local = String(userId || "").split("@")[0];
  if (!local || local === "Guest") return null;
  const piece = local.split(/[._-]/).find(Boolean);
  return piece ? piece.charAt(0).toUpperCase() + piece.slice(1) : null;
}

export function greetingText(date, name) {
  const part = __(partOfDay(date.getHours()));
  return name ? `${part}, ${name}.` : `${part}.`;
}

export function dateLabel(date, lang) {
  const weekday = date.toLocaleDateString(lang, { weekday: "long" });
  const day = date.toLocaleDateString(lang, { day: "numeric" });
  const month = date.toLocaleDateString(lang, { month: "long" });
  return `${weekday} · ${day} ${month}`;
}

export function initialOf({ fullName, userId }) {
  const src = (fullName || "").trim() || userId || "U";
  return src.charAt(0).toUpperCase() || "U";
}
