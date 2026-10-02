// pibiAssistant - AIDA Widget Onboarding Module
// Simplified: all onboarding happens in the SPA. Widget just shows a redirect screen.

/**
 * Widget Onboarding Module
 * Shows a "Complete setup" screen that redirects to the SPA for all onboarding.
 * The widget only shows the chat interface when setup + consent are fully complete.
 */
window.PAOWidgetOnboarding = {
	/**
	 * Show setup-required screen with a button to open the SPA.
	 * Replaces all previous inline onboarding (registration, user connect, onboarding chat).
	 *
	 * @param {Object} widget - Widget instance
	 * @param {'not_registered'|'needs_setup'|'needs_consent'} context - Why setup is needed
	 */
	show_setup_required(widget, context) {
		const $messages = widget.$widget.find(".pao-messages");
		const $inputArea = widget.$widget.find(".pao-input-area");

		// Hide chat elements
		$inputArea.hide();

		const messages = {
			not_registered: {
				title: __("Welcome to AIDA!"),
				subtitle: __("Your intelligent assistant from pibiCo"),
				admin_action: __("Open AIDA"),
				admin_hint: __("Opens the full AIDA assistant."),
				no_admin: __("Please ask your administrator to enable AIDA for this site."),
			},
			needs_setup: {
				title: __("Welcome to AIDA!"),
				subtitle: __("Your intelligent assistant from pibiCo"),
				admin_action: __("Open AIDA"),
				admin_hint: __("Opens the full AIDA assistant."),
			},
			needs_consent: {
				title: __("Welcome to AIDA!"),
				subtitle: __("Open AIDA to start chatting."),
				admin_action: __("Open AIDA"),
				admin_hint: __("Takes less than a minute."),
			},
		};

		const msg = messages[context] || messages.needs_consent;
		// Connecting the site is the only step here that belongs to an admin.
		// The other two belong to the person in front of us: needs_setup is
		// reached only when can_use is true, and can_use IS the membership
		// check, so they already hold a seat; consent is their own to give.
		// Gating those on the System Manager role told real members to go ask
		// their administrator while the SPA offered them the connect screen.
		const showButton = widget.is_admin || context !== "not_registered";

		const html = `
			<div class="pao-onboarding">
				<div class="pao-onboarding-header">
					<img class="aida-avatar" src="/assets/pibiassistant/chat/widget/aida-icon.svg" alt="AIDA" width="80" height="80" style="border-radius:50%;margin-bottom:10px;">
					<h2>${msg.title}</h2>
					<p>${msg.subtitle}</p>
				</div>

				${
					showButton
						? `
					<div class="pao-setup-section">
						<button class="btn btn-primary btn-lg pao-setup-btn">
							${msg.admin_action}
						</button>
						<p class="pao-setup-hint">${msg.admin_hint}</p>
					</div>
				`
						: `
					<div class="pao-contact-admin">
						<p><i class="ph ph-warning" aria-hidden="true"></i><span>${msg.no_admin}</span></p>
					</div>
				`
				}
			</div>
		`;

		$messages.html(html);

		if (showButton) {
			widget.$widget.find(".pao-setup-btn").on("click", () => {
				this.open_spa();
			});
		}
	},

	/**
	 * Open the SPA for onboarding.
	 */
	open_spa() {
		window.open("/aida", "_blank");
	},

	/**
	 * Check if the current user has completed per-user AR registration.
	 * @param {Object} widget - Widget instance
	 */
	async check_user_auth(widget) {
		try {
			const response = await frappe.call({
				silent: true,
				method: "pibiassistant.pibiassistant_chat.api.auth.get_user_auth_status",
				type: "GET",
			});
			const result = response.message;
			if (result && result.success && result.ready) {
				widget.user_setup_complete = true;
			} else {
				widget.user_setup_complete = false;
			}
		} catch (error) {
			PAOLogger.warn("Failed to check user auth status:", error);
			widget.user_setup_complete = false;
		}
	},

	/**
	 * Transition to the normal chat interface after all setup is complete.
	 * @param {Object} widget - Widget instance
	 */
	show_chat_interface(widget) {
		const $messages = widget.$widget.find(".pao-messages");
		const $inputArea = widget.$widget.find(".pao-input-area");

		$messages.empty();

		$messages.html(PAOWidgetUI.get_welcome_message_html());

		$inputArea.show();

		widget.$widget.find(".pao-input").focus();
		widget.update_context();
	},
};
