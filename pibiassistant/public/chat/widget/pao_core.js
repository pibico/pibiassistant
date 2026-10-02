// pibiAssistant - AIDA
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

/**
 * AidaCore - Shared functionality for AIDA widget and full-page assistant
 *
 * This module provides:
 * - Socket.IO streaming handlers
 * - Message formatting
 * - API wrappers
 * - Session management
 */
// DOMPurify configuration for LLM-rendered markdown.
//
// Why an allowlist: the widget used to call $.html() on raw Showdown output
// (see 2026-04-21 security audit). Showdown's raw-HTML-
// passthrough mode made every assistant message a stored-XSS vector. We
// sanitise at the single render boundary — PAOCore.format_message — so
// downstream sinks (widget_streaming, widget_richblocks, widget_onboarding)
// stay unchanged. The config preserves the markdown/rich-block element set
// while dropping <script>, event handlers (onerror=, onclick=, …), inline
// javascript: and data: URIs, and framing tags.
const _PAO_PURIFY_CONFIG = {
	ALLOWED_TAGS: [
		"a",
		"b",
		"blockquote",
		"br",
		"code",
		"del",
		"details",
		"div",
		"em",
		"h1",
		"h2",
		"h3",
		"h4",
		"h5",
		"h6",
		"hr",
		"i",
		"img",
		"ins",
		"li",
		"ol",
		"p",
		"pre",
		"s",
		"span",
		"strong",
		"sub",
		"summary",
		"sup",
		"table",
		"tbody",
		"td",
		"tfoot",
		"th",
		"thead",
		"tr",
		"u",
		"ul",
	],
	ALLOWED_ATTR: [
		"href",
		"target",
		"rel",
		"title",
		"alt",
		"src",
		"class",
		"id",
		"colspan",
		"rowspan",
		"align",
		"open",
	],
	// Force-open user links in a new tab with a safe rel (DOMPurify native hook).
	ADD_ATTR: ["target"],
	ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|ftp|tel):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
	FORBID_TAGS: [
		"script",
		"iframe",
		"object",
		"embed",
		"style",
		"form",
		"input",
		"textarea",
		"button",
		"link",
		"meta",
	],
	FORBID_ATTR: [
		"onerror",
		"onload",
		"onclick",
		"onmouseover",
		"onfocus",
		"onblur",
		"onchange",
		"onsubmit",
		"srcdoc",
	],
};

let _pao_purify_hooks_installed = false;

function _pao_install_purify_hooks() {
	if (_pao_purify_hooks_installed) return;
	if (typeof DOMPurify === "undefined" || !DOMPurify.addHook) return;

	// Harden links rendered from assistant markdown:
	//   - force target="_blank" (opens in new tab, keeps Desk alive)
	//   - force rel="noopener noreferrer" to block reverse tabnabbing
	DOMPurify.addHook("afterSanitizeAttributes", function (node) {
		if (node.tagName === "A" && node.hasAttribute("href")) {
			node.setAttribute("target", "_blank");
			node.setAttribute("rel", "noopener noreferrer");
		}
	});

	_pao_purify_hooks_installed = true;
}

// A single pass leaves a tag behind whenever removing one splices a new one
// together — "<scr<script>ipt>" becomes "<script>". Repeat to a fixpoint so
// the result cannot contain a tag however the input was nested.
function _strip_tags_completely(text) {
	let previous;
	do {
		previous = text;
		text = text.replace(/<[^>]*>/g, "");
	} while (text !== previous);
	return text;
}

function _pao_sanitize_html(html) {
	if (typeof DOMPurify === "undefined" || !DOMPurify.sanitize) {
		// Fail closed: if DOMPurify failed to load, strip ALL tags rather
		// than serving raw Showdown output. The widget degrades to plain
		// text but stays XSS-safe.
		return _strip_tags_completely(String(html || ""));
	}
	_pao_install_purify_hooks();
	return DOMPurify.sanitize(html, _PAO_PURIFY_CONFIG);
}

window.PAOCore = {
	/** Escape the five HTML-significant characters; no DOMPurify dependency. */
	escape_html(text) {
		return String(text == null ? "" : text)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;")
			.replace(/'/g, "&#39;");
	},

	/** Readable reason from a Frappe error body (_server_messages, then exception), tags stripped. */
	server_error_text(json) {
		try {
			const msgs = JSON.parse((json && json._server_messages) || "[]")
				.map((m) => {
					const v = JSON.parse(m);
					return v && v.message;
				})
				.filter(Boolean)
				.join(" ");
			return (msgs || (json && json.exception) || "").replace(/<[^>]*>/g, "").trim().slice(0, 160);
		} catch (e) {
			return "";
		}
	},

	/** POST multipart form data to a whitelisted method with the CSRF header. Returns { res, json }. */
	async post_form(url, form_data) {
		const csrf = window.csrf_token || (window.frappe && window.frappe.csrf_token) || "";
		const res = await fetch(url, {
			method: "POST",
			headers: { "X-Frappe-CSRF-Token": csrf },
			body: form_data,
			credentials: "same-origin",
		});
		let json = null;
		try {
			json = await res.json();
		} catch (e) {
			json = null;
		}
		return { res, json };
	},

	// Markdown converter instance (shared)
	markdown_converter: null,

	/**
	 * Initialize the markdown converter with table support
	 */
	init_markdown() {
		if (this.markdown_converter) return this.markdown_converter;

		if (!frappe.md2html) frappe.markdown("");
		if (frappe.md2html) {
			const ShowdownConstructor = frappe.md2html.constructor;
			this.markdown_converter = new ShowdownConstructor({
				tables: true,
				strikethrough: true,
				tasklists: true,
				smoothLivePreview: true,
				simpleLineBreaks: false,
				openLinksInNewWindow: true,
			});
		}
		return this.markdown_converter;
	},

	/**
	 * Format message content with markdown for assistant messages
	 * @param {string} content - Message content
	 * @param {string} role - 'user' or 'assistant'
	 * @returns {string} HTML-formatted content
	 */
	format_message(content, role = "user") {
		if (role === "assistant") {
			// Rich blocks: route through the rich block parser when available.
			// Rich-block renderers already _escapeHtml attrs and recurse
			// through format_message for bodies, so the end-to-end output
			// still passes through the sanitiser below.
			if (window.PAOWidgetRichBlocks && window.PAOWidgetRichBlocks.hasBlocks(content)) {
				return _pao_sanitize_html(window.PAOWidgetRichBlocks.process(content));
			}

			this.init_markdown();

			let html;
			if (this.markdown_converter) {
				html = this.markdown_converter.makeHtml(content);
			} else {
				html = frappe.markdown(content);
			}

			// Wrap tables in scrollable container
			html = html.replace(/<table>/g, '<div class="table-wrapper"><table>');
			html = html.replace(/<\/table>/g, "</table></div>");

			return _pao_sanitize_html(html);
		}

		// Simple formatting for user messages. User-supplied text can contain
		// angle brackets (</script>, <img onerror=…>) when users paste code or
		// craft messages — sanitise before the widget echoes their own input
		// back to them.
		let formatted = content
			.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
			.replace(/\*(.*?)\*/g, "<em>$1</em>")
			.replace(/`(.*?)`/g, "<code>$1</code>")
			.replace(/\n/g, "<br>");

		// Convert URLs to links
		formatted = formatted.replace(
			/(https?:\/\/[^\s]+)/g,
			'<a href="$1" target="_blank">$1</a>'
		);

		return _pao_sanitize_html(formatted);
	},

	/**
	 * Format timestamp for display
	 * @param {Date} date - Date object
	 * @returns {string} Formatted time string
	 */
	format_time(date) {
		const lang = (window.frappe && frappe.boot && frappe.boot.lang) || undefined;
		return date.toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
	},

	/**
	 * Generate a unique session ID
	 *
	 * The random half comes from crypto.getRandomValues, not Math.random: a
	 * session id names a conversation and is handed between the widget, the
	 * SPA and AR, so it should not be predictable from the clock. Unlike
	 * crypto.randomUUID, getRandomValues needs no secure context, so this
	 * works on an http:// dev bench too.
	 *
	 * @returns {string} Session ID
	 */
	generate_session_id() {
		const bytes = new Uint8Array(9);
		crypto.getRandomValues(bytes);
		const random = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
		return "pao_" + Date.now() + "_" + random;
	},

	// --- Avatar Helpers ---

	/**
	 * Get user avatar HTML
	 * @returns {string} HTML for user avatar
	 */
	get_user_avatar() {
		const user_image = frappe.user_info(frappe.session.user).image;
		if (user_image) {
			return `<img src="${PAOCore.escape_html(user_image)}" alt="" />`;
		}
		return `<div class="avatar-placeholder">${frappe.session.user[0].toUpperCase()}</div>`;
	},

	/**
	 * Get assistant avatar HTML
	 * @returns {string} HTML for assistant avatar
	 */
	get_assistant_avatar() {
		return `<img src="/assets/pibiassistant/chat/widget/aida-icon.svg" alt="AIDA" class="pao-avatar-img" style="width:100%;height:100%;border-radius:50%;">`;
	},

	// --- Context Extraction ---

	/**
	 * The Desk form currently on screen, or null when the route is not a form.
	 *
	 * Single accessor for the whole widget. Resolves the form from the routed
	 * form page rather than reading the `cur_frm` global directly: Frappe
	 * deprecates `cur_frm` because it holds whichever form last called
	 * refresh(), so it outlives navigation away from that form and can name a
	 * DocType the user is no longer looking at. Gating on the route first means
	 * the widget never hands the assistant stale form context.
	 *
	 * @returns {Object|null} A frappe.ui.form.Form with a loaded doc, or null.
	 */
	get_current_form() {
		const route = (frappe.get_route && frappe.get_route()) || [];
		if (route[0] !== "Form") return null;

		const layout = (frappe.router && frappe.router.doctype_layout) || route[1];
		const page = frappe.views && frappe.views.formview && frappe.views.formview[layout];
		// Fall back to the global only when the form page has not been
		// registered yet — the route says Form, so it cannot be stale here.
		// nosemgrep: frappe-cur-frm-usage
		const frm = (page && page.frm) || window.cur_frm;

		return frm && frm.doc ? frm : null;
	},

};

/**
 * PAOPanel - right slide panel (pibiCo guidelines) used instead of centered modals.
 * open({title, html|node, actions:[{label, kind, onClick, keepOpen}], dismissible, onClose}) -> {el, body, close}
 */
window.PAOPanel = (function () {
	const stack = [];
	let seq = 0;
	const esc = (s) => window.PAOCore.escape_html(s);
	const FOCUSABLE =
		'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
	let scrollLock = null;

	// Frappe reserves a scrollbar gutter on <html> (scrollbar-gutter: stable), which keeps a fixed layer 15px short of the edge
	function lockScroll() {
		if (scrollLock) return;
		const root = document.documentElement;
		const gutter = Math.max(0, Math.round(window.innerWidth - document.body.getBoundingClientRect().width));
		scrollLock = { overflow: root.style.overflow, pad: root.style.paddingRight, gutter: root.style.scrollbarGutter };
		root.style.scrollbarGutter = "auto";
		root.style.overflow = "hidden";
		if (gutter > 0) root.style.paddingRight = gutter + "px";
	}

	function unlockScroll() {
		if (!scrollLock) return;
		const root = document.documentElement;
		root.style.overflow = scrollLock.overflow;
		root.style.paddingRight = scrollLock.pad;
		root.style.scrollbarGutter = scrollLock.gutter;
		scrollLock = null;
	}

	function onKey(e) {
		const top = stack[stack.length - 1];
		if (!top) return;
		if (e.key === "Escape" && top.dismissible) {
			e.preventDefault();
			e.stopPropagation();
			top.close();
		} else if (e.key === "Tab") {
			const items = Array.from(top.panel.querySelectorAll(FOCUSABLE)).filter(
				(n) => n.offsetParent !== null
			);
			if (!items.length) {
				e.preventDefault();
				top.panel.focus();
				return;
			}
			const first = items[0];
			const last = items[items.length - 1];
			if (e.shiftKey && (document.activeElement === first || document.activeElement === top.panel)) {
				e.preventDefault();
				last.focus();
			} else if (!e.shiftKey && document.activeElement === last) {
				e.preventDefault();
				first.focus();
			}
		}
	}

	function open(opts) {
		opts = opts || {};
		const id = `pao-panel-${++seq}`;
		const dismissible = opts.dismissible !== false;
		const prevFocus = document.activeElement;
		const backdrop = document.createElement("div");
		backdrop.className = "pao-panel-backdrop";
		const panel = document.createElement("aside");
		panel.className = "pao-panel";
		panel.id = id;
		panel.tabIndex = -1;
		panel.setAttribute("role", "dialog");
		panel.setAttribute("aria-modal", "true");
		panel.setAttribute("aria-labelledby", `${id}-title`);
		panel.innerHTML = `
			<header class="pao-panel-header">
				<h2 class="pao-panel-title" id="${id}-title">${esc(opts.title || "")}</h2>
				${
					dismissible
						? `<button type="button" class="pao-panel-close" aria-label="${esc(
								window.__ ? __("Close") : "Close"
						  )}"><i class="ph ph-x" aria-hidden="true"></i></button>`
						: ""
				}
			</header>
			<div class="pao-panel-body"></div>
			<footer class="pao-panel-footer"></footer>`;
		const body = panel.querySelector(".pao-panel-body");
		if (opts.node) body.appendChild(opts.node);
		else body.innerHTML = opts.html || "";
		const footer = panel.querySelector(".pao-panel-footer");

		let closed = false;
		const entry = { panel, dismissible, close };
		function close() {
			if (closed) return;
			closed = true;
			const i = stack.indexOf(entry);
			if (i >= 0) stack.splice(i, 1);
			panel.classList.remove("active");
			backdrop.classList.remove("active");
			if (!stack.length) {
				document.removeEventListener("keydown", onKey, true);
				document.body.classList.remove("pao-panel-open");
				unlockScroll();
			}
			const done = () => {
				panel.remove();
				backdrop.remove();
			};
			const reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
			if (reduce) done();
			else setTimeout(done, 320);
			if (prevFocus && prevFocus.focus && document.contains(prevFocus)) {
				try {
					prevFocus.focus({ preventScroll: true });
				} catch (e) {
					/* element gone */
				}
			}
			if (typeof opts.onClose === "function") opts.onClose();
		}

		(opts.actions || []).forEach((a) => {
			const b = document.createElement("button");
			b.type = "button";
			b.className = `pao-panel-btn pao-panel-btn-${a.kind || "outline"}`;
			b.textContent = a.label;
			b.addEventListener("click", () => {
				if (!a.keepOpen) close();
				if (typeof a.onClick === "function") a.onClick(entry);
			});
			footer.appendChild(b);
		});
		if (!footer.children.length) footer.remove();

		if (dismissible) {
			backdrop.addEventListener("click", close);
			panel.querySelector(".pao-panel-close").addEventListener("click", close);
		}
		document.body.appendChild(backdrop);
		document.body.appendChild(panel);
		if (!stack.length) {
			document.addEventListener("keydown", onKey, true);
			lockScroll();
		}
		stack.push(entry);
		document.body.classList.add("pao-panel-open");
		requestAnimationFrame(() => {
			panel.classList.add("active");
			backdrop.classList.add("active");
			const target =
				panel.querySelector("[autofocus]") ||
				panel.querySelector(".pao-panel-body " + FOCUSABLE) ||
				panel.querySelector(".pao-panel-footer button") ||
				panel.querySelector(".pao-panel-close") ||
				panel;
			target.focus({ preventScroll: true });
		});
		return { el: panel, body, close };
	}

	return { open, escape: esc };
})();
