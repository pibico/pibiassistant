/**
 * PAOPlanStrip — renders an agent task plan as a compact inline strip
 * inside the streaming assistant bubble. Vanilla JS + jQuery, mirrors the
 * thinking/tool indicator idiom in widget_streaming.js.
 *
 * Plan payload (every plan_* event carries the FULL plan — replace wholesale):
 *   { id, status, tasks: [{ id, title, status, note, delegated, parentId }] }
 *   status ∈ pending | running | done | failed | skipped
 */
window.PAOPlanStrip = {
	GLYPHS: {
		pending: '<i class="ph ph-circle" aria-hidden="true"></i>',
		running: '<i class="ph ph-spinner" aria-hidden="true"></i>',
		done: '<i class="ph ph-check-circle" aria-hidden="true"></i>',
		failed: '<i class="ph ph-x-circle" aria-hidden="true"></i>',
		skipped: '<i class="ph ph-prohibit" aria-hidden="true"></i>',
	},

	glyph(status) {
		return this.GLYPHS[status] || this.GLYPHS.pending;
	},

	_escape(s) {
		// Reuse the widget's sanitizer boundary if present; else minimal escape.
		if (window.PAOCore && typeof PAOCore.escape_html === "function") {
			return PAOCore.escape_html(s == null ? "" : String(s));
		}
		return (s == null ? "" : String(s)).replace(/[&<>"]/g, (c) => (
			{ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]
		));
	},

	/** Count of completed (done/skipped) tasks, for the collapsed summary. */
	_doneCount(tasks) {
		return (tasks || []).filter((t) => t.status === "done" || t.status === "skipped").length;
	},

	/** HTML for one task row. running=true also leaves a sub-activity slot. */
	rowHtml(task) {
		const isChild = !!task.parentId;
		const noteHtml = task.note
			? ` <span class="pao-plan-note">· ${this._escape(task.note)}</span>`
			: "";
		const delegatedHtml = task.delegated
			? ` <span class="pao-plan-delegated"><i class="ph ph-arrow-bend-down-right" aria-hidden="true"></i> specialist</span>`
			: "";
		const subSlot = task.status === "running"
			? `<div class="pao-plan-subactivity" data-task-id="${this._escape(task.id)}"></div>`
			: "";
		return (
			`<li class="pao-plan-row pao-plan-${this._escape(task.status)}${isChild ? " pao-plan-child" : ""}"` +
			` data-task-id="${this._escape(task.id)}"` +
			` aria-label="${this._escape(task.title)} — ${this._escape(task.status)}">` +
			`<span class="pao-plan-glyph">${this.glyph(task.status)}</span>` +
			`<span class="pao-plan-title">${this._escape(task.title)}</span>` +
			delegatedHtml + noteHtml + subSlot +
			`</li>`
		);
	},

	/** Full expanded strip HTML for a live/loaded plan. */
	stripHtml(plan) {
		const tasks = (plan && plan.tasks) || [];
		const rows = tasks.map((t) => this.rowHtml(t)).join("");
		const heading = tasks.length === 1 ? __("Working through 1 step…") : __("Working through {0} steps…", [tasks.length]);
		return (
			`<div class="pao-plan-strip" data-plan-id="${this._escape(plan && plan.id)}">` +
			`<div class="pao-plan-heading">${this._escape(heading)}</div>` +
			`<ul class="pao-plan-list">${rows}</ul>` +
			`</div>`
		);
	},

	/** Collapsed one-line summary (post-completion / on reload), expandable. */
	collapsedHtml(plan) {
		const tasks = (plan && plan.tasks) || [];
		const done = this._doneCount(tasks);
		const rows = tasks.map((t) => this.rowHtml(t)).join("");
		const label = tasks.length === 1 ? __("Completed {0} of 1 step", [done]) : __("Completed {0} of {1} steps", [done, tasks.length]);
		return (
			`<div class="pao-plan-strip pao-plan-collapsed" data-plan-id="${this._escape(plan && plan.id)}">` +
			`<button type="button" class="pao-plan-summary"><i class="ph ph-check" aria-hidden="true"></i> ${this._escape(label)} <span class="pao-plan-caret"><i class="ph ph-caret-right" aria-hidden="true"></i></span></button>` +
			`<ul class="pao-plan-list" style="display:none;">${rows}</ul>` +
			`</div>`
		);
	},
};
