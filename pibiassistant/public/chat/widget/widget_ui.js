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
		const sizes = { default: 48, header: 24, welcome: 72, message: 24 };
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
						<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
							<line x1="1" y1="1" x2="23" y2="23"></line>
						</svg>
					</button>
					<button class="pao-expand-btn pao-expand-prominent" title="${__('Open full assistant')}">
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
							<polyline points="15 3 21 3 21 9"></polyline>
							<line x1="10" y1="14" x2="21" y2="3"></line>
						</svg>
						<span>${__('Expand')}</span>
					</button>
					<button class="pao-close-btn" title="${__('Close')}">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<line x1="18" y1="6" x2="6" y2="18"></line>
							<line x1="6" y1="6" x2="18" y2="18"></line>
						</svg>
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
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
						</svg>
					</button>
					<input type="file" class="pao-file-input" style="display: none;" accept=".pdf,.png,.jpg,.jpeg,.gif,.csv,.xlsx,.xls,.docx,.doc,.txt,.json,.xml">
					<textarea class="pao-input" placeholder="${__('Ask me anything you need...')}" rows="1"></textarea>
					<button class="pao-send-btn" disabled title="${__('Send message')}">
						<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<line x1="22" y1="2" x2="11" y2="13"></line>
							<polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
						</svg>
					</button>
				</div>

				<!-- Quota Display -->
				<div class="pao-quota-display" style="display: none;">
					<span class="pao-quota-text"></span>
					<div class="pao-quota-bar">
						<div class="pao-quota-fill"></div>
					</div>
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
							<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
								<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
								<polyline points="14 2 14 8 20 8"></polyline>
							</svg>
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
					<button class="pao-file-remove" title="${__('Remove')}">×</button>
				</div>
			`);
		}

		return $(`
			<div class="pao-file-preview-item" data-url="${file.file_url}">
				<div class="pao-file-icon">
					<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
						<polyline points="14 2 14 8 20 8"></polyline>
					</svg>
				</div>
				<span class="pao-file-name">${file.file_name}</span>
				<button class="pao-file-remove" title="${__('Remove')}">×</button>
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
					'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>';
				contextText = `${context.doctype}: ${context.name}`;
				break;
			case "List":
				iconSvg =
					'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>';
				contextText = __("{0} list", [context.doctype]);
				break;
			case "Report":
				iconSvg =
					'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>';
				contextText = __("Report: {0}", [context.name]);
				break;
			default:
				iconSvg =
					'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';
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
	position_chat_window($widget, $toggleBtn, $chatWindow) {
		if (window.innerWidth < 1024) {
			$chatWindow.css({ top: "", left: "", right: "", bottom: "", width: "", height: "" });
			return;
		}
		const vw = window.innerWidth;
		const vh = window.innerHeight;
		const margin = 15;
		const edge = 10;
		const chatWidth = Math.min(400, vw - 2 * edge);
		const chatHeight = Math.min(650, vh - 2 * edge);

		// The button is display:none while the chat is open, so fall back to
		// the rect remembered by PAOWidgetPositioning.
		let b = $toggleBtn[0].getBoundingClientRect();
		if (!b.width && $widget._btn) b = $widget._btn;
		else if (b.width) $widget._btn = { left: b.left, top: b.top, right: b.right, bottom: b.bottom };

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
		});
	},
};
