// pibiAssistant - AIDA
// Handles HTML rendering and DOM building for the AIDA widget

/**
 * Widget UI Module
 * Responsible for building and managing the widget's DOM structure
 */
window.PAOWidgetUI = {
	/**
	 * Welcome block shown in an empty conversation (initial build, post-onboarding).
	 * @returns {string} Welcome message HTML
	 */
	get_welcome_message_html() {
		return `
			<div class="pao-welcome">
				<div class="pao-avatar">
					<img class="aida-avatar" src="/assets/pibiassistant/chat/widget/aida-icon.svg" alt="AIDA" width="88" height="88" style="border-radius:50%;">
				</div>
				<h3>${__("Hi! I am AIDA")}</h3>
				<p>${__("Your intelligent assistant from pibiCo. I can help you with:")}</p>
				<ul>
					<li>${__("Understanding forms and data")}</li>
					<li>${__("Creating and managing documents")}</li>
					<li>${__("Answering questions about your ERP")}</li>
					<li>${__("Navigating the system")}</li>
				</ul>
			</div>
		`;
	},

	/**
	 * Position chat window relative to toggle button
	 * @param {jQuery} $widget - Widget element
	 * @param {jQuery} $toggleBtn - Toggle button element
	 * @param {jQuery} $chatWindow - Chat window element
	 */
	/**
	 * Where the launcher is when it has never been measured (page loaded with the chat
	 * already open): the saved drag position, else the default bottom-right corner.
	 */
	_launcher_rect(vw, vh) {
		const size = 72;
		const saved = PAOWidgetPositioning.load_custom_position();
		const left = saved ? saved.x * Math.max(1, vw - size) : vw - size - 35;
		const top = saved ? saved.y * Math.max(1, vh - size) : vh - size - 35;
		return { left, top, right: left + size, bottom: top + size };
	},

	position_chat_window($widget, $toggleBtn, $chatWindow) {
		if (window.innerWidth < 1024) {
			$chatWindow.css({ top: "", left: "", right: "", bottom: "", width: "", height: "" });
			return;
		}
		const vw = window.innerWidth;
		const vh = window.innerHeight;
		const margin = 15;
		const edge = 10;
		const saved = window.PAOWidgetPositioning && PAOWidgetPositioning.get_chat_size();
		const chatWidth = Math.min(saved ? saved.w : 400, vw - 2 * edge);
		const chatHeight = Math.min(saved ? saved.h : 650, vh - 2 * edge);

		const custom = PAOWidgetPositioning.get_window_position();
		if (custom) {
			$chatWindow.css({
				position: "fixed",
				left: edge + custom.x * Math.max(0, vw - chatWidth - 2 * edge) + "px",
				top: edge + custom.y * Math.max(0, vh - chatHeight - 2 * edge) + "px",
				right: "auto",
				bottom: "auto",
				width: chatWidth + "px",
				height: chatHeight + "px",
				"max-height": chatHeight + "px",
			});
			return;
		}

		// The button is display:none while the chat is open, so fall back to
		// the rect remembered by PAOWidgetPositioning.
		let b = $toggleBtn[0].getBoundingClientRect();
		if (!b.width && $widget._btn) b = $widget._btn;
		else if (b.width) $widget._btn = { left: b.left, top: b.top, right: b.right, bottom: b.bottom };
		else b = this._launcher_rect(vw, vh);

		const clampL = (v) => Math.max(edge, Math.min(v, vw - chatWidth - edge));
		const clampT = (v) => Math.max(edge, Math.min(v, vh - chatHeight - edge));
		let left;
		let top;

		if (b.top >= chatHeight + margin + edge) {
			// above the button, aligned to the side with more room
			top = b.top - chatHeight - margin;
			left = clampL(b.left + (b.right - b.left) / 2 > vw / 2 ? b.right - chatWidth : b.left);
		} else if (vh - b.bottom >= chatHeight + margin + edge) {
			top = b.bottom + margin;
			left = clampL(b.left + (b.right - b.left) / 2 > vw / 2 ? b.right - chatWidth : b.left);
		} else if (b.left >= chatWidth + margin + edge) {
			left = b.left - chatWidth - margin;
			top = clampT(b.bottom - chatHeight);
		} else if (vw - b.right >= chatWidth + margin + edge) {
			left = b.right + margin;
			top = clampT(b.bottom - chatHeight);
		} else {
			left = clampL(b.left);
			top = clampT(b.top - chatHeight - margin);
		}

		$chatWindow.css({
			position: "fixed",
			left: left + "px",
			top: clampT(top) + "px",
			right: "auto",
			bottom: "auto",
			width: chatWidth + "px",
			height: chatHeight + "px",
			"max-height": chatHeight + "px",
		});
	},
};
