import { getCall } from "../_core";

export const models = {
	getAvailable: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_available_models"),
	// Note: setPreferred removed - model selection is now per-request via localStorage
};
