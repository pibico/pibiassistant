// Frappe-style translation helper for the SPA. The boot script may expose
// window.aida_messages ({English source: translation}); without it the
// English source is returned unchanged.
export function __(text, args) {
	const dict = (typeof window !== "undefined" && window.aida_messages) || {};
	let out = dict[text] || text;
	if (Array.isArray(args)) {
		out = out.replace(/\{(\d+)\}/g, (m, i) => (args[i] !== undefined ? args[i] : m));
	}
	return out;
}

export const isAidaMode = () => typeof window !== "undefined" && !!window.aida_mode;
