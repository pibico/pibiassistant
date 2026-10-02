// pibiAssistant - AIDA
// Handles HTML rendering and DOM building for the AIDA widget

/**
 * Widget UI Module
 * Responsible for building and managing the widget's DOM structure
 */
window.PAOWidgetUI = {
	/**
	 * Build the complete widget HTML structure
	 * @param {Object} options - Widget options
	 * NOTE: Theme is automatically inherited from Frappe's html[data-theme] attribute
	 * @param {Object} options.preferences - User preferences
	 * @returns {string} HTML string for the widget
	 */
	build_widget_html(options) {
		const { preferences } = options;

		return `
			<div class="pao-widget">
				<!-- Tooltip -->
				<div class="pao-tooltip">
					<span class="pao-tooltip-icon"></span>
					<span class="pao-tooltip-text"></span>
				</div>

				<!-- Toggle Button -->
				<button class="pao-toggle-btn">
					${this.get_robot_html()}
				</button>

				<!-- Chat Window -->
				<div class="pao-chat-window" style="display: none;">
					${this.get_header_html()}
					${this.get_messages_container_html(preferences)}
					${this.get_input_area_html(preferences)}
				</div>
			</div>
		`;
	},

	/**
	 * Get AIDA avatar HTML
	 * @param {string} size - Size variant (default, header, welcome, message)
	 * @returns {string} Avatar HTML
	 */
	get_robot_html(size = "default") {
		const sizes = { default: 64, header: 32, welcome: 88, message: 44 };
		const px = sizes[size] || sizes.default;
		return `<img class="aida-avatar aida-avatar-${size}" src="/assets/pibiassistant/chat/widget/aida-icon.svg" alt="AIDA" width="${px}" height="${px}" style="border-radius:50%;">`;
	},

	/**
	 * Get header HTML
	 * @returns {string} Header HTML
	 */
	get_header_html() {
		return `
			<div class="pao-header">
				<div class="pao-header-brand">
					${this.get_robot_html("header")}
					<span class="pao-brand-text">AIDA</span>
				</div>
				<div class="pao-header-actions">
					<button class="pao-hide-btn" title="${__('Hide assistant (you can re-enable in My Preferences)')}">
						<i class="ph ph-eye-slash" aria-hidden="true"></i>
					</button>
					<button class="pao-expand-btn pao-expand-prominent" title="${__('Open full assistant')}">
						<i class="ph ph-arrow-square-out" aria-hidden="true"></i>
						<span>${__('Expand')}</span>
					</button>
					<button class="pao-close-btn" title="${__('Close')}">
						<i class="ph ph-x" aria-hidden="true"></i>
					</button>
				</div>
			</div>
		`;
	},

	/**
	 * Get messages container HTML with welcome message
	 * @param {Object} preferences - User preferences
	 * @returns {string} Messages container HTML
	 */
	get_messages_container_html(preferences) {
		return `
			<div class="pao-messages">
				${this.get_welcome_message_html()}
			</div>
		`;
	},

	/**
	 * Get welcome message HTML
	 * @returns {string} Welcome message HTML
	 */
	get_welcome_message_html() {
		return `
			<div class="pao-welcome">
				<div class="pao-avatar">
					${this.get_robot_html("welcome")}
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
	 * Get input area HTML
	 * @param {Object} preferences - User preferences
	 * @returns {string} Input area HTML
	 */
	get_input_area_html(preferences) {
		return `
			<!-- Input Area -->
			<div class="pao-input-area">
				<!-- File Preview Area -->
				<div class="pao-file-preview" style="display: none;"></div>

				<!-- Input Row -->
				<div class="pao-input-row">
					<button class="pao-file-upload-btn" title="${__('Attach file')}">
						<i class="ph ph-paperclip" aria-hidden="true"></i>
					</button>
					<input type="file" class="pao-file-input" style="display: none;" accept=".pdf,.png,.jpg,.jpeg,.gif,.csv,.xlsx,.xls,.docx,.doc,.txt,.json,.xml">
					<textarea class="pao-input" placeholder="${__('Ask me anything you need...')}" rows="1"></textarea>
					<button class="pao-send-btn" disabled title="${__('Send message')}">
						<i class="ph ph-paper-plane-tilt" aria-hidden="true"></i>
					</button>
				</div>

			</div>
		`;
	},

	/**
	 * Create a message bubble element
	 * @param {Object} options - Message options
	 * @returns {jQuery} Message element
	 */
	create_message_element(options) {
		const { role, content, isError, attachedFiles, formatMessage } = options;

		let attachmentsHtml = "";
		if (attachedFiles && attachedFiles.length > 0) {
			attachmentsHtml = '<div class="pao-message-attachments">';
			attachedFiles.forEach((file) => {
				const isImage = /\.(png|jpg|jpeg|gif|webp)$/i.test(file.file_url);
				if (isImage) {
					attachmentsHtml += `
						<div class="pao-attachment pao-attachment-image">
							<img src="${file.file_url}" alt="${file.file_name}" />
						</div>
					`;
				} else {
					attachmentsHtml += `
						<div class="pao-attachment pao-attachment-file">
							<i class="ph ph-file" aria-hidden="true"></i>
							<span>${file.file_name}</span>
						</div>
					`;
				}
			});
			attachmentsHtml += "</div>";
		}

		const formattedContent = formatMessage ? formatMessage(content, role) : content;
		const avatarHtml =
			role === "user"
				? window.PAOCore.get_user_avatar()
				: window.PAOCore.get_assistant_avatar();

		return $(`
			<div class="pao-message pao-message-${role} ${isError ? "pao-message-error" : ""}">
				<div class="pao-message-avatar">
					${avatarHtml}
				</div>
				<div class="pao-message-content">
					${attachmentsHtml}
					<div class="pao-message-text">${formattedContent}</div>
					<div class="pao-message-time">${window.PAOCore.format_time(new Date())}</div>
				</div>
			</div>
		`);
	},

	/**
	 * Create typing indicator element
	 * @returns {jQuery} Typing indicator element
	 */
	create_typing_indicator() {
		return $(`
			<div class="pao-message pao-message-assistant pao-typing">
				<div class="pao-message-avatar">
					${window.PAOCore.get_assistant_avatar()}
				</div>
				<div class="pao-message-content">
					<div class="pao-typing-indicator">
						<span class="pao-typing-dot"></span>
						<span class="pao-typing-dot"></span>
						<span class="pao-typing-dot"></span>
					</div>
				</div>
			</div>
		`);
	},

	/**
	 * Create file preview element
	 * @param {Object} file - File object with name, url, size
	 * @returns {jQuery} File preview element
	 */
	create_file_preview(file) {
		const isImage = /\.(png|jpg|jpeg|gif|webp)$/i.test(file.file_name);

		if (isImage) {
			return $(`
				<div class="pao-file-preview-item" data-url="${file.file_url}">
					<img src="${file.file_url}" alt="${file.file_name}">
					<button class="pao-file-remove" title="${__('Remove')}"><i class="ph ph-x" aria-hidden="true"></i></button>
				</div>
			`);
		}

		return $(`
			<div class="pao-file-preview-item" data-url="${file.file_url}">
				<div class="pao-file-icon">
					<i class="ph ph-file" aria-hidden="true"></i>
				</div>
				<span class="pao-file-name">${file.file_name}</span>
				<button class="pao-file-remove" title="${__('Remove')}"><i class="ph ph-x" aria-hidden="true"></i></button>
			</div>
		`);
	},

	/**
	 * Create tool indicator element
	 * @param {string} toolName - Name of the tool being used
	 * @returns {jQuery} Tool indicator element
	 */
	create_tool_indicator(toolName) {
		return $(`
			<div class="pao-tool-indicator">
				<div class="pao-tool-spinner"></div>
				<span>${frappe.utils.escape_html(__("Using {0}...", [toolName]))}</span>
			</div>
		`);
	},

	/**
	 * Create context indicator element
	 * @param {Object} context - Context object
	 * @returns {jQuery} Context indicator element
	 */
	create_context_indicator(context) {
		let iconSvg = "";
		let contextText = "";

		switch (context.type) {
			case "Form":
				iconSvg =
					'<i class="ph ph-file" aria-hidden="true"></i>';
				contextText = `${context.doctype}: ${context.name}`;
				break;
			case "List":
				iconSvg =
					'<i class="ph ph-list-bullets" aria-hidden="true"></i>';
				contextText = __("{0} list", [context.doctype]);
				break;
			case "Report":
				iconSvg =
					'<i class="ph ph-chart-bar" aria-hidden="true"></i>';
				contextText = __("Report: {0}", [context.name]);
				break;
			default:
				iconSvg =
					'<i class="ph ph-info" aria-hidden="true"></i>';
				contextText = context.type;
		}

		return $(`
			<div class="pao-context-badge">
				${iconSvg}
				<span>${contextText}</span>
			</div>
		`);
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
