// pibiAssistant - AIDA Widget Streaming Module
// Handles Socket.IO streaming, processing indicators, and tool indicators for the AIDA widget

/** Opening tag, question text and optional description shared by every question card. */
function pao_question_head(tool_id_attr, reason, with_description) {
	const esc = (v) => PAOCore.escape_html(v);
	const description =
		with_description && reason.description
			? `<div class="pao-interaction-description">${esc(reason.description)}</div>`
			: "";
	return `<div class="pao-interaction-card pao-interaction-question" data-tool-id="${tool_id_attr}">
					<div class="pao-interaction-question-text">${esc(reason.question || "")}</div>
					${description}`;
}

/**
 * Widget Streaming Module
 * Responsible for real-time streaming, processing indicators, and tool indicators
 */
window.PAOWidgetStreaming = {
	// Timeout configuration (matching Vue frontend)
	STREAM_TIMEOUT_MS: 5 * 60 * 1000, // 5 minutes max stream time
	ACTIVITY_TIMEOUT_MS: 120 * 1000, // 120 seconds inactivity timeout (includes heartbeats)

	// Timeout tracking
	_streamTimeoutId: null,
	_activityTimeoutId: null,

	// Connection recovery state
	_recoveryBound: false,
	_hasConnected: false,
	_visibilityHandler: null,
	_reconcileInFlight: false,

	// Processing indicator state (per-widget, stored on widget instance)
	PROCESSING_TIPS: [
		__("Tip: Use Shift+Enter for multi-line messages"),
		__("Tip: You can attach files for context-aware assistance"),
		__("Tip: Click the expand button to open in a larger window"),
		__("\"The best way to predict the future is to create it.\" — Alan Kay"),
		__("\"Simplicity is the ultimate sophistication.\" — Leonardo da Vinci"),
		__("\"First, solve the problem. Then, write the code.\" — John Johnson"),
		__("\"Any fool can write code that a computer can understand. Good programmers write code that humans can understand.\" — Martin Fowler"),
	],

	/**
	 * Subscribe the socket to the session's realtime room.
	 * Frappe's `task_subscribe` joins `task_progress:<id>`; the server emits
	 * pao_message_stream into that same room (see _emit_socket_event in
	 * api/chat.py). This is what scopes events to this tab only.
	 */
	subscribe_session(session_id) {
		if (session_id && frappe.realtime && frappe.realtime.task_subscribe) {
			frappe.realtime.task_subscribe(session_id);
		}
	},

	/**
	 * Run `fn` once frappe.realtime.socket exists. Both `realtime.on()` and
	 * `realtime.emit()` are silent no-ops while the socket is undefined, and
	 * the socket can lag script load — binding blind loses every event for the
	 * page. Mirrors the poll in widget_browser_tools.js (10s ceiling).
	 */
	_when_socket_ready(fn, attempt) {
		if (typeof frappe !== "undefined" && frappe.realtime && frappe.realtime.socket) {
			fn();
			return;
		}
		const next = (attempt || 0) + 1;
		if (next > 100) {
			PAOLogger.warn("frappe.realtime.socket unavailable — streaming disabled");
			return;
		}
		setTimeout(() => this._when_socket_ready(fn, next), 100);
	},

	/**
	 * Set up Socket.IO listeners for streaming responses
	 * @param {Object} widget - Widget instance reference
	 */
	setup_socket_listeners(widget) {
		this._when_socket_ready(() => this._bind_socket_listeners(widget));
	},

	_bind_socket_listeners(widget) {
		this.subscribe_session(widget.session_id);
		this.setup_connection_recovery(widget);
		frappe.realtime.on("pao_message_stream", (data) => {
			// Only process events for this session (defence-in-depth — the
			// task_progress room scoping is the primary filter)
			if (data.session_id !== widget.session_id) {
				return;
			}

			// Reset activity timeout on any event
			this.reset_activity_timeout(widget);

			switch (data.event) {
				case "stream_start":
					if (data.message_id) {
						widget.current_message_id = data.message_id;
						this.note_seen_message(widget, data.message_id);
					}
					// Stop pressed before the turn existed: the first cancel found nothing to stop.
					if (widget._stopping) widget.request_cancel();
					if (widget._lateAbort && widget._lateAbort !== true && data.message_id !== widget._lateAbort) {
						widget._lateAbort = null;
					}
					widget._activePlan = null;
					if (data.resumed) {
						// Reuse the existing streaming message from the interrupted stream
						// so the resumed response continues in the same bubble.
						const $existing = widget.$widget.find(".pao-message-streaming");
						if ($existing.length) {
							// Element already exists and has the streaming class — just
							// make sure the text container is visible and add cursor back
							const $content = $existing.find(".pao-message-text");
							$content.show();
							if (!$content.find(".pao-streaming-cursor").length) {
								$content.append('<span class="pao-streaming-cursor">▋</span>');
							}
						} else {
							// No existing element (e.g. page was refreshed) — create new
							this.add_streaming_message(widget);
						}
					}
					break;

				case "model_selected":
					if (data.selected) {
						PAOLogger.debug("Auto mode selected model:", data.selected);
					}
					break;

				case "stream_chunk":
					this.update_streaming_message(widget, data.chunk);
					break;

				case "thinking":
					this.show_thinking_indicator(widget, data.content);
					break;

				case "thinking_complete":
					this.hide_thinking_indicator(widget);
					break;

				case "tool_call_start":
					this.show_tool_indicator(widget, data.tool_name, data.tool_id);
					break;

				case "tool_call_result":
				case "tool_result":
					this.hide_tool_indicator(widget, data.tool_id);
					break;

				case "tool_cancelled":
					this.hide_tool_indicator(widget, data.tool_id, true);
					break;

				case "plan_created":
				case "task_updated":
					this.render_plan(widget, data.plan);
					break;

				case "plan_complete":
					this.collapse_plan(widget, data.plan);
					break;

				case "approval_required":
					this.show_interaction_card(widget, data);
					break;

				case "stream_complete":
					this.clear_timeouts();
					if (data.interrupted) {
						// HITL interrupt — stream paused, waiting for user response.
						// Don't finalize; keep the interaction card visible. The
						// watchdog is re-armed when the resume is submitted.
						widget._isStreaming = false;
						this.stop_processing_indicator(widget);
						widget.$widget.find(".pao-thinking-indicator").remove();
						widget.$widget.find(".pao-tool-indicator").remove();
						break;
					}
					// Stream finished cleanly — drop any stale pending-interrupt
					// state so the next turn starts fresh.
					widget._pendingInterrupts = [];
					widget._isSubmittingInterrupts = false;
					this.clear_approval_attention(widget);
					this.finalize_streaming_message(
						widget,
						data.full_response,
						data.tokens_used,
						data.quota_remaining,
						data
					);
					break;

				case "stream_error":
					this.clear_timeouts();
					this.handle_stream_error(widget, data);
					break;

				case "stream_aborted": {
					const late = widget._lateAbort;
					widget._lateAbort = null;
					if (late && (late === true || !data.message_id || data.message_id === late)) break;
					this.finalize_aborted(widget, data);
					break;
				}
			}
		});

		// AR-emitted lifecycle events ("ar_interrupt_event") — distinct channel
		// from `pao_message_stream` so AR doesn't have to know PA's wire format.
		// Payload: {kind: "expired"|"resolved", session_id: str}.
		frappe.realtime.on("ar_interrupt_event", (data) => {
			if (!data || !data.session_id) return;
			if (data.session_id !== widget.session_id) return; // wrong session — ignore
			if (data.kind === "expired") {
				this.mark_interaction_expired(widget);
			} else if (data.kind === "resolved") {
				this.dismiss_resolved_interaction(widget);
			}
			// Unknown kinds: ignore silently for forward-compat.
		});
	},

	/**
	 * Start stream timeouts (called when sending a message)
	 * @param {Object} widget - Widget instance
	 */
	start_stream_timeout(widget) {
		this.clear_timeouts();
		widget._isStreaming = true;

		// Max stream time (5 minutes)
		this._streamTimeoutId = setTimeout(() => {
			this.handle_stream_timeout(widget, __("Request exceeded maximum time (5 minutes)"));
		}, this.STREAM_TIMEOUT_MS);

		// Activity timeout (60 seconds without events)
		this._activityTimeoutId = setTimeout(() => {
			this.handle_stream_timeout(widget, __("No response received. Please try again."), {
				allowRetry: true,
			});
		}, this.ACTIVITY_TIMEOUT_MS);
	},

	/**
	 * Reset activity timeout (called on each received event)
	 * @param {Object} widget - Widget instance
	 */
	reset_activity_timeout(widget) {
		if (this._activityTimeoutId) {
			clearTimeout(this._activityTimeoutId);
			this._activityTimeoutId = setTimeout(() => {
				this.handle_stream_timeout(
					widget,
					__("Connection appears to have stalled. Please try again."),
					{ allowRetry: true }
				);
			}, this.ACTIVITY_TIMEOUT_MS);
		}
	},

	/**
	 * Clear all timeouts
	 */
	clear_timeouts() {
		if (this._streamTimeoutId) {
			clearTimeout(this._streamTimeoutId);
			this._streamTimeoutId = null;
		}
		if (this._activityTimeoutId) {
			clearTimeout(this._activityTimeoutId);
			this._activityTimeoutId = null;
		}
	},

	/**
	 * Handle stream timeout.
	 *
	 * Silence is not proof of failure: a dropped socket loses every remaining
	 * event for the turn (room membership is per-connection and emits are
	 * fire-and-forget), while the relay keeps running and persists the answer.
	 * So check the server before declaring failure, and give a socket that is
	 * actually down one more window to come back.
	 *
	 * @param {Object} widget - Widget instance
	 * @param {string} message - Timeout message
	 * @param {Object} [options] - {allowRetry: bool} — grant the grace window
	 */
	async handle_stream_timeout(widget, message, options) {
		this.clear_timeouts();

		if (await this.reconcile_from_server(widget)) {
			return;
		}

		if (options && options.allowRetry && !this._socket_connected()) {
			this._nudge_socket();
			this.update_processing_status(widget, __("Connection lost — reconnecting..."));
			this._activityTimeoutId = setTimeout(() => {
				this.handle_stream_timeout(widget, message);
			}, this.ACTIVITY_TIMEOUT_MS);
			return;
		}

		this._fail_turn(widget, message);
	},

	/**
	 * Close out the in-flight turn with a notice instead of an answer.
	 * @param {string} [icon] - Leading glyph; defaults to the timeout clock.
	 */
	_fail_turn(widget, message, icon) {
		widget._isStreaming = false;
		this.stop_processing_indicator(widget);

		widget.$widget.find(".pao-message-streaming").remove();
		widget.$widget.find(".pao-thinking-indicator").remove();
		widget.$widget.find(".pao-tool-indicator").remove();

		const prefix = icon === undefined ? "" : icon;
		widget.add_message_to_ui("assistant", prefix ? `${prefix} ${message}` : message, true);
		this._release_composer(widget);
		this.clear_approval_attention(widget);
	},

	// --- Connection Recovery ---

	/**
	 * Wire post-reconnect recovery.
	 *
	 * Frappe's realtime client auto-reconnects but never re-emits
	 * `task_subscribe` (see socketio_client.js), so the fresh connection is no
	 * longer in `task_progress:<session_id>` — every remaining event for the
	 * turn in flight is lost. It also caps at `reconnectionAttempts: 3`, after
	 * which nothing revives the socket on its own. "connect" fires on the
	 * first connection AND on every reconnection, which is the only hook the
	 * client offers; the SPA recovers the same way (useStreaming.js).
	 */
	setup_connection_recovery(widget) {
		if (this._recoveryBound) return;
		// frappe.realtime.on() is a silent no-op while the socket is undefined.
		if (typeof frappe === "undefined" || !frappe.realtime || !frappe.realtime.socket) {
			return;
		}

		this._hasConnected = !!frappe.realtime.socket.connected;

		this._connectHandler = () => this._on_socket_connect(widget);
		this._disconnectHandler = () => this._on_socket_disconnect(widget);
		frappe.realtime.on("connect", this._connectHandler);
		frappe.realtime.on("disconnect", this._disconnectHandler);

		this._visibilityHandler = () => this._on_tab_visible(widget);
		document.addEventListener("visibilitychange", this._visibilityHandler);

		this._recoveryBound = true;
	},

	teardown_recovery() {
		if (!this._recoveryBound) return;
		try {
			frappe.realtime.off("connect", this._connectHandler);
			frappe.realtime.off("disconnect", this._disconnectHandler);
		} catch (e) {
			/* socket already gone */
		}
		document.removeEventListener("visibilitychange", this._visibilityHandler);
		this._connectHandler = this._disconnectHandler = this._visibilityHandler = null;
		this._recoveryBound = false;
	},

	_on_socket_connect(widget) {
		const first = !this._hasConnected;
		this._hasConnected = true;
		// The first connection is init's job — unless a turn is already in
		// flight, meaning the send raced a socket that had never connected.
		if (first && !widget._isStreaming) return;
		this.recover_session(widget);
	},

	_on_socket_disconnect(widget) {
		if (widget && widget._isStreaming) {
			this.update_processing_status(widget, __("Connection lost — reconnecting..."));
		}
	},

	/**
	 * A backgrounded tab can have its socket suspended and its reconnection
	 * attempts exhausted, leaving a dead socket that nothing revives when the
	 * user returns. A throttled tab can also keep a socket that still reports
	 * connected while having missed events — "connect" never fires for that
	 * one, so an in-flight turn has to recover here instead.
	 */
	_on_tab_visible(widget) {
		if (document.visibilityState !== "visible") return;
		if (!this._socket_connected()) {
			this._nudge_socket();
			return; // recovery rides the "connect" handler
		}
		if (widget && widget._isStreaming) this.recover_session(widget);
	},

	/**
	 * Re-join the session room and re-read what events may have carried while
	 * this client wasn't listening.
	 */
	recover_session(widget) {
		if (!widget || !widget.session_id) return;
		this.subscribe_session(widget.session_id);
		this.hydrate_pending_interrupt(widget);
		if (widget._isStreaming) {
			this.update_processing_status(widget, __("Processing your request..."));
			this.reconcile_from_server(widget);
		}
	},

	_socket_connected() {
		const socket = typeof frappe !== "undefined" && frappe.realtime && frappe.realtime.socket;
		return !!(socket && socket.connected);
	},

	_nudge_socket() {
		const socket = typeof frappe !== "undefined" && frappe.realtime && frappe.realtime.socket;
		if (socket && !socket.connected && typeof socket.connect === "function") {
			socket.connect();
		}
	},

	/**
	 * Remember an assistant turn we have already rendered, so a recovery read
	 * can tell a new answer from one that is already on screen.
	 */
	note_seen_message(widget, messageId) {
		if (!widget || !messageId) return;
		if (!widget._seenMessageIds) widget._seenMessageIds = new Set();
		widget._seenMessageIds.add(messageId);
	},

	/**
	 * Whether a persisted assistant row represents a finished turn. Streaming
	 * persists an empty shell row at stream_start and backfills it on
	 * completion, so "has content, blocks, or a terminal flag" is what
	 * separates a turn that landed from one still in flight. Mirrors the SPA's
	 * isFinalizedRow (stores/chat/utils.js), except `blocks` arrives here as
	 * the raw JSON string the server stored.
	 */
	_is_finalized_row(row) {
		if (!row || row.role !== "assistant") return false;
		if (row.errored || row.aborted) return true;
		if (row.content) return true;

		let blocks = row.blocks;
		if (typeof blocks === "string") {
			try {
				blocks = JSON.parse(blocks);
			} catch (e) {
				return false;
			}
		}
		return Array.isArray(blocks) && blocks.length > 0;
	},

	/**
	 * Pick the server row that finishes the turn we are still waiting on, or
	 * null if there is nothing to adopt yet.
	 *
	 * Matching on the turn's message_id is exact. Without one — the socket
	 * dropped before stream_start — the trailing row is the only candidate,
	 * and it is adopted only when it carries an id we have never rendered.
	 * Anything looser would replay the previous answer as if it were this one
	 * (e.g. under GDPR processing restriction, where nothing is persisted).
	 */
	_pick_recovery_row(rows, messageId, seenIds) {
		if (!Array.isArray(rows) || !rows.length) return null;

		if (messageId) {
			const match = rows.filter((m) => m.message_id === messageId)[0];
			return match && this._is_finalized_row(match) ? match : null;
		}

		const last = rows[rows.length - 1];
		if (!this._is_finalized_row(last) || !last.message_id) return null;
		if (seenIds && seenIds.has(last.message_id)) return null;
		return last;
	},

	_fetch_session_messages(session_id) {
		return new Promise((resolve, reject) => {
			frappe.call({
				silent: true,
				method: "pibiassistant.pibiassistant_chat.api.chat.sessions.get_session_history",
				type: "GET",
				args: { session_id: session_id },
				callback: (r) => {
					const payload = r && r.message;
					if (Array.isArray(payload)) return resolve(payload);
					resolve(payload && Array.isArray(payload.messages) ? payload.messages : []);
				},
				error: (err) => reject(err),
			});
		});
	},

	/**
	 * Re-read the persisted turn and adopt it if the answer landed while we
	 * weren't listening. Stream events have no server-side replay buffer, so
	 * the persisted row is the only recovery path.
	 *
	 * @returns {Promise<boolean>} whether an answer was adopted
	 */
	async reconcile_from_server(widget) {
		if (!widget || !widget.session_id) return false;
		if (this._reconcileInFlight) return false;

		this._reconcileInFlight = true;
		const sessionId = widget.session_id;
		try {
			const rows = await this._fetch_session_messages(sessionId);
			// The user may have switched conversations during the await, or the
			// real stream_complete may have landed and finalized the turn — in
			// which case adopting now would render the answer twice.
			if (widget.session_id !== sessionId || !widget._isStreaming) return false;

			const row = this._pick_recovery_row(
				rows,
				widget.current_message_id,
				widget._seenMessageIds
			);
			if (!row) return false;

			this._adopt_server_answer(widget, row);
			return true;
		} catch (err) {
			PAOLogger.error("Failed to reconcile session from server:", err);
			return false;
		} finally {
			this._reconcileInFlight = false;
		}
	},

	/**
	 * Render a persisted answer into the turn the user is still watching.
	 */
	_adopt_server_answer(widget, row) {
		this.clear_timeouts();
		this.note_seen_message(widget, row.message_id);

		// A row can be terminal without text (blocks-only, or a stop/error flag).
		// The widget renders text, so that becomes a plain notice.
		if (!row.content) {
			this._fail_turn(
				widget,
				row.aborted
					? __("Response stopped.")
					: __("The response ended unexpectedly. Please try again."),
				""
			);
			return;
		}

		widget._isStreaming = false;
		const $streaming = widget.$widget.find(".pao-message-streaming");
		if ($streaming.length) {
			// finalize_streaming_message prefers the locally streamed text; the
			// server row is the complete one, so it wins.
			$streaming.find(".pao-message-text").data("raw-markdown", row.content);
			this.finalize_streaming_message(widget, row.content, 0, null);
		} else {
			// The turn was already given up on (timeout wiped the bubble) —
			// append the answer rather than losing it.
			widget.add_message_to_ui("assistant", row.content);
			widget.messages.push({ role: "assistant", content: row.content });
		}
		this._release_composer(widget);
	},

	// --- Processing Indicator ---

	/**
	 * Start the processing indicator timers for tips display
	 * @param {Object} widget - Widget instance
	 */
	start_processing_indicator(widget) {
		this.stop_processing_indicator(widget);

		widget._processing_tip_index = Math.floor(Math.random() * this.PROCESSING_TIPS.length);

		widget._processing_tip_timer = setTimeout(() => {
			this.show_processing_tip(widget);

			widget._processing_tip_rotation = setInterval(() => {
				widget._processing_tip_index =
					(widget._processing_tip_index + 1) % this.PROCESSING_TIPS.length;
				this.show_processing_tip(widget);
			}, 8000);
		}, 5000);
	},

	/**
	 * Display the current processing tip
	 * @param {Object} widget - Widget instance
	 */
	show_processing_tip(widget) {
		const $tip = widget.$widget.find(".pao-processing-tip");
		if ($tip.length > 0) {
			$tip.css("display", "block").text(this.PROCESSING_TIPS[widget._processing_tip_index]);
		}
	},

	/**
	 * Clear processing indicator timers
	 * @param {Object} widget - Widget instance
	 */
	stop_processing_indicator(widget) {
		if (widget._processing_tip_timer) {
			clearTimeout(widget._processing_tip_timer);
			widget._processing_tip_timer = null;
		}
		if (widget._processing_tip_rotation) {
			clearInterval(widget._processing_tip_rotation);
			widget._processing_tip_rotation = null;
		}
	},

	/**
	 * Update the processing status message
	 * @param {Object} widget - Widget instance
	 * @param {string} status - Status text
	 */
	update_processing_status(widget, status) {
		const $text = widget.$widget.find(".pao-processing-text");
		if ($text.length > 0) {
			$text.text(status);
		}
	},

	// --- HITL Interaction Cards ---

	/**
	 * Flip the most recent pending interaction card to "expired" state.
	 * Called when AR emits ar_interrupt_event{kind:"expired"}.
	 */
	mark_interaction_expired(widget) {
		const $card = widget.$widget
			.find(".pao-interaction-card")
			.not(".pao-interaction-decided")
			.last();
		if (!$card.length) return;
		$card.addClass("pao-interaction-decided pao-interaction-expired");
		$card.find("button, input").prop("disabled", true);
		// Replace card body with a warning banner. Match the SPA's amber tone
		// (#f59e0b, the codebase's `--pao-warning`).
		$card.html(
			`<div class="pao-interaction-expired-banner" >${__("Approval expired — resend to continue")}</div>`
		);
		// The banner says "resend", so the composer has to accept one. It was
		// disabled when the card rendered and only resolve_interaction re-enables
		// it — which never runs for a card that expired.
		this._release_composer(widget);
		this.clear_approval_attention(widget);
	},

	/**
	 * Dismiss a pending card because another tab resolved the pause.
	 * Subtle gray styling — the action is done; no input needed.
	 */
	dismiss_resolved_interaction(widget) {
		const $card = widget.$widget
			.find(".pao-interaction-card")
			.not(".pao-interaction-decided")
			.last();
		if (!$card.length) return;
		$card
			.addClass("pao-interaction-decided pao-interaction-resolved-elsewhere")
			.html(`<div class="pao-interaction-note">${__("Resolved in another tab")}</div>`);
		this._release_composer(widget);
		this.clear_approval_attention(widget);
	},

	/**
	 * Best-effort: call AR (via PA proxy) to check for a pending HITL
	 * pause on this session. If one is present, render the InteractionCard
	 * via the existing show_interaction_card path (which is now idempotent).
	 * Used on widget init() and after socket reconnect.
	 */
	hydrate_pending_interrupt(widget) {
		if (!widget.session_id) return;
		frappe.call({
			silent: true,
			method: "pibiassistant.pibiassistant_chat.api.chat.get_pending_interrupt",
			args: { session_id: widget.session_id },
			type: "GET",
			callback: (r) => {
				const data = r && r.message;
				if (!data || !data.pending || !data.event) return;
				// Reuse the existing card-render path. The guard in
				// show_interaction_card prevents duplicates.
				this.show_interaction_card(widget, data.event);
				this._schedule_local_expiry(widget, data.expires_at);
			},
		});
	},

	/**
	 * Safety net for the expiry flip. The authoritative `ar_interrupt_event`
	 * is published on AR's own realtime, which a split deployment's browsers
	 * never see, so without a local timer an expired card stays interactive
	 * and its composer stays locked until a page reload.
	 */
	_schedule_local_expiry(widget, expiresAt) {
		if (widget._expiryTimer) {
			clearTimeout(widget._expiryTimer);
			widget._expiryTimer = null;
		}
		if (!expiresAt) return;

		const ms = new Date(expiresAt).getTime() - Date.now();
		if (!(ms > 0 && ms < 24 * 60 * 60 * 1000)) return;

		const sessionId = widget.session_id;
		widget._expiryTimer = setTimeout(() => {
			widget._expiryTimer = null;
			// The user may have switched conversations while it ran.
			if (widget.session_id !== sessionId) return;
			this.mark_interaction_expired(widget);
		}, ms);
	},

	/**
	 * Show an interaction card (approval or question) in the chat
	 * @param {Object} widget - Widget instance
	 * @param {Object} data - Interaction data from approval_required event
	 */
	show_interaction_card(widget, data) {
		this.stop_processing_indicator(widget);
		widget.$widget.find(".pao-thinking-indicator").remove();
		widget.$widget.find(".pao-tool-indicator").remove();
		widget.$widget.find(".pao-processing-indicator").hide();

		// Idempotency guard: hydration on page-mount or after socket reconnect
		// can call this with the same tool_id as a live socket event. Don't
		// render a duplicate card.
		const toolId = data.tool_id;
		if (toolId) {
			const existing = widget.$widget
				.find(".pao-interaction-card")
				.filter((_, el) => el.getAttribute("data-tool-id") === String(toolId))
				.not(".pao-interaction-decided");
			if (existing.length) {
				return;
			}
		}

		// HTML-escape once; reused in every card root's data-tool-id attribute.
		const safeToolIdAttr = data.tool_id ? PAOCore.escape_html(data.tool_id) : "";

		// Show text content if any was streamed before the interrupt
		const $streamingMsg = widget.$widget.find(".pao-message-streaming");
		if ($streamingMsg.length) {
			const $content = $streamingMsg.find(".pao-message-text");
			if ($content.data("raw-markdown")) {
				$content.show();
			}
		}

		const interrupts = data.interrupts || [];
		const firstInterrupt = interrupts[0] || {};
		const reason = firstInterrupt.reason || {};
		const interactionType = reason.type || "approval";

		let cardHtml = "";

		if (interactionType === "approval") {
			const esc = (v) => PAOCore.escape_html(v);
			const toolName = data.tool_name || "";
			const titleMap = {
				create_document: __("Create Document"),
				update_document: __("Update Document"),
				delete_document: __("Delete Document"),
				rename_document: __("Rename Document"),
				cancel_document: __("Cancel Document"),
				amend_document: __("Amend Document"),
				create_from_document: __("Create From Document"),
				assign_document: __("Assign Document"),
				add_comment: __("Add Comment"),
				submit_document: __("Submit Document"),
			};
			const title = titleMap[toolName] || toolName.replace(/_/g, " ");
			const action = reason.action || title;
			const input = data.input || {};
			const fmt = (v) => {
				if (v !== null && typeof v === "object") {
					let json = "";
					try {
						json = JSON.stringify(v, null, 2);
					} catch (e) {
						json = String(v);
					}
					if (json.length > 2000) json = json.slice(0, 2000) + "…";
					return `<details class="pao-interaction-nested"><summary>${esc(__("Details"))}</summary><pre>${esc(json)}</pre></details>`;
				}
				return `<b>${esc(v)}</b>`;
			};
			const detailsHtml = Object.entries(input)
				.map(
					([k, v]) =>
						`<span class="pao-interaction-detail">${esc(k.replace(/_/g, " "))}: ${fmt(v)}</span>`
				)
				.join(" · ");

			cardHtml = `
				<div class="pao-interaction-card pao-interaction-approval" data-tool-id="${safeToolIdAttr}">
					<div class="pao-interaction-header">
						<span class="pao-interaction-title">${esc(__("Approval Required"))}: ${esc(action)}</span>
					</div>
					${detailsHtml ? `<div class="pao-interaction-details">${detailsHtml}</div>` : ""}
					<div class="pao-interaction-actions">
						<button class="pao-interaction-btn pao-btn-reject" data-response="rejected">${__(
							"Reject"
						)}</button>
						<button class="pao-interaction-btn pao-btn-approve" data-response="approve">${__(
							"Approve"
						)}</button>
						<button class="pao-interaction-btn pao-btn-trust" data-response="trust">${__(
							"Always Allow"
						)}</button>
					</div>
				</div>`;
		} else if (interactionType === "single_select") {
			const options = reason.options || [];
			const pillsHtml = options
				.map(
					(opt) =>
						`<button class="pao-pill" data-value="${PAOCore.escape_html(
							opt
						)}">${PAOCore.escape_html(opt)}</button>`
				)
				.join("");

			cardHtml = `
				${pao_question_head(safeToolIdAttr, reason, true)}
					<div class="pao-interaction-pills">${pillsHtml}</div>
				</div>`;
		} else if (interactionType === "confirm") {
			cardHtml = `
				${pao_question_head(safeToolIdAttr, reason, true)}
					<div class="pao-interaction-actions">
						<button class="pao-interaction-btn pao-btn-reject" data-response="no">${__("No")}</button>
						<button class="pao-interaction-btn pao-btn-approve" data-response="yes">${__("Yes")}</button>
					</div>
				</div>`;
		} else if (interactionType === "multi_select") {
			const options = reason.options || [];
			const checksHtml = options
				.map(
					(opt) =>
						`<label class="pao-multi-option">
					<input type="checkbox" value="${PAOCore.escape_html(opt)}" />
					<span>${PAOCore.escape_html(opt)}</span>
				</label>`
				)
				.join("");

			cardHtml = `
				${pao_question_head(safeToolIdAttr, reason, false)}
					<div class="pao-interaction-multi">${checksHtml}</div>
					<button class="pao-interaction-btn pao-btn-approve pao-multi-submit" disabled>${__(
						"Submit"
					)}</button>
				</div>`;
		} else if (interactionType === "text_input") {
			cardHtml = `
				${pao_question_head(safeToolIdAttr, reason, false)}
					<div class="pao-interaction-text-input">
						<input type="text" class="pao-text-field" placeholder="${PAOCore.escape_html(
							reason.placeholder || __("Type your answer...")
						)}" />
						<button class="pao-interaction-btn pao-btn-approve pao-text-submit" disabled>${__(
							"Send"
						)}</button>
					</div>
				</div>`;
		}

		const $messages = widget.$widget.find(".pao-messages");
		const $card = $(cardHtml);
		$messages.append($card);
		widget.scroll_to_bottom();

		// Disable input while interaction is pending
		widget.$widget.find(".pao-input-area textarea").prop("disabled", true);
		widget.$widget.find(".pao-send-btn").prop("disabled", true);

		// Register this card in the per-widget pending-interrupts batch. When
		// the model emits N parallel tool_use blocks that need approval, AR
		// streams N separate approval_required events and we render N cards.
		// Strands' resume contract requires a single resume call carrying
		// responses for every pending interrupt — firing one resume per card
		// races against Strands' per-agent threading lock and corrupts the
		// saved AR Message history. Batching here is the same fix used by
		// the Vue SPA in chatStore.submitInterruptDecision.
		if (!widget._pendingInterrupts) widget._pendingInterrupts = [];
		widget._pendingInterrupts.push({
			$card,
			interrupts,
			decision: null,
		});

		// Bind interaction card events (pass interrupts directly, not via DOM attribute)
		this.bind_interaction_events(widget, $card, interrupts);

		// Refresh the "Waiting for N more decisions" hint on any earlier card
		// that's already been decided.
		this._update_batch_hints(widget);

		this.raise_approval_attention(widget, data);
		this._schedule_local_expiry(widget, data.expires_at);
	},

	/**
	 * Make a pending approval impossible to miss.
	 *
	 * A card rendered into a closed widget lands in hidden DOM: the launcher
	 * carries no badge and autofade dims it to ~15% exactly when a decision is
	 * needed. So pop the widget open (same reasoning as the browser-tool
	 * prompt in widget_browser_tools.js), and raise signals that survive the
	 * user closing it again or working in another tab.
	 */
	raise_approval_attention(widget, data) {
		if (!widget.$widget) return;

		// Drives the launcher badge and suppresses autofade.
		widget.$widget.addClass("pao-awaiting-approval");

		if (!widget.is_open && typeof widget.open === "function") {
			try {
				widget.open();
			} catch (e) {
				/* best-effort — badge and toast still stand in */
			}
		}

		const toolName = data && data.tool_name;
		if (frappe.show_alert) {
			frappe.show_alert(
				{
					message: toolName
						? __("Approval needed: {0}", [PAOCore.escape_html(toolName)])
						: __("The assistant needs your approval"),
					indicator: "orange",
				},
				10
			);
		}

		this._start_title_flash();
	},

	/**
	 * Drop every attention signal. Safe to call when none is active.
	 */
	clear_approval_attention(widget) {
		if (widget && widget.$widget) {
			widget.$widget.removeClass("pao-awaiting-approval");
		}
		this._stop_title_flash();
	},

	// Alternates the tab title so a backgrounded tab still shows the ask.
	_start_title_flash() {
		if (this._titleFlashTimer) return;
		this._titleFlashOriginal = document.title;
		let showing = false;
		this._titleFlashTimer = setInterval(() => {
			showing = !showing;
			document.title = showing ? "● " + __("Approval needed") : this._titleFlashOriginal;
		}, 1200);
	},

	_stop_title_flash() {
		if (!this._titleFlashTimer) return;
		clearInterval(this._titleFlashTimer);
		this._titleFlashTimer = null;
		if (this._titleFlashOriginal) document.title = this._titleFlashOriginal;
	},

	// Rendering an interaction card disables the composer; every path that
	// retires a card has to hand it back.
	_release_composer(widget) {
		if (!widget || !widget.$widget) return;
		widget.$widget.find(".pao-input-area textarea").prop("disabled", false);
		widget.sync_send_button();
	},

	/**
	 * Bind click/input events on an interaction card
	 * @param {Object} widget - Widget instance
	 * @param {jQuery} $card - The interaction card element
	 * @param {Array} interrupts - Interrupt objects with id
	 */
	bind_interaction_events(widget, $card, interrupts) {
		const self = this;

		// Approval/confirm buttons
		$card.on("click", ".pao-interaction-btn[data-response]", function () {
			const response = $(this).data("response");
			self.resolve_interaction(widget, $card, interrupts, response);
		});

		// Single select pills
		$card.on("click", ".pao-pill", function () {
			const value = $(this).data("value");
			self.resolve_interaction(widget, $card, interrupts, value);
		});

		// Multi-select checkbox toggle
		$card.on("change", ".pao-multi-option input", function () {
			const checked = $card.find(".pao-multi-option input:checked").length;
			$card
				.find(".pao-multi-submit")
				.prop("disabled", checked === 0)
				.text(checked ? `${__("Submit")} (${checked})` : __("Submit"));
		});

		// Multi-select submit
		$card.on("click", ".pao-multi-submit", function () {
			const selected = [];
			$card.find(".pao-multi-option input:checked").each(function () {
				selected.push($(this).val());
			});
			if (selected.length) {
				self.resolve_interaction(widget, $card, interrupts, selected);
			}
		});

		// Text input
		$card.on("input", ".pao-text-field", function () {
			$card.find(".pao-text-submit").prop("disabled", !$(this).val().trim());
		});

		$card.on("click", ".pao-text-submit", function () {
			const val = $card.find(".pao-text-field").val().trim();
			if (val) self.resolve_interaction(widget, $card, interrupts, val);
		});

		$card.on("keydown", ".pao-text-field", function (e) {
			if (e.key === "Enter") {
				const val = $(this).val().trim();
				if (val) self.resolve_interaction(widget, $card, interrupts, val);
			}
		});
	},

	/**
	 * Record a user's decision on one HITL card, then flush all pending
	 * decisions in a single resume_interrupt call once every card has been
	 * decided. See the comment in show_interaction_card for why batching
	 * is required.
	 *
	 * @param {Object} widget - Widget instance
	 * @param {jQuery} $card - The interaction card element
	 * @param {Array} interrupts - Interrupt objects with id (this card's slice)
	 * @param {*} response - User's response value
	 */
	resolve_interaction(widget, $card, interrupts, response) {
		const entry = (widget._pendingInterrupts || []).find((e) => e.$card.is($card));
		if (!entry || entry.decision || widget._isSubmittingInterrupts) return;

		const displayResponse = Array.isArray(response) ? response.join(", ") : String(response);
		const isPositive = !["rejected", "no"].includes(response);
		entry.decision = { response, displayResponse, isPositive };

		// Visually mark this card as decided but keep it in place — the
		// resolved indicator only replaces it after the network call succeeds.
		$card.addClass("pao-interaction-decided");
		$card
			.find(
				".pao-interaction-actions, .pao-interaction-pills, .pao-interaction-multi, .pao-interaction-text-input"
			)
			.find("button, input")
			.prop("disabled", true);

		this._update_batch_hints(widget);

		// Flush only when every visible card has a decision.
		const allDecided = widget._pendingInterrupts.every((e) => e.decision);
		if (allDecided) {
			this._flush_pending_interrupts(widget);
		}
	},

	/**
	 * Render the "Waiting for N more decisions" hint on every decided card
	 * whenever a new card is added or another decision lands. Called from
	 * both show_interaction_card and resolve_interaction.
	 */
	_update_batch_hints(widget) {
		const pending = widget._pendingInterrupts || [];
		const undecided = pending.filter((e) => !e.decision).length;
		const hint =
			undecided === 0
				? ""
				: undecided === 1
				? __("Waiting for 1 more decision")
				: __("Waiting for {0} more decisions", [undecided]);

		pending.forEach((entry) => {
			if (!entry.decision) return;
			let $banner = entry.$card.find(".pao-interaction-batch-hint");
			if (!$banner.length) {
				$banner = $('<div class="pao-interaction-batch-hint"></div>');
				entry.$card.append($banner);
			}
			const label = entry.decision.isPositive ? __("Decided") : __("Decided");
			$banner.text(hint ? `${label} · ${hint}` : __("Submitting…"));
		});
	},

	/**
	 * Fire one resume_interrupt covering every decided card's response.
	 * On success, replace each card with its resolved indicator and clear
	 * the pending batch. On error, revert decisions so the user can retry.
	 */
	_flush_pending_interrupts(widget) {
		const pending = widget._pendingInterrupts || [];
		if (!pending.length || widget._isSubmittingInterrupts) return;

		const interruptResponses = [];
		pending.forEach((entry) => {
			entry.interrupts.forEach((i) => {
				interruptResponses.push({ interruptId: i.id, response: entry.decision.response });
			});
		});

		widget._isSubmittingInterrupts = true;
		pending.forEach((entry) => {
			const $banner = entry.$card.find(".pao-interaction-batch-hint");
			$banner.text(__("Submitting…"));
		});

		const self = this;
		frappe.call({
			silent: true,
			method: "pibiassistant.pibiassistant_chat.api.chat.messages.resume_interrupt",
			args: {
				session_id: widget.session_id,
				interrupt_response: JSON.stringify(interruptResponses),
				message_id: widget.current_message_id || null,
				// Omitting this defaults AR to "spa", which flips client_type
				// mid-turn and rebuilds the agent holding the pause.
				client_type: "widget",
			},
			callback: () => {
				// Replace each card with its resolved indicator.
				pending.forEach((entry) => {
					const icon = entry.decision.isPositive ? '<i class="ph ph-check" aria-hidden="true"></i>' : '<i class="ph ph-x" aria-hidden="true"></i>';
					entry.$card.replaceWith(
						`<div class="pao-interaction-resolved">${icon} ${PAOCore.escape_html(
							entry.decision.displayResponse
						)}</div>`
					);
				});
				widget._pendingInterrupts = [];
				widget._isSubmittingInterrupts = false;
				// The turn is live again — re-arm the watchdog the interrupt
				// cleared, or a drop after resume hangs the spinner forever.
				self.start_stream_timeout(widget);
				// Re-enable input — streaming resumes via Socket.IO.
				self._release_composer(widget);
				self.clear_approval_attention(widget);
			},
			error: (err) => {
				PAOLogger.error("Failed to resume interrupt:", err);
				// Revert: re-enable buttons on each card so the user can try again.
				pending.forEach((entry) => {
					entry.decision = null;
					entry.$card.removeClass("pao-interaction-decided");
					entry.$card.find("button, input").prop("disabled", false);
					entry.$card.find(".pao-interaction-batch-hint").remove();
				});
				widget._isSubmittingInterrupts = false;
			},
		});
	},

	// --- Streaming Messages ---

	/**
	 * Add a placeholder message with processing indicator
	 * @param {Object} widget - Widget instance
	 * @returns {jQuery} Message element
	 */
	add_streaming_message(widget) {
		const $messages = widget.$widget.find(".pao-messages");

		const $message = $(`
			<div class="pao-message pao-message-assistant pao-message-streaming">
				<div class="pao-message-avatar">
					${PAOCore.get_assistant_avatar()}
				</div>
				<div class="pao-message-content">
					<div class="pao-processing-indicator">
						<div class="pao-processing-status">
							<span class="pao-processing-dot"></span>
							<span class="pao-processing-text">${__("Processing your request...")}</span>
						</div>
						<div class="pao-processing-tip"></div>
					</div>
					<div class="pao-message-text" style="display: none;">
						<span class="pao-streaming-cursor">▋</span>
					</div>
				</div>
			</div>
		`);

		$messages.append($message);
		widget.scroll_to_bottom();

		this.start_processing_indicator(widget);
		this.set_robot_mood(widget, "thinking");

		return $message;
	},

	/**
	 * Set the mood data attribute on every robot avatar inside the widget.
	 * Mirrors the SPA's robotMoodStore behaviour without a real reactive
	 * store — the widget only needs idle/thinking/delighted/concerned
	 * transitions, which CSS handles via [data-mood].
	 *
	 * @param {Object} widget - Widget instance
	 * @param {string} mood - One of idle|attentive|thinking|delighted|concerned|excited|sleepy
	 */
	set_robot_mood(widget, mood) {
		const $robots = widget.$widget.find(".pao-robot");
		if (mood && mood !== "idle") {
			$robots.attr("data-mood", mood);
		} else {
			$robots.removeAttr("data-mood");
		}
	},

	/**
	 * Briefly set a transient mood, then revert to idle.
	 * Used for delighted/excited pulses after a successful completion.
	 *
	 * @param {Object} widget - Widget instance
	 * @param {string} mood - Transient mood
	 * @param {number} ms - Hold duration
	 */
	pulse_robot_mood(widget, mood, ms = 1500) {
		this.set_robot_mood(widget, mood);
		setTimeout(() => {
			// Only reset if the current mood is still the one we set —
			// avoids overwriting a newer mood (e.g. user fired off
			// another message during the pulse window).
			const $robots = widget.$widget.find(".pao-robot");
			if ($robots.attr("data-mood") === mood) {
				this.set_robot_mood(widget, "idle");
			}
		}, ms);
	},

	/**
	 * Update the streaming message with new chunk
	 * @param {Object} widget - Widget instance
	 * @param {string} chunk - New text chunk
	 */
	update_streaming_message(widget, chunk) {
		const $streamingMsg = widget.$widget.find(".pao-message-streaming");

		if ($streamingMsg.length > 0) {
			const $content = $streamingMsg.find(".pao-message-text");
			const $processingIndicator = $streamingMsg.find(".pao-processing-indicator");

			// On first chunk, hide processing indicator and show text container
			if ($processingIndicator.is(":visible")) {
				$processingIndicator.hide();
				$content.show();
				this.stop_processing_indicator(widget);
			}

			let rawText = $content.data("raw-markdown") || "";

			// Smart spacing: add paragraph break between distinct thoughts
			// BUT NOT inside markdown tables
			if (rawText.length > 0 && chunk.trim().length > 0) {
				const lines = rawText.split("\n");
				let inTable = false;

				for (let i = lines.length - 1; i >= Math.max(0, lines.length - 5); i--) {
					const line = lines[i].trim();
					if (line.startsWith("|") && line.endsWith("|")) {
						inTable = true;
						break;
					}
					if (line === "") {
						break;
					}
				}

				const chunkStartsTable =
					chunk.trim().startsWith("|") && chunk.trim().includes("|");

				if (!inTable && !chunkStartsTable) {
					const lastChar = rawText.trim().slice(-1);
					const firstChar = chunk.trim()[0];

					if (
						[".", "!", "?"].includes(lastChar) &&
						(firstChar === firstChar.toUpperCase() || chunk.startsWith("\n"))
					) {
						rawText += "\n\n";
					}
				}
			}

			rawText += chunk;
			$content.data("raw-markdown", rawText);
			this.schedule_stream_render(widget);
		}
	},

	/** Reparse the answer at most once per frame; chunks only append to raw-markdown. */
	schedule_stream_render(widget) {
		if (widget._streamRaf) return;
		const raf = window.requestAnimationFrame || ((fn) => setTimeout(fn, 16));
		widget._streamRaf = raf(() => {
			widget._streamRaf = null;
			const $content = widget.$widget.find(".pao-message-streaming .pao-message-text");
			const rawText = $content.data("raw-markdown");
			if (!$content.length || rawText == null) return;
			$content.html(
				PAOCore.format_message(rawText, "assistant") +
					'<span class="pao-streaming-cursor">▋</span>'
			);
			widget.scroll_to_bottom();
		});
	},

	cancel_stream_render(widget) {
		if (!widget._streamRaf) return;
		(window.cancelAnimationFrame || clearTimeout)(widget._streamRaf);
		widget._streamRaf = null;
	},

	/**
	 * Finalize the streaming message
	 * @param {Object} widget - Widget instance
	 * @param {string} fullResponse - Complete response text
	 * @param {number} tokensUsed - Tokens consumed
	 * @param {number} quotaRemaining - Remaining quota
	 */
	/** Small footer under an answer: model, tokens in/out, speed and time. */
	build_message_meta(meta) {
		const parts = [];
		if (meta && meta.model_id) parts.push(PAOCore.escape_html(meta.model_id));
		const tin = meta && meta.prompt_tokens;
		const tout = meta && meta.completion_tokens;
		if (tin != null || tout != null) {
			parts.push(`<span title="${__("Input tokens")}">↑${tin != null ? tin : "–"}</span> <span title="${__("Output tokens")}">↓${tout != null ? tout : "–"}</span>`);
		}
		if (tout && meta.duration_ms > 0) {
			parts.push(`<span title="${__("Output speed")}">${(tout / (meta.duration_ms / 1000)).toFixed(1)} ${__("tokens/s")}</span>`);
		}
		parts.push(PAOCore.format_time(new Date()));
		return `<div class="pao-message-time pao-message-meta">${parts.join(" · ")}</div>`;
	},

	finalize_streaming_message(widget, fullResponse, tokensUsed, quotaRemaining, meta) {
		this.cancel_stream_render(widget);
		widget._isStreaming = false;
		widget._lateAbort = null;
		this.stop_processing_indicator(widget);
		this.pulse_robot_mood(widget, "delighted");

		const $streamingMsg = widget.$widget.find(".pao-message-streaming");

		// Remove any remaining indicators
		widget.$widget.find(".pao-thinking-indicator").remove();
		widget.$widget.find(".pao-tool-indicator").remove();

		if ($streamingMsg.length > 0) {
			const $content = $streamingMsg.find(".pao-message-text");

			// Ensure text container is visible and processing indicator is hidden
			$streamingMsg.find(".pao-processing-indicator").hide();
			$content.show();

			let finalText = $content.data("raw-markdown") || fullResponse;
			$content.html(PAOCore.format_message(finalText, "assistant"));
			$content.removeData("raw-markdown");

			$streamingMsg.find(".pao-message-content").append($(this.build_message_meta(meta)));

			$streamingMsg.removeClass("pao-message-streaming");

			widget.messages.push(widget._toWidgetMessage({ role: "assistant", content: fullResponse }));
		}

		// Re-enable send button
		widget.sync_send_button();
	},

	/**
	 * Close the turn the user stopped: keep what was already streamed, drop the
	 * server's "(Stopped by user)" marker (the footer says it) and free the composer.
	 */
	finalize_aborted(widget, data) {
		this.cancel_stream_render(widget);
		clearTimeout(widget._stopFallback);
		widget._stopping = false;
		this.clear_timeouts();
		this.stop_processing_indicator(widget);
		widget.$widget.find(".pao-thinking-indicator, .pao-tool-indicator").remove();

		const $streamingMsg = widget.$widget.find(".pao-message-streaming");
		const $content = $streamingMsg.find(".pao-message-text");
		const text = String($content.data("raw-markdown") || (data && data.partial_response) || "")
			.replace(/\s*_\(Stopped by user\)_\s*$/, "")
			.trim();
		if ($streamingMsg.length) {
			$streamingMsg.find(".pao-processing-indicator").hide();
			$content.removeData("raw-markdown").show();
			$content.html(text ? PAOCore.format_message(text, "assistant") : "");
			$streamingMsg
				.removeClass("pao-message-streaming")
				.addClass("pao-message-aborted")
				.find(".pao-message-content")
				.append(
					`<div class="pao-message-time pao-message-meta pao-message-stopped">${__("Response stopped.")}</div>`
				);
			if (text) widget.messages.push({ role: "assistant", content: text });
		}
		widget._isStreaming = false;
		widget.$widget.find(".pao-input-area textarea").prop("disabled", false);
		widget.sync_send_button();
		widget.$widget.find(".pao-input").trigger("focus");
	},

	/**
	 * Handle streaming error
	 * @param {Object} widget - Widget instance
	 * @param {Object} data - Error data
	 */
	handle_stream_error(widget, data) {
		this.cancel_stream_render(widget);
		widget._isStreaming = false;
		this.stop_processing_indicator(widget);
		this.pulse_robot_mood(widget, "concerned", 2500);

		const $streamingMsg = widget.$widget.find(".pao-message-streaming");
		$streamingMsg.remove();

		widget.$widget.find(".pao-thinking-indicator").remove();
		widget.$widget.find(".pao-tool-indicator").remove();
		widget.sync_send_button();

		if (data.action_required === "re_authorize") {
			window.PAOPanel.open({
				title: __("Re-authorization Required"),
				html: `<p>${window.PAOPanel.escape(
					__("Your AIDA session has expired. Please contact your administrator to re-authorize the connection.")
				)}</p>`,
				actions: [
					{ label: __("Close"), kind: "outline" },
					{
						label: __("Go to Settings"),
						kind: "primary",
						onClick: () => frappe.set_route("Form", "PA Chat Settings"),
					},
				],
			});
		} else {
			widget.add_message_to_ui("assistant", __("Error: {0}", [data.error || __("Unknown error")]), true);
		}
	},

	// --- Thinking Indicator ---

	/**
	 * Show thinking/reasoning indicator
	 * @param {Object} widget - Widget instance
	 * @param {string} content - Thinking content
	 */
	show_thinking_indicator(widget, content) {
		// When a plan is active, fold thinking into the running task's sub-slot.
		if (widget._activePlan) {
			const $slot = this._running_subactivity_slot(widget);
			if ($slot && $slot.length) {
				$slot.html('<span class="pao-plan-sub-spinner is-thinking"><i class="ph ph-chat-dots" aria-hidden="true"></i></span> ' + window.PAOPlanStrip._escape(__("Thinking...")));
				return;
			}
		}
		const $streamingMsg = widget.$widget.find(".pao-message-streaming");
		if ($streamingMsg.length > 0) {
			let $indicator = $streamingMsg.find(".pao-thinking-indicator");
			if ($indicator.length === 0) {
				$indicator = $(`
					<div class="pao-thinking-indicator">
						<span class="pao-thinking-spinner"><i class="ph ph-chat-dots" aria-hidden="true"></i></span>
						<span class="pao-thinking-text">${__("Thinking...")}</span>
					</div>
				`);
				$streamingMsg.find(".pao-message-content").prepend($indicator);
			}
		}
	},

	/**
	 * Hide thinking indicator
	 * @param {Object} widget - Widget instance
	 */
	hide_thinking_indicator(widget) {
		// Plan-active: thinking lives in the running task's sub-slot; clear it.
		if (widget._activePlan) {
			widget.$widget.find(".pao-plan-subactivity").empty();
			return;
		}
		widget.$widget.find(".pao-thinking-indicator").remove();
	},

	// --- Tool Indicators ---

	/**
	 * Show tool execution indicator
	 * @param {Object} widget - Widget instance
	 * @param {string} tool_name - Name of the tool
	 * @param {string} tool_id - Optional tool ID for tracking
	 */
	show_tool_indicator(widget, tool_name, tool_id = null) {
		// When a plan is active, fold the tool indicator into the running task's sub-slot.
		if (widget._activePlan) {
			const $slot = this._running_subactivity_slot(widget);
			if ($slot && $slot.length) {
				$slot.attr("data-active-tool-id", tool_id || "");
				$slot.html('<span class="pao-plan-sub-spinner is-executing"><i class="ph ph-gear" aria-hidden="true"></i></span> ' + window.PAOPlanStrip._escape(`${__("Executing")}: ${tool_name}`));
				return;
			}
		}
		const $streamingMsg = widget.$widget.find(".pao-message-streaming");
		if ($streamingMsg.length > 0) {
			let $indicator = $streamingMsg.find(".pao-tool-indicator");
			if ($indicator.length === 0) {
				$indicator = $(`
					<div class="pao-tool-indicator">
						<span class="pao-tool-spinner"><i class="ph ph-gear" aria-hidden="true"></i></span>
						<span class="pao-tool-name"></span>
					</div>
				`);
				$streamingMsg.find(".pao-message-content").append($indicator);
			}
			if (tool_id) {
				$indicator.attr("data-tool-id", tool_id);
			}
			$indicator.find(".pao-tool-name").text(`${__("Executing")}: ${tool_name}`);
		}
	},

	/**
	 * Hide tool execution indicator
	 * @param {Object} widget - Widget instance
	 * @param {string} tool_id - Optional tool ID to target specific indicator
	 * @param {boolean} cancelled - Whether the tool was cancelled
	 */
	hide_tool_indicator(widget, tool_id = null, cancelled = false) {
		// Plan-active: tool activity lives in the running task's sub-slot; clear it.
		if (widget._activePlan) {
			widget.$widget.find(".pao-plan-subactivity").empty();
			return;
		}
		if (tool_id) {
			widget.$widget.find(`.pao-tool-indicator[data-tool-id="${tool_id}"]`).remove();
		} else {
			widget.$widget.find(".pao-tool-indicator").remove();
		}
	},

	// --- Task plan strip ---

	/** Render/replace the live plan strip in the active streaming bubble. */
	render_plan(widget, plan) {
		const $streamingMsg = widget.$widget.find(".pao-message-streaming");
		if ($streamingMsg.length === 0) return;
		if (!plan || !plan.tasks || plan.tasks.length === 0) return;
		if (!window.PAOPlanStrip) return;

		// A plan is now active for this turn — Task 4's folding reads this.
		widget._activePlan = plan;

		// The generic spinner is redundant once we show real tasks.
		$streamingMsg.find(".pao-processing-indicator").hide();

		const $content = $streamingMsg.find(".pao-message-content");
		const html = window.PAOPlanStrip.stripHtml(plan);
		const $strip = $content.find(".pao-plan-strip");
		if ($strip.length) {
			$strip.replaceWith(html);
		} else {
			// Plan leads the bubble, above thinking/text.
			$content.prepend(html);
		}
	},

	/** Collapse the live strip to a one-line summary at plan_complete. */
	collapse_plan(widget, plan) {
		const $streamingMsg = widget.$widget.find(".pao-message-streaming");
		const finalPlan = plan || widget._activePlan;
		widget._activePlan = null;
		if (!finalPlan || !finalPlan.tasks || finalPlan.tasks.length === 0) return;
		if (!window.PAOPlanStrip) return;
		const $strip = $streamingMsg.find(".pao-plan-strip");
		if ($strip.length) {
			$strip.replaceWith(window.PAOPlanStrip.collapsedHtml(finalPlan));
		}
	},

	/** Find the sub-activity slot under the currently-running task, if any. */
	_running_subactivity_slot(widget) {
		const $streamingMsg = widget.$widget.find(".pao-message-streaming");
		return $streamingMsg.find(".pao-plan-row.pao-plan-running .pao-plan-subactivity").first();
	},
};
