import { baseCall } from "../_core";

// SPA Initialization (combined endpoint — replaces 6 sequential calls)
export const init = {
	initialize: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.initialize_spa"),
};
