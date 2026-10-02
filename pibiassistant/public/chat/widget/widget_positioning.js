// pibiAssistant - AIDA
// Drag (pointer events), viewport clamping and position persistence for the AIDA launcher

const PAO_POS_KEY = "pao_toggle_pos";
const PAO_MARGIN = 8;
const PAO_DRAG_THRESHOLD = 6;
const PAO_NUDGE = 10;
const PAO_SIZE_KEY = "pao_chat_size";
const PAO_WINDOW_POS_KEY = "pao_chat_pos";
const PAO_MIN_W = 320;
const PAO_MIN_H = 420;
const PAO_EDGE = 10;
const PAO_RESIZE_STEP = 24;

window.PAOWidgetPositioning = {
	/**
	 * Size of the launcher, remembered because the button is display:none while the chat is open
	 */
	_size(widget) {
		const btn = widget.$widget.find(".pao-toggle-btn")[0];
		if (btn && btn.offsetWidth > 0) {
			widget._btnSize = { w: btn.offsetWidth, h: btn.offsetHeight };
			const r = btn.getBoundingClientRect();
			widget.$widget._btn = { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
		}
		return widget._btnSize || { w: 70, h: 70 };
	},

	_clamp(widget, left, top) {
		const s = this._size(widget);
		const maxL = Math.max(PAO_MARGIN, window.innerWidth - s.w - PAO_MARGIN);
		const maxT = Math.max(PAO_MARGIN, window.innerHeight - s.h - PAO_MARGIN);
		return {
			left: Math.min(Math.max(left, PAO_MARGIN), maxL),
			top: Math.min(Math.max(top, PAO_MARGIN), maxT),
		};
	},

	_place(widget, left, top) {
		const p = this._clamp(widget, left, top);
		widget.$widget.css({
			position: "fixed",
			left: p.left + "px",
			top: p.top + "px",
			right: "auto",
			bottom: "auto",
		});
		return p;
	},

	/**
	 * Set up pointer drag + keyboard nudge on the toggle button
	 * @param {Object} widget - Widget instance
	 */
	setup_drag_handlers(widget) {
		const btn = widget.$widget.find(".pao-toggle-btn")[0];
		if (!btn) return;
		let pid = null;
		let startX = 0;
		let startY = 0;
		let startLeft = 0;
		let startTop = 0;
		let moved = false;
		let resetTimer = null;

		widget._hasDragged = false;
		this._size(widget);

		btn.addEventListener("pointerdown", (e) => {
			if (e.pointerType === "mouse" && e.button !== 0) return;
			if (pid !== null) return;
			pid = e.pointerId;
			moved = false;
			const rect = widget.$widget[0].getBoundingClientRect();
			startX = e.clientX;
			startY = e.clientY;
			startLeft = rect.left;
			startTop = rect.top;
			try {
				btn.setPointerCapture(pid);
			} catch (err) {
				/* capture is an optimisation */
			}
		});

		btn.addEventListener("pointermove", (e) => {
			if (e.pointerId !== pid) return;
			const dx = e.clientX - startX;
			const dy = e.clientY - startY;
			if (!moved) {
				if (Math.hypot(dx, dy) < PAO_DRAG_THRESHOLD) return;
				moved = true;
				widget._hasDragged = true;
				widget.$widget.addClass("pao-dragging");
				btn.style.cursor = "grabbing";
			}
			this._place(widget, startLeft + dx, startTop + dy);
		});

		const end = (e) => {
			if (e.pointerId !== pid) return;
			try {
				btn.releasePointerCapture(pid);
			} catch (err) {
				/* already released */
			}
			pid = null;
			btn.style.cursor = "";
			widget.$widget.removeClass("pao-dragging");
			if (moved) {
				const rect = widget.$widget[0].getBoundingClientRect();
				this.save_custom_position(widget, rect.left, rect.top);
				this.refresh_anchored(widget);
				// The click that follows a drag is swallowed by widget.js; make sure
				// the flag cannot stay armed if no click is dispatched.
				clearTimeout(resetTimer);
				resetTimer = setTimeout(() => {
					widget._hasDragged = false;
				}, 150);
			}
		};
		btn.addEventListener("pointerup", end);
		btn.addEventListener("pointercancel", end);

		btn.addEventListener("keydown", (e) => {
			if (!e.altKey && !e.shiftKey) return;
			const step = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
			if (e.key === "Home") {
				e.preventDefault();
				this.reset_position(widget);
				return;
			}
			if (!step) return;
			e.preventDefault();
			const rect = widget.$widget[0].getBoundingClientRect();
			const p = this._place(widget, rect.left + step[0] * PAO_NUDGE, rect.top + step[1] * PAO_NUDGE);
			this.save_custom_position(widget, p.left, p.top);
			this.refresh_anchored(widget);
		});
	},

	/**
	 * @returns {{w:number,h:number}|null} Saved chat window size, or null for the default
	 */
	get_chat_size() {
		try {
			const s = JSON.parse(localStorage.getItem(PAO_SIZE_KEY) || "null");
			if (s && isFinite(s.w) && isFinite(s.h)) return { w: +s.w, h: +s.h };
		} catch (error) {
			/* storage blocked or corrupt */
		}
		return null;
	},

	_save_chat_size(size) {
		try {
			if (size) localStorage.setItem(PAO_SIZE_KEY, JSON.stringify(size));
			else localStorage.removeItem(PAO_SIZE_KEY);
		} catch (error) {
			/* storage blocked: the size lasts for this page only */
		}
	},

	/**
	 * @returns {{x:number,y:number}|null} Saved chat window position as fractions of the free range
	 */
	get_window_position() {
		try {
			const p = JSON.parse(localStorage.getItem(PAO_WINDOW_POS_KEY) || "null");
			if (p && isFinite(p.x) && isFinite(p.y)) return { x: +p.x, y: +p.y };
		} catch (error) {
			/* storage blocked or corrupt */
		}
		return null;
	},

	_save_window_position(pos) {
		try {
			if (pos) localStorage.setItem(PAO_WINDOW_POS_KEY, JSON.stringify(pos));
			else localStorage.removeItem(PAO_WINDOW_POS_KEY);
		} catch (error) {
			/* storage blocked: the position lasts for this page only */
		}
	},

	/**
	 * Move the open chat window by its header (desktop widths only); double-click resets it
	 * to the spot anchored beside the launcher.
	 */
	setup_window_drag(widget) {
		const header = widget.$widget.find(".pao-header")[0];
		const win = widget.$widget.find(".pao-chat-window")[0];
		if (!header || !win) return;
		header.setAttribute("title", __("Drag to move the chat (double-click resets)"));
		let pid = null;
		let offX = 0;
		let offY = 0;
		let moved = false;

		header.addEventListener("pointerdown", (e) => {
			if (pid !== null || window.innerWidth < 1024 || e.target.closest("button")) return;
			if (e.pointerType === "mouse" && e.button !== 0) return;
			const r = win.getBoundingClientRect();
			pid = e.pointerId;
			offX = e.clientX - r.left;
			offY = e.clientY - r.top;
			moved = false;
			header.setPointerCapture(pid);
		});
		header.addEventListener("pointermove", (e) => {
			if (e.pointerId !== pid) return;
			const r = win.getBoundingClientRect();
			const left = Math.min(Math.max(e.clientX - offX, PAO_EDGE), Math.max(PAO_EDGE, window.innerWidth - r.width - PAO_EDGE));
			const top = Math.min(Math.max(e.clientY - offY, PAO_EDGE), Math.max(PAO_EDGE, window.innerHeight - r.height - PAO_EDGE));
			if (!moved && Math.hypot(left - r.left, top - r.top) < PAO_DRAG_THRESHOLD) return;
			moved = true;
			widget.$widget.addClass("pao-moving");
			win.style.left = left + "px";
			win.style.top = top + "px";
		});
		const end = (e) => {
			if (e.pointerId !== pid) return;
			header.releasePointerCapture(pid);
			pid = null;
			widget.$widget.removeClass("pao-moving");
			if (!moved) return;
			const r = win.getBoundingClientRect();
			const rangeX = Math.max(1, window.innerWidth - r.width - 2 * PAO_EDGE);
			const rangeY = Math.max(1, window.innerHeight - r.height - 2 * PAO_EDGE);
			this._save_window_position({
				x: Math.min(1, Math.max(0, (r.left - PAO_EDGE) / rangeX)),
				y: Math.min(1, Math.max(0, (r.top - PAO_EDGE) / rangeY)),
			});
		};
		header.addEventListener("pointerup", end);
		header.addEventListener("pointercancel", end);
		header.addEventListener("dblclick", (e) => {
			if (e.target.closest("button")) return;
			this._save_window_position(null);
			this.refresh_anchored(widget);
		});
	},

	_apply_chat_size(widget, w, h) {
		const maxW = window.innerWidth - 2 * PAO_EDGE;
		const maxH = window.innerHeight - 2 * PAO_EDGE;
		const size = {
			w: Math.round(Math.min(Math.max(w, PAO_MIN_W), Math.max(PAO_MIN_W, maxW))),
			h: Math.round(Math.min(Math.max(h, PAO_MIN_H), Math.max(PAO_MIN_H, maxH))),
		};
		this._save_chat_size(size);
		this.refresh_anchored(widget);
		return size;
	},

	/**
	 * Resize grip in the top-left corner of the chat window (desktop widths only):
	 * drag, or Alt+arrows when focused; double-click or Alt+Home restores the default size.
	 */
	setup_resize_grip(widget) {
		const grip = widget.$widget.find(".pao-resize-grip")[0];
		const win = widget.$widget.find(".pao-chat-window")[0];
		if (!grip || !win) return;
		let pid = null;
		let right = 0;
		let bottom = 0;

		grip.addEventListener("pointerdown", (e) => {
			if (pid !== null || (e.pointerType === "mouse" && e.button !== 0)) return;
			const r = win.getBoundingClientRect();
			pid = e.pointerId;
			right = r.right;
			bottom = r.bottom;
			grip.setPointerCapture(pid);
			widget.$widget.addClass("pao-resizing");
			e.preventDefault();
		});
		grip.addEventListener("pointermove", (e) => {
			if (e.pointerId !== pid) return;
			const w = Math.min(Math.max(right - e.clientX, PAO_MIN_W), window.innerWidth - 2 * PAO_EDGE);
			const h = Math.min(Math.max(bottom - e.clientY, PAO_MIN_H), window.innerHeight - 2 * PAO_EDGE);
			const left = Math.max(PAO_EDGE, right - w);
			const top = Math.max(PAO_EDGE, bottom - h);
			win.style.cssText += `;left:${left}px;top:${top}px;width:${w}px;height:${h}px;max-height:${h}px`;
		});
		const end = (e) => {
			if (e.pointerId !== pid) return;
			const r = win.getBoundingClientRect();
			grip.releasePointerCapture(pid);
			pid = null;
			widget.$widget.removeClass("pao-resizing");
			this._apply_chat_size(widget, r.width, r.height);
		};
		grip.addEventListener("pointerup", end);
		grip.addEventListener("pointercancel", end);

		grip.addEventListener("dblclick", () => {
			this._save_chat_size(null);
			this.refresh_anchored(widget);
		});
		grip.addEventListener("keydown", (e) => {
			if (!e.altKey) return;
			if (e.key === "Home") {
				e.preventDefault();
				this._save_chat_size(null);
				this.refresh_anchored(widget);
				return;
			}
			const grow = { ArrowLeft: [1, 0], ArrowRight: [-1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[e.key];
			if (!grow) return;
			e.preventDefault();
			const r = win.getBoundingClientRect();
			this._apply_chat_size(widget, r.width + grow[0] * PAO_RESIZE_STEP, r.height + grow[1] * PAO_RESIZE_STEP);
		});
	},

	refresh_anchored(widget) {
		const $btn = widget.$widget.find(".pao-toggle-btn");
		if (widget.is_open) {
			PAOWidgetUI.position_chat_window(widget.$widget, $btn, widget.$widget.find(".pao-chat-window"));
		} else if (window.PAOWidgetTooltips && widget.$widget.find(".pao-tooltip").hasClass("pao-show")) {
			PAOWidgetTooltips.position_tooltip(widget.$widget.find(".pao-tooltip"), $btn);
		}
	},

	reset_position(widget) {
		widget.custom_position = null;
		try {
			localStorage.removeItem(PAO_POS_KEY);
		} catch (e) {
			/* storage blocked */
		}
		widget.$widget.css({ left: "", top: "", right: "", bottom: "" });
		this.refresh_anchored(widget);
	},

	/**
	 * @returns {{x:number,y:number}|null} Saved position as viewport fractions
	 */
	load_custom_position() {
		try {
			const p = JSON.parse(localStorage.getItem(PAO_POS_KEY) || "null");
			if (p && isFinite(p.x) && isFinite(p.y)) return { x: +p.x, y: +p.y };
		} catch (error) {
			/* storage blocked or corrupt */
		}
		return null;
	},

	/**
	 * Persist the launcher position as fractions of the free viewport range
	 */
	save_custom_position(widget, left, top) {
		const s = this._size(widget);
		const rangeX = Math.max(1, window.innerWidth - s.w);
		const rangeY = Math.max(1, window.innerHeight - s.h);
		const position = {
			x: Math.min(1, Math.max(0, left / rangeX)),
			y: Math.min(1, Math.max(0, top / rangeY)),
		};
		widget.custom_position = position;
		try {
			localStorage.setItem(PAO_POS_KEY, JSON.stringify(position));
		} catch (error) {
			/* storage blocked: position lasts for this page only */
		}
	},

	/**
	 * Apply a saved {x,y} fraction position, clamped to the current viewport
	 */
	apply_custom_position(widget, position) {
		if (!position || !isFinite(position.x) || !isFinite(position.y)) return;
		const s = this._size(widget);
		this._place(
			widget,
			position.x * Math.max(1, window.innerWidth - s.w),
			position.y * Math.max(1, window.innerHeight - s.h)
		);
	},

	setup_resize_handler(widget) {
		let timer;
		const run = () => {
			clearTimeout(timer);
			timer = setTimeout(() => this.reposition_on_resize(widget), 100);
		};
		$(window).on("resize", run);
		window.addEventListener("orientationchange", run);
		(widget._cleanups = widget._cleanups || []).push(() => {
			clearTimeout(timer);
			$(window).off("resize", run);
			window.removeEventListener("orientationchange", run);
		});
	},

	reposition_on_resize(widget) {
		if (widget.custom_position) {
			this.apply_custom_position(widget, widget.custom_position);
		}
		this.refresh_anchored(widget);
	},
};
