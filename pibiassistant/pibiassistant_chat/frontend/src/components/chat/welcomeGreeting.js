import { __ } from "@/utils/i18n";

// Time-aware greeting + a friendly display name derived from the username.
export function greetingForHour(hour) {
	const h = Number.isFinite(hour) ? hour : 12;
	if (h < 5) return __("Good evening");
	if (h < 12) return __("Good morning");
	if (h < 17) return __("Good afternoon");
	return __("Good evening");
}

export function displayNameFromUser(user) {
	if (!user || user === "Guest") return __("there");
	const local = String(user).split("@")[0];
	const first = local.split(/[._-]/)[0] || local;
	return first.charAt(0).toUpperCase() + first.slice(1);
}

// "Monday · 6 July" — locale-aware pieces, ledger-label composition.
export function formatDateLabel(date = new Date()) {
	const weekday = date.toLocaleDateString(document.documentElement.lang || undefined, { weekday: "long" });
	const day = date.getDate();
	const month = date.toLocaleDateString(document.documentElement.lang || undefined, { month: "long" });
	return `${weekday} · ${day} ${month}`;
}

// Compact relative time for Resume rows. Frappe datetimes are naive strings.
export function relativeTimeLabel(value, now = new Date()) {
	const then = value instanceof Date ? value : new Date(String(value).replace(" ", "T"));
	const diffMs = now - then;
	const mins = Math.floor(diffMs / 60000);
	if (mins < 1) return __("just now");
	if (mins < 60) return __("{0}m ago", [mins]);
	const hours = Math.floor(mins / 60);
	if (hours < 24 && then.getDate() === now.getDate()) return __("{0}h ago", [hours]);
	const days = Math.floor(diffMs / 86400000);
	if (days <= 1) return __("yesterday");
	if (days < 7) return __("{0}d ago", [days]);
	const month = then.toLocaleDateString(undefined, { month: "short" });
	return `${then.getDate()} ${month}`;
}
