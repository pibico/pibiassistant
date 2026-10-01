import { baseCall, getCall } from "../_core";

export const profile = {
	get: () => getCall("pibiassistant.pibiassistant_chat.api.get_profile"),

	update: (fields) =>
		baseCall("pibiassistant.pibiassistant_chat.api.update_profile", fields),
};
