import { getCall } from "../_core";

export const suggestions = {
	get: (context = {}) =>
		getCall("pibiassistant.pibiassistant_chat.api.get_suggested_prompts", {
			context: JSON.stringify(context),
		}),
};
