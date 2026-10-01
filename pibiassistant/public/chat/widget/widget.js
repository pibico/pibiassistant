// pibiAssistant - AIDA
// Copyright (C) 2025 Paul Clinton
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

/**
 * AIDA Widget - Main chat widget for pibiAssistant
 */
class PAOWidget {
	constructor() {
		// Resolved asynchronously in init() via resolve_session() — a stored id
		// may belong to another live tab, which only that tab can answer.
		this.session_id = null;
		this.session_restored = false;

		this.messages = [];
		// Turn-in-flight state, read by the reconnect recovery in
		// widget_streaming.js to tell a lost answer from a finished one.
		this._isStreaming = false;
		this.current_message_id = null;
		this._seenMessageIds = new Set();
		this.is_open = false;
		this.is_minimized = false;
		this.preferences = null;
		this.context = null;
		this.attached_files = []; // Store uploaded files
		this.user_setup_complete = false; // Per-user AR registration status
		this.privacy_consent_complete = false; // Privacy consent done in SPA
		this.default_tooltip_messages = [
			{ icon: "👋", text: "Hey! Need help with anything?" },
			{ icon: "💬", text: "Click me to start chatting!" },
			{ icon: "🔍", text: "Looking for something specific?" },
		];
		this.tooltip_messages = [...this.default_tooltip_messages];
		this.current_tooltip_index = 0;
		this.tooltip_interval = null;

		this.init();
	}

	async init() {
		// Check access: show_widget gates whether the launcher renders at all
		// (hidden for non-members who aren't admins); can_use gates chat vs.
		// the onboarding screen for those who do see it.
		const [access] = await Promise.all([this.check_access(), this.resolve_session()]);

		// Diagnostics kill switch resolves here — ahead of the early returns
		// below — so a non-member, an admin-disabled user, or a site with chat
		// off still gets the operator's actual decision, not just whatever this
		// browser last happened to persist. check_access() is not a new RPC:
		// every Desk page load already makes it, on every one of these paths.
		//
		// Persist only when the field actually came back: check_access()'s own
		// catch block (a transient RPC failure) omits it, and the resulting
		// fail-open "enabled" must not overwrite a real persisted "off" — that
		// persisted value exists specifically to cover the window before this
		// call resolves on the NEXT load, and a write here would erase it.
		if (window.PAODiagnostics) {
			const diagnosticsFieldPresent = access.enable_browser_diagnostics !== undefined;
			window.PAODiagnostics.setEnabled(
				access.enable_browser_diagnostics !== false,
				diagnosticsFieldPresent
			);
		}

		// Store access info for onboarding
		this.can_use = access.can_use;
		this.registration_status = access.status;
		this.is_admin = access.is_admin;
		this.pa_cloud_url = access.pa_cloud_url;
		this.preferences = access.preferences || {};

		// Not a member and not an admin -> server returns show_widget:false ->
		// the launcher never mounts (no trace on the page).
		if (!access.show_widget) {
			return;
		}

		// Per-user opt-out: user disabled the launcher in their preferences.
		// They can re-enable from /app/pa-chat-user-preferences/<their-email>.
		if (this.preferences && this.preferences.hide_widget) {
			return;
		}

		// Load widget customization settings
		await this.load_widget_settings();

		// Build widget UI
		this.build_widget();

		// Setup Socket.IO listeners for streaming
		this.setup_socket_listeners();

		// Restore any pending HITL pause that survived a disconnect or
		// worker restart so the user can finish where they left off.
		if (window.PAOWidgetStreaming && window.PAOWidgetStreaming.hydrate_pending_interrupt) {
			window.PAOWidgetStreaming.hydrate_pending_interrupt(this);
		}

		// Auto-fade launcher while user is typing in Frappe inputs or scrolling.
		if (window.PAOWidgetAutofade) {
			window.PAOWidgetAutofade.setup(this);
		}

		// Note: PAOBrowserTools auto-initializes when its script loads
		// (see widget_browser_tools.js) - no need to call initialize() here

		// If site is registered, check per-user auth status
		if (this.can_use) {
			await this.check_user_auth();
		}

		// Check privacy consent from preferences (set during SPA onboarding)
		if (this.can_use && this.user_setup_complete) {
			this.privacy_consent_complete = !!(
				this.preferences && this.preferences.privacy_consent_complete
			);
		}

		// Only load session history if fully set up (including consent)
		if (this.can_use && this.user_setup_complete && this.privacy_consent_complete) {
			await this.load_session_history();
		}

		// Setup keyboard shortcut
		if (this.preferences && this.preferences.keyboard_shortcut) {
			this.setup_keyboard_shortcut(this.preferences.keyboard_shortcut);
		}

		// Stay closed on load. A restored conversation used to pop the panel
		// open on every Desk refresh; it now waits for a launcher click.
		this.start_tooltip_animation();

		// Listen for route changes to update context and visibility
		frappe.router.on("change", () => {
			this.check_and_update_visibility();
			this.update_context();
		});

		// Initial visibility check (hide on pao-assistant page)
		this.check_and_update_visibility();
	}

	async check_access() {
		try {
			const response = await frappe.call({
				method: "pibiassistant.pibiassistant_chat.api.settings.access.can_use_pao",
				type: "GET",
				args: {},
			});
			return response.message;
		} catch (error) {
			return { can_use: false, reason: "Error checking access" };
		}
	}

	async load_widget_settings() {
		/**
		 * Load widget customization settings from server
		 */
		try {
			const response = await frappe.call({
				method: "pibiassistant.pibiassistant_chat.api.settings.widget.get_widget_settings",
				type: "GET",
				args: {},
			});
			this.widget_settings = response.message || this.get_default_settings();
			this.apply_widget_styles();
		} catch (error) {
			PAOLogger.error("Error loading widget settings:", error);
			this.widget_settings = this.get_default_settings();
		}
	}

	get_default_settings() {
		/**
		 * Default widget settings fallback
		 */
		return {
			button: {
				size: 56,
				icon: "aida",
				enable_pulse: true,
				shadow: "0 4px 20px rgba(0,0,0,0.15)",
			},
			window: {
				width: 400,
				height: 650,
				border_radius: 12,
				font_size: "14px",
			},
			messages: {},
			custom_css: "",
		};
	}

	apply_widget_styles() {
		/**
		 * Generate and inject dynamic CSS based on widget settings
		 */
		const settings = this.widget_settings;
		let css = "";

		// Button styles
		if (settings.button) {
			const btn = settings.button;
			css += `
				.pao-toggle-btn {
					width: ${btn.size}px !important;
					height: ${btn.size}px !important;
					${btn.color ? `background: ${btn.color} !important;` : ""}
					${btn.shadow ? `box-shadow: ${btn.shadow} !important;` : ""}
					${!btn.enable_pulse ? "animation: none !important;" : ""}
				}
			`;
		}

		// Window styles
		if (settings.window) {
			const win = settings.window;
			css += `
				.pao-chat-window {
					width: ${win.width}px !important;
					max-height: ${win.height}px !important;
					border-radius: ${win.border_radius}px !important;
				}

				.pao-header {
					${win.header_bg ? `background: ${win.header_bg} !important;` : ""}
				}

				.pao-messages {
					${win.chat_bg ? `background: ${win.chat_bg} !important;` : ""}
					font-size: ${win.font_size} !important;
				}
			`;
		}

		// Message bubble styles
		if (settings.messages) {
			const msg = settings.messages;
			if (msg.user_bg || msg.user_text) {
				css += `
					.pao-message.user .pao-message-content {
						${msg.user_bg ? `background: ${msg.user_bg} !important;` : ""}
						${msg.user_text ? `color: ${msg.user_text} !important;` : ""}
					}
				`;
			}
			if (msg.assistant_bg || msg.assistant_text) {
				css += `
					.pao-message.assistant .pao-message-content {
						${msg.assistant_bg ? `background: ${msg.assistant_bg} !important;` : ""}
						${msg.assistant_text ? `color: ${msg.assistant_text} !important;` : ""}
					}
				`;
			}
		}

		// Custom CSS
		if (settings.custom_css) {
			css += `\n${settings.custom_css}`;
		}

		// Inject or update style tag
		let styleTag = document.getElementById("pao-dynamic-styles");
		if (!styleTag) {
			styleTag = document.createElement("style");
			styleTag.id = "pao-dynamic-styles";
			document.head.appendChild(styleTag);
		}
		styleTag.textContent = css;
	}

	async load_session_history() {
		/**
		 * Load previous messages from this session and restore them to the chat
		 */
		try {
			const response = await frappe.call({
				method: "pibiassistant.pibiassistant_chat.api.chat.sessions.get_session_history",
				type: "GET",
				args: {
					session_id: this.session_id,
				},
			});

			// get_session_history returns { messages: [...], has_more }. Older/edge
			// paths may return a bare array — handle both.
			const payload = response.message;
			const messages = Array.isArray(payload)
				? payload
				: (payload && Array.isArray(payload.messages) ? payload.messages : []);

			// Clear welcome message if there are previous messages
			if (messages.length > 0) {
				this.$widget.find(".pao-welcome").remove();
			}

			// Render each message
			messages.forEach((msg) => {
				this.messages.push(this._toWidgetMessage(msg));

				// Recovery reads compare against what is already on screen.
				if (msg.message_id) {
					this._seenMessageIds.add(msg.message_id);
				}

				// Add message bubble to UI with attachments
				const attachments = msg.attachments || [];
				const $msg = this.add_message_to_ui(msg.role, msg.content, false, attachments);

				// Re-render a persisted task plan as a collapsed, expandable
				// summary above this message's content (matches the SPA).
				this.render_persisted_plan(msg, $msg);
				this.render_routing_chip(msg, $msg);
			});

			// Scroll to bottom after loading history
			this.scroll_to_bottom();

			// If session was restored from SPA and last message is from user,
			// the assistant response may still be streaming/pending - poll for it
			if (this.session_restored && messages.length > 0) {
				const lastMsg = messages[messages.length - 1];
				if (lastMsg.role === "user") {
					this.poll_for_pending_response();
				}
			}
		} catch (error) {
			// Continue with empty history
		}
	}

	/**
	 * Poll for pending assistant response after navigation
	 * Called when session is restored and last message is from user
	 * This handles the case where user navigated away mid-stream
	 */
	async poll_for_pending_response() {
		const maxAttempts = 30; // Poll for up to 30 seconds (MCP tools can take 15s+)
		const pollInterval = 1000; // 1 second between polls

		// Show a "Continuing..." indicator
		const $messages = this.$widget.find(".pao-messages");
		const $waitingIndicator = $(`
			<div class="pao-message pao-message-assistant pao-waiting-response">
				<div class="pao-message-avatar">${this.get_assistant_avatar()}</div>
				<div class="pao-message-content">
					<div class="pao-message-text">
						<span class="pao-waiting-text">${__("Continuing previous response...")}</span>
						<span class="pao-streaming-cursor">▋</span>
					</div>
				</div>
			</div>
		`);
		$messages.append($waitingIndicator);
		this.scroll_to_bottom();

		for (let attempt = 0; attempt < maxAttempts; attempt++) {
			await new Promise((resolve) => setTimeout(resolve, pollInterval));

			try {
				const response = await frappe.call({
					method: "pibiassistant.pibiassistant_chat.api.chat.sessions.get_session_history",
					type: "GET",
					args: { session_id: this.session_id },
				});

				// Same response shape as get_session_history: { messages: [...], has_more }.
				const payload = response.message;
				const messages = Array.isArray(payload)
					? payload
					: (payload && Array.isArray(payload.messages) ? payload.messages : []);

				// Check if we now have an assistant response at the end
				if (messages.length > 0) {
					const lastMsg = messages[messages.length - 1];
					if (lastMsg.role === "assistant") {
						// Found the response! Remove indicator and render
						$waitingIndicator.remove();

						this.messages.push(this._toWidgetMessage(lastMsg));
						const $late = this.add_message_to_ui(lastMsg.role, lastMsg.content);
						// The recovery path after a long tool call — exactly when a
						// user most wants to know which model ran.
						this.render_routing_chip(lastMsg, $late);
						return;
					}
				}
			} catch (error) {
				// Continue polling on error
			}
		}

		// Timeout - remove indicator and show a non-error info message
		// The response may still be processing server-side (e.g. long MCP tool calls)
		$waitingIndicator.remove();
		this.add_message_to_ui(
			"assistant",
			__(
				"The response is taking longer than expected. It may still appear when ready — try sending a new message to check."
			),
			false
		);
	}

	build_widget() {
		// Load custom position from localStorage if available
		this.custom_position = this.load_custom_position();

		// Create widget container (always starts at bottom-left unless custom position exists)
		// Theme is automatically inherited from Frappe's html[data-theme] attribute
		this.$widget = $(`
			<div class="pao-widget">
				<!-- Tooltip -->
				<div class="pao-tooltip">
					<span class="pao-tooltip-icon"></span>
					<span class="pao-tooltip-text"></span>
				</div>

				<!-- Toggle Button -->
				<button class="pao-toggle-btn">
						<img class="aida-avatar" src="/assets/pibiassistant/chat/widget/aida-icon.svg" alt="AIDA" width="48" height="48" style="border-radius:50%;">
					<span class="pao-approval-badge" aria-hidden="true"></span>
				</button>

				<!-- Chat Window -->
				<div class="pao-chat-window" style="display: none;">
					<!-- Header -->
					<div class="pao-header">
						<div class="pao-header-brand">
							<img class="aida-avatar aida-avatar-header" src="/assets/pibiassistant/chat/widget/aida-icon.svg" alt="AIDA" width="24" height="24" style="border-radius:50%;margin-right:6px;vertical-align:middle;">
								<span class="pao-brand-text">AIDA</span>
						</div>
						<div class="pao-header-actions">
							<button class="pao-expand-btn" title="Open Full Page">
								<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<polyline points="15 3 21 3 21 9"></polyline>
									<polyline points="9 21 3 21 3 15"></polyline>
									<line x1="21" y1="3" x2="14" y2="10"></line>
									<line x1="3" y1="21" x2="10" y2="14"></line>
								</svg>
							</button>
							<button class="pao-close-btn" title="Close">
								<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<line x1="18" y1="6" x2="6" y2="18"></line>
									<line x1="6" y1="6" x2="18" y2="18"></line>
								</svg>
							</button>
						</div>
					</div>

					<!-- Messages Container -->
					<div class="pao-messages">
						<div class="pao-welcome">
							<div class="pao-avatar">
								<img src="/assets/pibiassistant/chat/widget/aida-icon.svg" alt="AIDA" style="width:64px;height:64px;border-radius:50%;">
							</div>
							<h3>¡Hola! Soy AIDA</h3>
							<p>Tu asistente inteligente de pibiCo. Puedo ayudarte con:</p>
							<ul>
								<li>Consultar datos y formularios</li>
								<li>Crear y gestionar documentos</li>
								<li>Responder preguntas sobre tu ERP</li>
								<li>Navegar por el sistema</li>
							</ul>
						</div>
					</div>

					<!-- Input Area -->
					<div class="pao-input-area">
						<!-- File Preview List -->
						<div class="pao-file-preview-list" style="display: none;"></div>

						<div class="pao-input-wrapper">
							<button class="pao-file-upload-btn" title="Attach file">
								<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
								</svg>
							</button>
							<input type="file" class="pao-file-input" style="display: none;" accept=".pdf,.png,.jpg,.jpeg,.csv,.xlsx,.xls,.docx,.txt">
							<button class="pao-mic-btn" type="button" title="Voice input (Ctrl+Shift+Space)" aria-label="Voice input (Ctrl+Shift+Space)">
								<svg class="pao-mic-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
									<path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
									<path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
									<line x1="12" y1="19" x2="12" y2="23"></line>
									<line x1="8" y1="23" x2="16" y2="23"></line>
								</svg>
								<span class="pao-mic-elapsed" style="display:none;"></span>
							</button>
							<textarea
								class="pao-input"
								placeholder="Pregúntame lo que necesites..."
								rows="1"
							></textarea>
							<button class="pao-send-btn" title="Send" disabled>
								<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<line x1="22" y1="2" x2="11" y2="13"></line>
									<polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
								</svg>
							</button>
						</div>
						<div class="pao-context-row">
							<div class="pao-context-indicator">
								<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<circle cx="12" cy="12" r="10"></circle>
									<line x1="12" y1="16" x2="12" y2="12"></line>
									<line x1="12" y1="8" x2="12.01" y2="8"></line>
								</svg>
								<span class="pao-context-text"></span>
							</div>
						</div>
					</div>
				</div>
			</div>
		`);

		// Append to body
		$("body").append(this.$widget);

		// Apply custom position if saved in localStorage (takes precedence over preset)
		if (this.custom_position) {
			// Handle both new anchor-based format and legacy absolute format
			if (typeof this.custom_position.anchorRight !== "undefined") {
				// New anchor-based format
				this.apply_custom_position(this.custom_position);
			} else if (this.custom_position.left !== undefined) {
				// Legacy absolute position format
				this.apply_custom_position(this.custom_position.left, this.custom_position.top);
			}
		}

		// Bind events
		this.bind_events();

		// Update context (this also loads suggested prompts)
		this.update_context();

		// Update quota display
		this.update_quota_display();
	}

	bind_events() {
		// Toggle button - suppress click if user was dragging
		this.$widget.find(".pao-toggle-btn").on("click", () => {
			if (this._hasDragged) {
				this._hasDragged = false; // Reset for next interaction
				return; // Don't toggle - was a drag operation
			}
			this.toggle();
		});

		// Close button
		this.$widget.find(".pao-close-btn").on("click", () => {
			this.close();
		});

		// Expand button - open full page assistant
		this.$widget.find(".pao-expand-btn").on("click", () => {
			this.expand_to_full_page();
		});

		// Voice input — tap mic to record, tap again to stop+transcribe+send
		if (window.PAOVoiceCapture) {
			this._voiceCapture = new window.PAOVoiceCapture({
				onStateChange: (state) => this._handleVoiceState(state),
				onElapsed: (seconds) => this._handleVoiceElapsed(seconds),
				onComplete: (blob, durationMs) => this._handleVoiceComplete(blob, durationMs),
				onError: (reason, code) => this._handleVoiceError(reason, code),
			});
			this.$widget.find(".pao-mic-btn").on("click", () => {
				this._voiceCapture.toggle();
			});
			// Global Ctrl+Shift+Space shortcut
			$(document).on("keydown.paoVoice", (e) => {
				if (e.ctrlKey && e.shiftKey && (e.key === " " || e.code === "Space")) {
					const target = e.target;
					const isChatInput = target && target.classList && target.classList.contains("pao-input");
					const isOtherInput = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA") && !isChatInput;
					if (isOtherInput) return;
					e.preventDefault();
					if (!this.is_open) this.open();
					this._voiceCapture.toggle();
				}
			});
		}

		// Setup drag functionality on header
		this.setup_drag_handlers();

		// Setup window resize handler to keep widget within viewport
		this.setup_resize_handler();

		// Input handling
		const $input = this.$widget.find(".pao-input");
		const $sendBtn = this.$widget.find(".pao-send-btn");

		$input.on("input", () => {
			// Auto-resize textarea
			$input[0].style.height = "auto";
			$input[0].style.height = Math.min($input[0].scrollHeight, 120) + "px";

			// Enable/disable send button + toggle active fill
			const hasText = !!$input.val().trim();
			$sendBtn.prop("disabled", !hasText);
			$sendBtn.toggleClass("is-active", hasText);
		});

		$input.on("keydown", (e) => {
			// Let the slash menu handle Enter/Tab/Arrows/Escape when it's open.
			if (this._slashMenuState && this._slashMenuState.open) {
				return;
			}
			// Send on Enter (without Shift)
			if (e.key === "Enter" && !e.shiftKey) {
				e.preventDefault();
				if ($input.val().trim()) {
					this.send_message($input.val().trim());
				}
			}
		});

		$sendBtn.on("click", () => {
			if ($input.val().trim()) {
				this.send_message($input.val().trim());
			}
		});

		// File upload handling
		const $fileBtn = this.$widget.find(".pao-file-upload-btn");
		const $fileInput = this.$widget.find(".pao-file-input");

		$fileBtn.on("click", () => {
			$fileInput.click();
		});

		$fileInput.on("change", (e) => {
			const files = e.target.files;
			if (files && files.length > 0) {
				this.handle_file_upload(files[0]);
				$fileInput.val(""); // Reset input
			}
		});

		// Setup link handlers for document navigation
		this.setup_link_handlers();

		// Task-plan collapsed-summary expand toggle (history reload + live completion)
		this.$widget.on("click", ".pao-plan-summary", function () {
			const $strip = $(this).closest(".pao-plan-strip");
			const $list = $strip.find(".pao-plan-list");
			const open = $list.is(":visible");
			$list.toggle(!open);
			$strip.toggleClass("pao-plan-expanded", !open);
		});

		// Rich block interactive events (accordion toggle, tab switching)
		if (window.PAOWidgetRichBlocks) {
			PAOWidgetRichBlocks.initEventDelegation(this);
		}

		// Slash-command menu for prompt templates
		if (window.PAOWidgetSlashMenu) {
			PAOWidgetSlashMenu.mount(this);
		}
	}

	setup_link_handlers() {
		// Intercept clicks on Frappe app links for SPA navigation
		// (Showdown has openLinksInNewWindow:true, but we want internal links to navigate in-page)
		this.$widget.find(".pao-messages").on("click", 'a[href^="/app/"]', (e) => {
			e.preventDefault();
			const href = $(e.currentTarget).attr("href");

			// Parse the Frappe route: /app/sales-invoice/INV-00001 → ["sales-invoice", "INV-00001"]
			const routeParts = href.replace("/app/", "").split("/").map(decodeURIComponent);

			// Use Frappe's SPA navigation
			frappe.set_route(...routeParts);
		});
	}

	// --- Positioning — delegated to PAOWidgetPositioning ---

	setup_drag_handlers() {
		PAOWidgetPositioning.setup_drag_handlers(this);
	}

	load_custom_position() {
		return PAOWidgetPositioning.load_custom_position();
	}

	setup_resize_handler() {
		PAOWidgetPositioning.setup_resize_handler(this);
	}

	apply_custom_position(leftOrPosition, top) {
		PAOWidgetPositioning.apply_custom_position(this, leftOrPosition, top);
	}

	async update_server_preference(field, value) {
		try {
			await frappe.call({
				method: "pibiassistant.pibiassistant_chat.api.settings.widget.update_user_preference",
				args: {
					field: field,
					value: value,
				},
			});
		} catch (error) {
			// Silently fail
		}
	}

	_handleVoiceState(state) {
		const $btn = this.$widget.find(".pao-mic-btn");
		const $elapsed = this.$widget.find(".pao-mic-elapsed");
		$btn.removeClass("is-recording is-transcribing is-error");
		$elapsed.hide().text("");
		const $input = this.$widget.find(".pao-input");
		if (state === "recording") {
			$btn.addClass("is-recording");
			$elapsed.show();
		} else if (state === "transcribing") {
			$btn.addClass("is-transcribing");
			$input.attr("placeholder", "Transcribing…");
		} else if (state === "error") {
			$btn.addClass("is-error");
			setTimeout(() => $btn.removeClass("is-error"), 200);
		} else {
			$input.attr("placeholder", "Pregúntame lo que necesites...");
		}
	}

	_handleVoiceElapsed(seconds) {
		const m = Math.floor(seconds / 60);
		const s = Math.floor(seconds % 60);
		this.$widget.find(".pao-mic-elapsed").text(`${m}:${s.toString().padStart(2, "0")}`);
	}

	async _resolveTranscribeLanguage() {
		// Resolution order: AR Tenant User profile locale → browser locale → "en".
		// Profile fetch is cached per widget instance after the first call.
		if (this._profileLocale === undefined) {
			try {
				const resp = await frappe.call({
					method: "pibiassistant.pibiassistant_chat.api.get_profile",
					type: "GET",
				});
				this._profileLocale = (resp && resp.message && resp.message.locale) || null;
			} catch {
				this._profileLocale = null;
			}
		}
		const candidates = [this._profileLocale, navigator.language, "en"];
		for (const c of candidates) {
			if (c) return String(c).split("-")[0].toLowerCase();
		}
		return "en";
	}

	async _handleVoiceComplete(blob, durationMs) {
		const formData = new FormData();
		formData.append("audio", blob, "audio.webm");
		formData.append("duration_ms", String(durationMs));
		formData.append("language", await this._resolveTranscribeLanguage());
		try {
			const csrf = window.csrf_token || (window.frappe && window.frappe.csrf_token) || "";
			const res = await fetch("/api/method/pibiassistant.pibiassistant_chat.api.voice.transcribe", {
				method: "POST",
				headers: { "X-Frappe-CSRF-Token": csrf },
				body: formData,
				credentials: "same-origin",
			});
			const json = await res.json();
			const data = json.message || json;
			if (!res.ok || !data || data.text === undefined) {
				frappe.show_alert({ message: "Couldn't transcribe — try again or type instead.", indicator: "red" });
				return;
			}
			if (!data.text) {
				frappe.show_alert({ message: "Didn't catch that.", indicator: "orange" });
				return;
			}
			// Auto-send the transcribed text. send_message() takes the text
			// directly; we don't push it through the textarea first.
			this.send_message(data.text);
		} catch (err) {
			frappe.show_alert({ message: "Couldn't transcribe — try again or type instead.", indicator: "red" });
		} finally {
			if (this._voiceCapture) this._voiceCapture.finishedTranscribing();
		}
	}

	_handleVoiceError(reason, code) {
		const messages = {
			"permission-denied": "Microphone access denied. Enable it in your browser settings.",
			"no-mic": "No microphone found.",
			"too-short": "Didn't catch that.",
			"recorder-error": "Couldn't start recording — try again.",
		};
		const message = messages[code] || "Voice error — try again.";
		frappe.show_alert({ message, indicator: code === "too-short" ? "orange" : "red" });
	}

	setup_keyboard_shortcut(shortcut) {
		// Parse shortcut (e.g., "Ctrl+K")
		const parts = shortcut.split("+");
		const key = parts.pop().toLowerCase();
		const modifiers = parts.map((m) => m.toLowerCase());

		$(document).on("keydown", (e) => {
			const hasCtrl = modifiers.includes("ctrl")
				? e.ctrlKey || e.metaKey
				: !e.ctrlKey && !e.metaKey;
			const hasAlt = modifiers.includes("alt") ? e.altKey : !e.altKey;
			const hasShift = modifiers.includes("shift") ? e.shiftKey : !e.shiftKey;

			if (e.key.toLowerCase() === key && hasCtrl && hasAlt && hasShift) {
				e.preventDefault();
				this.toggle();
			}
		});
	}

	check_and_update_visibility() {
		// Hide widget when on full-page assistant (Vue SPA at /aida or old desk page)
		const route = frappe.get_route() || [];
		const path = window.location.pathname;

		// Hide on Vue SPA (/aida) AND old desk page (pao-assistant)
		if ((route && route[0] === "pao-assistant") || path.startsWith("/aida")) {
			this.$widget && this.$widget.hide();
		} else {
			this.$widget && this.$widget.show();
		}
	}

	update_context() {
		// Delegate context detection to PAOWidgetContext
		this.context = PAOWidgetContext.detect_context();

		// Update context indicator
		this.update_context_indicator();

		// Warm the slash-menu template cache for fully set up users.
		if (this.can_use && this.user_setup_complete && window.PAOWidgetSlashMenu) {
			PAOWidgetSlashMenu.prefetch(this);
		}
	}

	update_context_indicator() {
		const $indicator = this.$widget.find(".pao-context-indicator");
		const $text = $indicator.find(".pao-context-text");

		const contextText = PAOWidgetContext.get_context_display_text(this.context);
		if (contextText) {
			$text.text(contextText);
			$indicator.show();
		} else {
			$indicator.hide();
		}
	}

	async send_message(message) {
		const $input = this.$widget.find(".pao-input");
		const $sendBtn = this.$widget.find(".pao-send-btn");

		// Refuse only when every credit is genuinely gone. PAOWidgetQuota
		// owns that test so this surface cannot drift from AR's admission
		// rule again — a tenant running on prepaid credits is admitted here,
		// exactly as AR and the SPA admit them.
		//
		// Only intercept for admins; non-admins fall through and see the
		// inline streaming error from the API ("Service temporarily
		// unavailable, contact your administrator"). They have no upgrade
		// path so a modal here would just block them with no recourse.
		if (PAOWidgetQuota.is_blocked(this.quota_status) && this.quota_status.is_admin) {
			this.show_quota_blocked_modal(this.quota_status.is_admin);
			return;
		}

		// Clear input
		$input.val("").trigger("input");
		$sendBtn.prop("disabled", true);

		// Hide welcome message if present
		this.$widget.find(".pao-welcome").fadeOut();

		// Add user message to UI with attached files
		this.add_message_to_ui("user", message, false, this.attached_files.slice());

		// Add streaming assistant message placeholder
		const $assistantMsg = this.add_streaming_message();

		// Start stream timeout protection
		if (window.PAOWidgetStreaming) {
			PAOWidgetStreaming.start_stream_timeout(this);
		}

		try {
			// Get attached file URLs
			const file_urls = this.attached_files.map((f) => f.file_url);

			// Build attachments array for Vision API (images with base64 data).
			// Keys must match upload_message_file's response shape — `type`/`format`,
			// not `is_image`/`file_type`. Getting this wrong silently drops every
			// image to the OCR path instead of native vision.
			const attachments = this.attached_files
				.filter((f) => f.base64_data && f.type === "image")
				.map((f) => ({
					type: "image",
					format: f.format || "png",
					data: f.base64_data,
					name: f.file_name,
					file_url: f.file_url,
				}));

			// Counts only — no messages, no urls, no bodies. Enough for the model
			// to know there IS something to look at without shipping anything
			// before the user has approved a capture.
			let client_signals = null;
			try {
				if (window.PAODiagnostics) {
					const counts = window.PAODiagnostics.counts();
					if (counts.console || counts.failed_requests) {
						client_signals = JSON.stringify({ recent_errors: counts });
					}
				}
			} catch (e) {
				/* signals are an optimisation; never block a message on them */
			}

			// Build context from current page for AIDA
			let page_context = "";
			try {
				if (cur_frm) {
					page_context = `[Context: DocType=${cur_frm.doctype}, Name=${cur_frm.docname}]`;
				} else if (cur_list) {
					page_context = `[Context: List ${cur_list.doctype}]`;
				}
			} catch(e) {}

			const full_message = page_context ? `${page_context}\n${message}` : message;

			// Send to AIDA API proxy
			const apiArgs = {
				session_id: this.session_id,
				message: full_message,
			};

			const response = await frappe.call({
				method: "pibiassistant.pibiassistant_chat.api.aida.send_message",
				args: apiArgs,
			});

			// Clear attached files after sending
			this.attached_files = [];
			this.$widget.find(".pao-file-preview-list").hide().empty();

			// Backend will stream response via Socket.IO
			// Response handling is done in socket event handlers
		} catch (error) {
			// The turn never started — clear the watchdog and the in-flight flag
			// so reconnect recovery doesn't go looking for an answer.
			this._isStreaming = false;
			if (window.PAOWidgetStreaming) {
				PAOWidgetStreaming.clear_timeouts();
			}

			$assistantMsg.remove();
			$sendBtn.prop("disabled", false);

			this.add_message_to_ui(
				"assistant",
				"Sorry, I encountered an error. Please try again or check your quota.",
				true
			);
		}
	}

	async handle_file_upload(file) {
		// Validate file size (50MB max)
		const maxSize = 50 * 1024 * 1024;
		if (file.size > maxSize) {
			frappe.show_alert(
				{
					message: __("File size exceeds 50MB limit"),
					indicator: "red",
				},
				5
			);
			return;
		}

		// Show uploading indicator
		frappe.show_alert(
			{
				message: __("Uploading file..."),
				indicator: "blue",
			},
			3
		);

		try {
			// Upload file
			const formData = new FormData();
			formData.append("file", file);

			const response = await fetch(
				"/api/method/pibiassistant.pibiassistant_chat.api.settings.uploads.upload_message_file",
				{
					method: "POST",
					headers: {
						"X-Frappe-CSRF-Token": frappe.csrf_token,
					},
					body: formData,
				}
			);

			const result = await response.json();

			if (result.message && result.message.success) {
				// Add to attached files
				this.attached_files.push(result.message.file);

				// Render preview
				this.render_file_preview(result.message.file);

				frappe.show_alert(
					{
						message: __("File uploaded successfully"),
						indicator: "green",
					},
					3
				);
			} else {
				throw new Error(result.message || "Upload failed");
			}
		} catch (error) {
			PAOLogger.error("File upload error:", error);
			frappe.show_alert(
				{
					message: __("Failed to upload file: {0}", [error.message || "Unknown error"]),
					indicator: "red",
				},
				5
			);
		}
	}

	render_file_preview(file) {
		const $previewList = this.$widget.find(".pao-file-preview-list");
		const fileSize = frappe.form.formatters.FileSize(file.file_size);

		const $preview = $(`
			<div class="pao-file-preview" data-file-url="${file.file_url}">
				<div class="pao-file-icon">
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
						<polyline points="13 2 13 9 20 9"></polyline>
					</svg>
				</div>
				<div class="pao-file-info">
					<div class="pao-file-name">${file.file_name}</div>
					<div class="pao-file-size">${fileSize}</div>
				</div>
				<button class="pao-file-remove" title="Remove">
					<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
						<line x1="18" y1="6" x2="6" y2="18"></line>
						<line x1="6" y1="6" x2="18" y2="18"></line>
					</svg>
				</button>
			</div>
		`);

		// Remove button handler
		$preview.find(".pao-file-remove").on("click", () => {
			this.remove_file(file.file_url);
		});

		$previewList.append($preview).show();
	}

	remove_file(file_url) {
		// Remove from array
		this.attached_files = this.attached_files.filter((f) => f.file_url !== file_url);

		// Remove from UI
		this.$widget.find(`.pao-file-preview[data-file-url="${file_url}"]`).remove();

		// Hide preview list if no files
		if (this.attached_files.length === 0) {
			this.$widget.find(".pao-file-preview-list").hide();
		}
	}

	add_message_to_ui(role, content, is_error = false, attached_files = []) {
		const $messages = this.$widget.find(".pao-messages");

		// Build attachments HTML if there are files
		let attachmentsHtml = "";
		if (attached_files && attached_files.length > 0) {
			attachmentsHtml = '<div class="pao-message-attachments">';
			attached_files.forEach((file) => {
				const fileSizeKB = file.file_size ? (file.file_size / 1024).toFixed(1) : "0";
				attachmentsHtml += `<div class="pao-attachment-item"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg><span class="pao-attachment-name">${
					file.file_name || "Unnamed file"
				}</span><span class="pao-attachment-size">${fileSizeKB} KB</span></div>`;
			});
			attachmentsHtml += "</div>";
		}

		const $message = $(`
			<div class="pao-message pao-message-${role} ${is_error ? "pao-message-error" : ""}">
				<div class="pao-message-avatar">
					${role === "user" ? this.get_user_avatar() : this.get_assistant_avatar()}
				</div>
				<div class="pao-message-content">
					${attachmentsHtml}
					<div class="pao-message-text">${this.format_message(content, role)}</div>
					<div class="pao-message-time">${this.format_time(new Date())}</div>
				</div>
			</div>
		`);

		$messages.append($message);
		this.scroll_to_bottom();

		return $message;
	}

	_toWidgetMessage(msg) {
		// ONE field list for both history readers. Keeping two lists is how
		// `provider` and `fallback_attempted` were lost in production before.
		return {
			role: msg.role,
			content: msg.content,
			model: msg.model,
			credits_used: msg.credits_used,
			routing: msg.routing,
		};
	}

	render_routing_chip(msg, $message) {
		let receipt = msg && msg.routing;
		if (!receipt || msg.role === "user") return;
		if (typeof receipt === "string") {
			try {
				receipt = JSON.parse(receipt);
			} catch (e) {
				return;
			}
		}
		const routing = window.PAOWidgetRouting;
		if (!routing) return;
		const label = routing.chipLabel(receipt);
		if (!label) return;

		const $msg = $message && $message.length
			? $message
			: this.$widget.find(".pao-message").last();
		if (!$msg.length || $msg.find(".pao-routing-chip").length) return;

		// Non-interactive text, and exception-only: the widget has no panel to
		// open, so an ordinary turn renders nothing here at all.
		const $chip = $("<span>")
			.addClass("pao-routing-chip")
			.attr("title", routing.headline(receipt, null))
			.text(label);
		const $time = $msg.find(".pao-message-time");
		($time.length ? $time : $msg).append($chip);
	}

	render_persisted_plan(msg, $message) {
		let blocks = msg && msg.blocks;
		if (!blocks) return;
		if (typeof blocks === "string") {
			try {
				blocks = JSON.parse(blocks);
			} catch (e) {
				return;
			}
		}
		if (!Array.isArray(blocks)) return;
		const planBlock = blocks.find((b) => b && b.type === "plan");
		if (!planBlock || !planBlock.tasks || planBlock.tasks.length === 0) return;
		if (!window.PAOPlanStrip) return;

		// Insert the collapsed summary at the TOP of this message's content.
		const $content = ($message && $message.length
			? $message
			: this.$widget.find(".pao-message").last()
		).find(".pao-message-content");
		if ($content.length) {
			$content.prepend(window.PAOPlanStrip.collapsedHtml(planBlock));
		}
	}

	add_typing_indicator() {
		const $messages = this.$widget.find(".pao-messages");
		const $typing = $(`
			<div class="pao-typing-indicator">
				<div class="pao-message-avatar">
					${this.get_assistant_avatar()}
				</div>
				<div class="pao-typing-dots">
					<span></span><span></span><span></span>
				</div>
			</div>
		`);
		$messages.append($typing);
		this.scroll_to_bottom();
		return $typing;
	}

	// --- Formatting & Avatars — delegated to PAOCore ---

	format_message(content, role = "user") {
		return PAOCore.format_message(content, role);
	}

	format_time(date) {
		return PAOCore.format_time(date);
	}

	get_user_avatar() {
		return PAOCore.get_user_avatar();
	}

	get_assistant_avatar() {
		return PAOCore.get_assistant_avatar();
	}

	// --- Quota/Billing — delegated to PAOWidgetQuota ---

	async update_quota_display() {
		return PAOWidgetQuota.fetch_quota_status(this);
	}

	show_quota_blocked_modal(is_admin) {
		PAOWidgetQuota.show_quota_blocked_modal(this, is_admin);
	}

	scroll_to_bottom() {
		const $messages = this.$widget.find(".pao-messages");
		$messages.scrollTop($messages[0].scrollHeight);
	}

	toggle() {
		if (this.is_open) {
			this.close();
		} else {
			this.open();
		}
	}

	open() {
		this.is_open = true;
		this.is_minimized = false;

		// Stop tooltip animation when opening
		this.stop_tooltip_animation();

		const $chatWindow = this.$widget.find(".pao-chat-window");

		// Stop any ongoing animations to prevent conflicts
		$chatWindow.stop(true, false);

		// Position chat window BEFORE changing classes (so toggle button is still visible)
		this.position_chat_window();

		// Remove any minimized state and add open state
		this.$widget.removeClass("pao-minimized");
		this.$widget.addClass("pao-open");

		// Show the chat window with animation
		$chatWindow.slideDown(200, () => {
			if (!this.can_use) {
				PAOWidgetOnboarding.show_setup_required(this, "not_registered");
			} else if (!this.user_setup_complete) {
				PAOWidgetOnboarding.show_setup_required(this, "needs_setup");
			} else if (!this.privacy_consent_complete) {
				PAOWidgetOnboarding.show_setup_required(this, "needs_consent");
			} else {
				this.$widget.find(".pao-input").focus();
			}
		});

		// Only update context if fully set up (this also loads suggested prompts)
		if (this.can_use && this.user_setup_complete && this.privacy_consent_complete) {
			this.update_context();
		}
	}

	close() {
		this.is_open = false;
		this.is_minimized = true;

		const $chatWindow = this.$widget.find(".pao-chat-window");

		// Stop any ongoing animations to prevent conflicts
		$chatWindow.stop(true, false);

		// Hide the chat window with animation
		$chatWindow.slideUp(200, () => {
			// After animation completes, update classes
			this.$widget.removeClass("pao-open");
			this.$widget.addClass("pao-minimized");
		});

		// Start tooltip animation when closing
		this.start_tooltip_animation();
	}

	expand_to_full_page() {
		/**
		 * Open the full-page assistant view (Vue SPA), preserving the current session
		 */
		// Store session_id for the SPA to pick up. Same-tab navigation only,
		// so sessionStorage scopes the hand-off to this tab — other tabs
		// won't inherit the session id and receive its socket events.
		try {
			sessionStorage.setItem(
				"pao_active_session",
				PAOWidgetSession.encode(this.session_id, this.current_user())
			);
		} catch (e) {
			// Silently fail
		}

		// Close the widget
		this.close();

		// Navigate to Vue SPA full page assistant
		window.location.href = "/aida";
	}

	position_chat_window() {
		// Smart positioning to ensure chat window stays within viewport
		const $chatWindow = this.$widget.find(".pao-chat-window");
		const $toggleBtn = this.$widget.find(".pao-toggle-btn");

		// Phone/tablet layout is CSS (bottom sheet). Clear inline desktop
		// coordinates so they cannot pin a 400×650 box to the top.
		if (window.innerWidth < 1024) {
			$chatWindow.css({ top: "", left: "", right: "", bottom: "", width: "", height: "" });
			return;
		}

		// Safety check - ensure button exists and is visible
		if (!$toggleBtn.length || !$toggleBtn.is(":visible")) {
			// Fallback to widget position
			const widgetRect = this.$widget[0].getBoundingClientRect();
			if (widgetRect.width === 0 || widgetRect.height === 0) {
				return;
			}
		}

		// Get button position
		const btnRect = $toggleBtn[0].getBoundingClientRect();

		// Additional safety check for invalid dimensions
		if (btnRect.width === 0 || btnRect.height === 0) {
			// Use center of screen as fallback
			const chatWidth = 400;
			const chatHeight = 650;
			$chatWindow.css({
				position: "fixed",
				left: Math.max(20, (window.innerWidth - chatWidth) / 2) + "px",
				top: Math.max(20, (window.innerHeight - chatHeight) / 2) + "px",
				right: "auto",
				bottom: "auto",
			});
			return;
		}
		const chatWidth = 400; // From CSS
		const chatHeight = 650; // From CSS
		const spacing = 16; // Gap between button and chat

		// Get viewport dimensions
		const viewportWidth = window.innerWidth;
		const viewportHeight = window.innerHeight;

		// Calculate optimal position
		let left, top, bottom, right;

		// Determine vertical position (prefer above button)
		const spaceAbove = btnRect.top;
		const spaceBelow = viewportHeight - btnRect.bottom;

		if (spaceAbove >= chatHeight + spacing) {
			// Position above button - align bottom of chat with top of button with minimal spacing
			bottom = viewportHeight - btnRect.top + 10; // Reduced spacing to 10px
			top = "auto";
		} else if (spaceBelow >= chatHeight + spacing) {
			// Position below button
			top = btnRect.bottom + spacing;
			bottom = "auto";
		} else {
			// Not enough space - anchor to viewport with minimal bottom padding
			// Calculate to leave just enough room for the button
			const buttonSpaceNeeded = viewportHeight - btnRect.top + 10; // 10px padding
			bottom = buttonSpaceNeeded;
			top = 20; // Add top padding to prevent overflow
		}

		// Determine horizontal position (prefer aligned with button)
		const spaceRight = viewportWidth - btnRect.right;
		const spaceLeft = btnRect.left;

		if (spaceRight >= chatWidth) {
			// Align left edge with button
			left = btnRect.left;
			right = "auto";
		} else if (spaceLeft >= chatWidth) {
			// Align right edge with button
			right = viewportWidth - btnRect.right;
			left = "auto";
		} else {
			// Center horizontally
			left = Math.max(20, (viewportWidth - chatWidth) / 2);
			right = "auto";
		}

		// Apply positioning
		$chatWindow.css({
			position: "fixed",
			left: left !== "auto" ? left + "px" : "auto",
			right: right !== "auto" ? right + "px" : "auto",
			top: top !== "auto" ? top + "px" : "auto",
			bottom: bottom !== "auto" ? bottom + "px" : "auto",
		});
	}

	// --- Streaming — delegated to PAOWidgetStreaming ---

	setup_socket_listeners() {
		PAOWidgetStreaming.setup_socket_listeners(this);
	}

	add_streaming_message() {
		return PAOWidgetStreaming.add_streaming_message(this);
	}

	/**
	 * Session precedence:
	 * 1. One-time SPA→widget hand-off token (consumed on read).
	 * 2. The widget's own persisted session (survives a same-tab reload).
	 * 3. A fresh session.
	 *
	 * Either stored id may have been cloned into this tab by "Duplicate tab",
	 * so it is only adopted when no other live widget answers the claim probe.
	 */
	async resolve_session() {
		// Widget assets are served unhashed behind a long max-age, so a stale
		// cache can deliver this file without widget_session.js. Without it we
		// cannot tell whose stored session this is, so start a fresh one rather
		// than leaving the widget unmounted or adopting someone else's.
		if (typeof PAOWidgetSession === "undefined") {
			this.session_id = this.generate_session_id();
			this.session_restored = false;
			return;
		}

		const stored = this.get_stored_session();
		const persisted = this.get_persistent_session();

		const probe = PAOWidgetSession.make_claim_probe();
		const outcome = await PAOWidgetSession.resolve({
			stored: stored,
			persisted: persisted,
			owner: this.current_user(),
			isClaimed: probe,
			generate: () => this.generate_session_id(),
		});

		this.session_id = outcome.session_id;
		this.session_restored = outcome.restored;

		if (outcome.consumed_handoff) {
			this.clear_stored_session();
		}
		// Persist for the next same-tab reload. sessionStorage survives reload
		// but clears on tab close — so a closed tab / new tab starts fresh.
		this.set_persistent_session(this.session_id);
		PAOWidgetSession.start_claim_responder(this);
	}

	generate_session_id() {
		return PAOCore.generate_session_id();
	}

	/** The user this tab is currently logged in as, or null. */
	current_user() {
		try {
			return (frappe && frappe.session && frappe.session.user) || null;
		} catch (e) {
			return null;
		}
	}

	/**
	 * Get stored session from storage (set by SPA when returning to desk).
	 * Uses sessionStorage so the hand-off is scoped to the originating tab —
	 * a freshly-opened tab won't inherit the session id (cross-tab continuity
	 * is intentionally not a use case). Returns {id, user} — the owner decides
	 * whether it may be adopted, since sessionStorage outlives a login.
	 */
	get_stored_session() {
		try {
			return PAOWidgetSession.decode(sessionStorage.getItem("pao_widget_session"));
		} catch (e) {
			return null;
		}
	}

	/**
	 * Clear the stored session after consuming it (one-time use).
	 * Also clears the legacy localStorage key so users with values written by
	 * older builds get a clean slate after upgrading.
	 */
	clear_stored_session() {
		try {
			sessionStorage.removeItem("pao_widget_session");
			localStorage.removeItem("pao_widget_session");
		} catch (e) {
			// Silently fail
		}
	}

	/**
	 * Get the widget's own persisted session (survives a same-tab reload).
	 * Distinct from the one-time SPA hand-off key — this is NOT consumed on read.
	 */
	get_persistent_session() {
		try {
			return PAOWidgetSession.decode(
				sessionStorage.getItem("pao_widget_persistent_session")
			);
		} catch (e) {
			return null;
		}
	}

	/**
	 * Persist the widget's session so a same-tab reload restores the conversation.
	 * Stamped with the current user — a later login must not inherit it.
	 */
	set_persistent_session(session_id) {
		try {
			if (session_id) {
				sessionStorage.setItem(
					"pao_widget_persistent_session",
					PAOWidgetSession.encode(session_id, this.current_user())
				);
			}
		} catch (e) {
			// Silently fail (e.g. storage disabled)
		}
	}

	// --- Tooltips — delegated to PAOWidgetTooltips ---

	start_tooltip_animation() {
		PAOWidgetTooltips.start_tooltip_animation(this);
	}

	stop_tooltip_animation() {
		PAOWidgetTooltips.stop_tooltip_animation(this);
	}

	// --- User Auth — delegated to PAOWidgetOnboarding ---

	async check_user_auth() {
		return PAOWidgetOnboarding.check_user_auth(this);
	}

	show_chat_interface() {
		PAOWidgetOnboarding.show_chat_interface(this);
	}

	// --- Teardown for hot-unmount ---
	//
	// Called when an admin toggles PA Chat off from PA Admin without a
	// page refresh. Removes the widget DOM, detaches realtime listeners,
	// kills the tooltip rotation interval, and unsets the global instance
	// so a subsequent enable can re-init from a clean slate.
	teardown() {
		try {
			this.stop_tooltip_animation();
		} catch (e) {
			// Tooltip animation may not have started — safe to ignore.
		}

		try {
			PAOWidgetSession.stop_claim_responder(this);
			if (this.session_id && frappe.realtime && frappe.realtime.task_unsubscribe) {
				frappe.realtime.task_unsubscribe(this.session_id);
			}
			if (frappe.realtime && frappe.realtime.off) {
				frappe.realtime.off("pao_message_stream");
				frappe.realtime.off("ar_interrupt_event");
			}
		} catch (e) {
			PAOLogger.debug("Teardown: realtime cleanup failed", e);
		}

		try {
			if (this.$widget) {
				this.$widget.remove();
				this.$widget = null;
			}
		} catch (e) {
			PAOLogger.debug("Teardown: DOM removal failed", e);
		}

		// Onboarding overlay and any other body-level modals the widget owns
		$("body > .pao-onboarding-overlay, body > .pao-modal").remove();

		if (window.pao_widget === this) {
			window.pao_widget = null;
		}
	}
}

// Initialize AIDA widget when Frappe app is ready
$(document).on("app_ready", function () {
	PAOLogger.debug("app_ready event fired");
	initPAOWidget();
});

// Fallback: Initialize after DOM ready if app_ready hasn't fired within 5 seconds
// This handles edge cases where app_ready event might not fire properly
$(document).ready(function () {
	setTimeout(function () {
		if (!window.pao_widget) {
			PAOLogger.debug("Fallback initialization triggered (app_ready may not have fired)");
			initPAOWidget();
		}
	}, 5000);
});

function shouldMountPAOWidget() {
	// Desk bundle only. Guests (login / website) never get a launcher.
	// Phones and tablets used to be skipped via frappe.is_mobile() (width < 768),
	// which hid the widget on the whole mobile Desk and on many tablet
	// emulations. Compact screens get a smaller launcher + nearly full-screen
	// panel in CSS instead of being excluded.
	if (typeof frappe === "undefined" || !frappe.session) return false;
	return frappe.session.user !== "Guest";
}

function initPAOWidget() {
	// Prevent double initialization
	if (window.pao_widget) {
		PAOLogger.debug("Widget already initialized");
		return;
	}

	if (!shouldMountPAOWidget()) {
		PAOLogger.debug(
			"Skipping widget: user=" + (frappe && frappe.session && frappe.session.user)
		);
		return;
	}

	try {
		PAOLogger.debug("Initializing widget...");
		window.pao_widget = new PAOWidget();
		PAOLogger.debug("Widget initialized successfully");
	} catch (error) {
		PAOLogger.error("Widget initialization failed:", error);
	}
}

// Public helpers for the PA Admin hot-toggle flow. Available on window so
// pa_admin_tools.js can call them without importing this module.
window.initPAOWidget = initPAOWidget;
window.paoWidgetRemount = function () {
	// Tear down any existing instance (ghost or live) and re-init from a
	// clean slate. Called by PA Admin after toggling PA Chat on.
	if (window.pao_widget) {
		try {
			window.pao_widget.teardown();
		} catch (e) {
			// Last-resort cleanup: force-null so initPAOWidget can proceed.
			window.pao_widget = null;
		}
	}
	initPAOWidget();
};
window.paoWidgetTeardown = function () {
	// Tear down any live instance. Called by PA Admin after toggling PA
	// Chat off. Safe no-op when no instance exists.
	if (window.pao_widget) {
		try {
			window.pao_widget.teardown();
		} catch (e) {
			window.pao_widget = null;
		}
	}
};
