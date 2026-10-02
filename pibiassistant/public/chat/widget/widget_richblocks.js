// pibiAssistant - AIDA Widget Rich Blocks
// Renders callout, metric, steps, accordion, tabs, mermaid, and chart
// code fence blocks as styled HTML in the vanilla JS widget.

/**
 * PAOWidgetRichBlocks - Rich block parsing and rendering for the desk widget
 *
 * Ports the Vue SPA's parser.js + registry.js architecture to vanilla JS,
 * outputting HTML strings instead of Vue component instances.
 */
window.PAOWidgetRichBlocks = {
	// --- SVG Icons ---

	_icons: {
		info: '<i class="ph ph-info" aria-hidden="true"></i>',
		warning:
			'<i class="ph ph-warning" aria-hidden="true"></i>',
		tip: '<i class="ph ph-lightbulb" aria-hidden="true"></i>',
		success:
			'<i class="ph ph-check-circle" aria-hidden="true"></i>',
		error: '<i class="ph ph-x-circle" aria-hidden="true"></i>',
		trendUp:
			'<i class="ph ph-arrow-up" aria-hidden="true"></i>',
		trendDown:
			'<i class="ph ph-arrow-down" aria-hidden="true"></i>',
		check: '<i class="ph ph-check" aria-hidden="true"></i>',
		chevron:
			'<i class="ph ph-caret-right" aria-hidden="true"></i>',
		diagram:
			'<i class="ph ph-flow-arrow" aria-hidden="true"></i>',
		chart: '<i class="ph ph-chart-bar" aria-hidden="true"></i>',
	},

	// --- Attribute Parser ---

	/**
	 * Parse key="value" pairs from code fence attribute string.
	 * e.g. 'type="info" title="Note"' → { type: 'info', title: 'Note' }
	 */
	_parseAttrs(attrString) {
		if (!attrString) return {};
		const attrs = {};
		const re = /(\w+)="([^"]*)"/g;
		let m;
		while ((m = re.exec(attrString)) !== null) {
			attrs[m[1]] = m[2];
		}
		return attrs;
	},

	// --- JSON Body Parser ---

	/**
	 * The model reaches for a JSON body on any fence, having generalised from
	 * `chart`/`mermaid` sitting beside them in the same skill doc. Every block
	 * documenting fence-line attributes has to read a JSON body too, or the
	 * payload lands on the user's screen as visible JSON.
	 *
	 * Returns the parsed object/array, or null for a non-JSON body.
	 */
	_parseJsonBody(body) {
		const trimmed = (body || "").trim();
		if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) return null;
		try {
			const parsed = JSON.parse(trimmed);
			return parsed && typeof parsed === "object" ? parsed : null;
		} catch {
			return null;
		}
	},

	/** JSON body as a plain object, or {} for an array / non-JSON body. */
	_jsonObjectBody(body) {
		const parsed = this._parseJsonBody(body);
		return parsed && !Array.isArray(parsed) ? parsed : {};
	},

	/**
	 * First non-empty value for the given keys, attributes before JSON body.
	 * Attributes win because they are the documented dialect — a fence
	 * carrying both is a model hedging, and the explicit form is the intent.
	 */
	_picker(attrs, json) {
		return function () {
			const keys = Array.prototype.slice.call(arguments);
			for (const key of keys) {
				if (attrs[key]) return String(attrs[key]);
			}
			for (const key of keys) {
				const value = json[key];
				if (value !== undefined && value !== null && value !== "") {
					return String(value);
				}
			}
			return "";
		};
	},

	// --- Block Regex (built once) ---

	_blockTypes: ["chart", "mermaid", "callout", "metric", "steps", "accordion", "tabs"],

	_getBlockRegex() {
		if (!this._blockRegex) {
			const types = this._blockTypes.join("|");
			this._blockRegex = new RegExp(
				"```(" + types + ")([ \\t]+[^\\n]*)?\\n([\\s\\S]*?)```",
				"g"
			);
		}
		return this._blockRegex;
	},

	_getTestRegex() {
		if (!this._testRegex) {
			const types = this._blockTypes.join("|");
			this._testRegex = new RegExp("```(?:" + types + ")");
		}
		return this._testRegex;
	},

	// --- HTML Escaping ---

	_escapeHtml(text) {
		return PAOCore.escape_html(text);
	},

	// --- Markdown Helper ---

	_renderMarkdown(text) {
		if (!text || !text.trim()) return "";
		return PAOCore.format_message(text, "assistant");
	},

	/** One metric card, or null when neither a title nor a value is given. */
	_metricCard(attrs, json, self) {
		const pick = self._picker(attrs, json);
		const title = pick("title", "label");
		const value = pick("value");
		const change = pick("change", "delta");
		const trend = pick("trend");
		const description = pick("description", "suffix");

		if (!title && !value) return null;

		let trendClass = "pao-rb-trend-flat";
		let trendIcon = "";
		if (trend === "up") {
			trendClass = "pao-rb-trend-up";
			trendIcon = self._icons.trendUp;
		} else if (trend === "down") {
			trendClass = "pao-rb-trend-down";
			trendIcon = self._icons.trendDown;
		}

		let changeHtml = "";
		if (change) {
			changeHtml =
				'<span class="pao-rb-metric-change ' +
				trendClass +
				'">' +
				(trendIcon
					? '<span class="pao-rb-trend-icon">' + trendIcon + "</span>"
					: "") +
				self._escapeHtml(change) +
				"</span>";
		}

		return (
			'<div class="pao-rb-metric">' +
			(title
				? '<div class="pao-rb-metric-title">' + self._escapeHtml(title) + "</div>"
				: "") +
			'<div class="pao-rb-metric-row">' +
			'<span class="pao-rb-metric-value">' +
			self._escapeHtml(value) +
			"</span>" +
			changeHtml +
			"</div>" +
			(description
				? '<div class="pao-rb-metric-desc">' +
				  self._escapeHtml(description) +
				  "</div>"
				: "") +
			"</div>"
		);
	},

	// --- Section Splitter (used by accordion and tabs) ---

	_splitSections(body) {
		if (!body) return [];
		const parts = body.split(/^## /m).filter(Boolean);
		return parts.map((part) => {
			const newlineIdx = part.indexOf("\n");
			if (newlineIdx === -1) {
				return { title: part.trim(), html: "" };
			}
			const title = part.slice(0, newlineIdx).trim();
			const content = part.slice(newlineIdx + 1).trim();
			return {
				title,
				html: content ? this._renderMarkdown(content) : "",
			};
		});
	},

	// --- Block Renderers ---

	_blocks: {
		// Reads a JSON body the same way `metric` does. Without it a
		// `{"type":"warning","title":…,"content":…}` fence rendered an *info*
		// box with no title and the raw JSON as its text. An unrecognised
		// JSON shape keeps its body visible: better the reader sees the raw
		// object than an empty box that looks like a UI fault.
		callout(body, attrs, self) {
			const validTypes = ["info", "warning", "tip", "success", "error"];
			const json = self._jsonObjectBody(body);
			const pick = self._picker(attrs, json);
			const requestedType = pick("type");
			const type = validTypes.includes(requestedType) ? requestedType : "info";
			const title = pick("title", "heading");
			const icon = self._icons[type] || self._icons.info;
			const text = pick("content", "body", "text", "message") || body;
			const renderedBody = text ? self._renderMarkdown(text) : "";

			return (
				'<div class="pao-rb-callout pao-rb-callout-' +
				type +
				'">' +
				'<div class="pao-rb-callout-icon">' +
				icon +
				"</div>" +
				'<div class="pao-rb-callout-content">' +
				(title
					? '<div class="pao-rb-callout-title">' + self._escapeHtml(title) + "</div>"
					: "") +
				(renderedBody
					? '<div class="pao-rb-callout-body">' + renderedBody + "</div>"
					: "") +
				"</div>" +
				"</div>"
			);
		},

		// Data arrives three ways: fence-line attributes (documented), a JSON
		// object keyed on label/value (what the model usually writes, having
		// generalised from `chart`), or a JSON *array* — a whole KPI row in
		// one fence, rendered as one card per entry. The body used to be
		// ignored outright, so both JSON shapes produced an empty card; now
		// an unusable fence returns null and the caller shows a code block.
		metric(body, attrs, self) {
			const parsed = self._parseJsonBody(body);

			if (Array.isArray(parsed)) {
				const cards = parsed
					.map((entry) =>
						self._metricCard(
							attrs,
							entry && typeof entry === "object" ? entry : {},
							self
						)
					)
					.filter(Boolean);
				return cards.length ? cards.join("") : null;
			}

			return self._metricCard(attrs, parsed || {}, self);
		},

		steps(body, attrs, self) {
			const title = attrs.title || "";
			const current = attrs.current ? parseInt(attrs.current, 10) : 0;

			if (!body) return null;

			const stepTexts = body
				.split("\n")
				.map((line) => line.replace(/^\d+\.\s*/, "").trim())
				.filter(Boolean);

			if (stepTexts.length === 0) return null;

			let stepsHtml = "";
			stepTexts.forEach((text, idx) => {
				const num = idx + 1;
				let stepClass = "pao-rb-step";
				let markerContent;

				if (current > 0 && num < current) {
					stepClass += " pao-rb-step-done";
					markerContent =
						'<span class="pao-rb-step-check">' + self._icons.check + "</span>";
				} else if (current > 0 && num === current) {
					stepClass += " pao-rb-step-active";
					markerContent = '<span class="pao-rb-step-number">' + num + "</span>";
				} else {
					markerContent = '<span class="pao-rb-step-number">' + num + "</span>";
				}

				// Render inline markdown for step text
				const rendered = self._renderMarkdown(text);

				stepsHtml +=
					'<li class="' +
					stepClass +
					'">' +
					'<div class="pao-rb-step-marker">' +
					markerContent +
					"</div>" +
					'<div class="pao-rb-step-content">' +
					rendered +
					"</div>" +
					"</li>";
			});

			return (
				'<div class="pao-rb-steps">' +
				(title
					? '<div class="pao-rb-steps-title">' + self._escapeHtml(title) + "</div>"
					: "") +
				'<ol class="pao-rb-steps-list">' +
				stepsHtml +
				"</ol>" +
				"</div>"
			);
		},

		accordion(body, _attrs, self) {
			const sections = self._splitSections(body);
			if (sections.length === 0) return null;

			let html = '<div class="pao-rb-accordion">';
			sections.forEach((section, idx) => {
				const isOpen = idx === 0;
				html +=
					'<div class="pao-rb-accordion-section' +
					(isOpen ? " pao-rb-open" : "") +
					'">' +
					'<button class="pao-rb-accordion-header" type="button">' +
					'<span class="pao-rb-accordion-chevron">' +
					self._icons.chevron +
					"</span>" +
					'<span class="pao-rb-accordion-title">' +
					self._escapeHtml(section.title) +
					"</span>" +
					"</button>" +
					'<div class="pao-rb-accordion-body">' +
					section.html +
					"</div>" +
					"</div>";
			});
			html += "</div>";
			return html;
		},

		tabs(body, attrs, self) {
			const sections = self._splitSections(body);
			if (sections.length === 0) return null;

			// Find default tab by title match
			let activeIdx = 0;
			if (attrs.default) {
				const defaultLower = attrs.default.toLowerCase();
				const matchIdx = sections.findIndex((s) => s.title.toLowerCase() === defaultLower);
				if (matchIdx >= 0) activeIdx = matchIdx;
			}

			let buttonsHtml = "";
			let panelsHtml = "";

			sections.forEach((section, idx) => {
				const isActive = idx === activeIdx;
				buttonsHtml +=
					'<button class="pao-rb-tab-btn' +
					(isActive ? " pao-rb-active" : "") +
					'"' +
					' data-tab-index="' +
					idx +
					'"' +
					' role="tab" aria-selected="' +
					isActive +
					'"' +
					' type="button">' +
					self._escapeHtml(section.title) +
					"</button>";

				panelsHtml +=
					'<div class="pao-rb-tab-panel' +
					(isActive ? " pao-rb-active" : "") +
					'"' +
					' data-tab-index="' +
					idx +
					'"' +
					' role="tabpanel">' +
					section.html +
					"</div>";
			});

			return (
				'<div class="pao-rb-tabs">' +
				'<div class="pao-rb-tabs-bar" role="tablist">' +
				buttonsHtml +
				"</div>" +
				panelsHtml +
				"</div>"
			);
		},

		mermaid(body, _attrs, self) {
			if (!body) return null;
			// Diagram type is the first token of the source
			const firstWord = body.trim().split(/[\s\n{]/)[0] || "diagram";
			return self._placeholderCard("mermaid", self._icons.diagram, __("Mermaid Diagram"), self._escapeHtml(firstWord), body);
		},

		chart(body, _attrs, self) {
			if (!body) return null;

			let chartType = "chart";
			let chartTitle = "";

			try {
				const config = JSON.parse(body);
				chartType = config.type || "chart";
				chartTitle = config.title || "";
			} catch {
				// Invalid JSON — show as raw code
			}

			const typeLabel = chartTitle
				? self._escapeHtml(chartType) + " — " + self._escapeHtml(chartTitle)
				: self._escapeHtml(chartType);

			return self._placeholderCard("chart", self._icons.chart, __("Chart"), typeLabel, body);
		},
	},

	_placeholderCard(kind, icon, label, typeHtml, body) {
		return (
			'<div class="pao-rb-placeholder pao-rb-placeholder-' + kind + '">' +
			'<div class="pao-rb-placeholder-header">' +
			'<span class="pao-rb-placeholder-icon">' +
			icon +
			"</span>" +
			'<div class="pao-rb-placeholder-info">' +
			'<div class="pao-rb-placeholder-label">' + this._escapeHtml(label) + "</div>" +
			'<div class="pao-rb-placeholder-type">' +
			typeHtml +
			"</div>" +
			"</div>" +
			'<button class="pao-rb-view-full" type="button">' + this._escapeHtml(__("View in full assistant")) + "</button>" +
			"</div>" +
			'<details class="pao-rb-placeholder-code">' +
			"<summary>" + this._escapeHtml(__("Show source")) + "</summary>" +
			"<pre><code>" +
			this._escapeHtml(body) +
			"</code></pre>" +
			"</details>" +
			"</div>"
		);
	},

	// --- Public API ---

	/**
	 * Lightweight pre-check: does content contain any rich block code fences?
	 * Avoids running the full parser on every streaming chunk.
	 */
	hasBlocks(content) {
		return this._getTestRegex().test(content);
	},

	/**
	 * Parse content for rich blocks and render to HTML.
	 * Returns a complete HTML string with rich blocks + markdown segments.
	 */
	process(content) {
		if (!content) return "";

		const regex = this._getBlockRegex();
		const parts = [];
		let lastIndex = 0;

		// Reset regex state (global regexes are stateful)
		regex.lastIndex = 0;
		let match;

		while ((match = regex.exec(content)) !== null) {
			// Render text before this block as markdown
			if (match.index > lastIndex) {
				const textBefore = content.slice(lastIndex, match.index);
				if (textBefore.trim()) {
					parts.push(this._renderMarkdown(textBefore));
				}
			}

			const blockType = match[1];
			const attrString = match[2] ? match[2].trim() : "";
			const blockBody = match[3].trim();
			const renderer = this._blocks[blockType];

			if (renderer) {
				const attrs = this._parseAttrs(attrString);
				const blockHtml = renderer(blockBody, attrs, this);

				if (blockHtml) {
					parts.push(blockHtml);
				} else {
					// Renderer returned null — render as plain code block
					parts.push(this._renderMarkdown("```\n" + blockBody + "\n```"));
				}
			}

			lastIndex = match.index + match[0].length;
		}

		// Remaining text after last block
		if (lastIndex < content.length) {
			const textAfter = content.slice(lastIndex);
			if (textAfter.trim()) {
				parts.push(this._renderMarkdown(textAfter));
			}
		}

		// No blocks found — render entire content as markdown
		if (parts.length === 0 && content.trim()) {
			return this._renderMarkdown(content);
		}

		return parts.join("");
	},

	/**
	 * Set up jQuery event delegation for interactive blocks.
	 * Called once during widget initialization.
	 */
	initEventDelegation(widget) {
		const $messages = widget.$widget.find(".pao-messages");

		// Accordion toggle
		$messages.on("click", ".pao-rb-accordion-header", function (e) {
			e.preventDefault();
			$(this).closest(".pao-rb-accordion-section").toggleClass("pao-rb-open");
		});

		// Tab switching
		$messages.on("click", ".pao-rb-tab-btn", function (e) {
			e.preventDefault();
			const $btn = $(this);
			const $tabs = $btn.closest(".pao-rb-tabs");
			const idx = $btn.data("tab-index");

			// Deactivate all
			$tabs
				.find(".pao-rb-tab-btn")
				.removeClass("pao-rb-active")
				.attr("aria-selected", "false");
			$tabs.find(".pao-rb-tab-panel").removeClass("pao-rb-active");

			// Activate clicked
			$btn.addClass("pao-rb-active").attr("aria-selected", "true");
			$tabs
				.find('.pao-rb-tab-panel[data-tab-index="' + idx + '"]')
				.addClass("pao-rb-active");
		});

		// "View in full assistant" button for mermaid/chart placeholders
		$messages.on("click", ".pao-rb-view-full", function (e) {
			e.preventDefault();
			if (widget.expand_to_full_page) {
				widget.expand_to_full_page();
			}
		});
	},
};
