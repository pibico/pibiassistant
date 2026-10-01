// pibiAssistant - AIDA
// Drag (pointer events), viewport clamping and position persistence for the AIDA launcher

const PAO_POS_KEY = "pao_toggle_pos";
const PAO_MARGIN = 8;
const PAO_DRAG_THRESHOLD = 6;
const PAO_NUDGE = 10;

window.PAOWidgetPositioning = {
	/**
	 * Size of the launcher, remembered because the button is display:none while the chat is open
	 */
	_size(widget) {
		const btn = widget.$widget.find(".pao-toggle-btn")[0];
		if (btn && btn.offsetWidth > 0) {
			widget._btnSize = { w: btn.offsetWidth, h: btn.offsetHeight };
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
		btn.setAttribute("aria-label", __("Move AIDA (Alt+arrows)"));

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
	},

	reposition_on_resize(widget) {
		if (widget.custom_position) {
			this.apply_custom_position(widget, widget.custom_position);
		}
		this.refresh_anchored(widget);
	},
};
