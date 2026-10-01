import { baseCall, getCall } from "../_core";

export const registration = {
	getTerms: () => getCall("pibiassistant.pibiassistant_chat.api.get_ar_terms"),

	validatePartnerCode: (code) =>
		baseCall("pibiassistant.pibiassistant_chat.api.validate_partner_code", {
			referral_code: code,
		}),

	// No acceptedBy: the tenant owner is derived from the session on the
	// server. Sending one would be a claim, not a fact.
	register: (ownerEmail, termsVersion, referralCode = null, promotionToken = null) =>
		baseCall("pibiassistant.pibiassistant_chat.api.register_with_ar", {
			owner_email: ownerEmail,
			terms_version: termsVersion,
			referral_code: referralCode,
			promotion_token: promotionToken,
		}),

	getState: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.get_registration_state"),

	acceptUpdatedTerms: (termsVersion) =>
		baseCall("pibiassistant.pibiassistant_chat.api.accept_updated_terms", {
			terms_version: termsVersion,
		}),

	completeEmailVerification: (verificationToken) =>
		baseCall(
			"pibiassistant.pibiassistant_chat.api.complete_email_verification",
			{
				verification_token: verificationToken,
			}
		),

	requestSiteRebind: (newSiteUrl) =>
		baseCall("pibiassistant.pibiassistant_chat.api.request_site_rebind", {
			new_site_url: newSiteUrl,
		}),

	pollForRotatedSecret: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.poll_for_rotated_secret"),

	runDiagnostics: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.run_diagnostics"),
};
