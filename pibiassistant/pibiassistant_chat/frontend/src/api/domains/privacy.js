import { baseCall, getCall } from "../_core";

export const privacy = {
	exportData: () =>
		getCall("pibiassistant.pibiassistant_chat.api.privacy.export_my_data"),

	eraseData: (password) =>
		baseCall("pibiassistant.pibiassistant_chat.api.privacy.erase_my_data", {
			password,
		}),

	restrictProcessing: (restrict = true) =>
		baseCall(
			"pibiassistant.pibiassistant_chat.api.privacy.restrict_my_processing",
			{
				restrict,
			}
		),

	updateConsent: (consentType, granted = true) =>
		baseCall(
			"pibiassistant.pibiassistant_chat.api.privacy.update_my_consent",
			{
				consent_type: consentType,
				granted,
			}
		),

	getConfig: () =>
		getCall(
			"pibiassistant.pibiassistant_chat.api.privacy.get_privacy_config"
		),

	updateConfig: (config) =>
		baseCall(
			"pibiassistant.pibiassistant_chat.api.privacy.update_privacy_config",
			{
				config: JSON.stringify(config),
			}
		),

	saveInitialConsent: (memoryConsent) =>
		baseCall(
			"pibiassistant.pibiassistant_chat.api.privacy.save_initial_consent",
			{
				memory_consent: memoryConsent,
			}
		),
};
