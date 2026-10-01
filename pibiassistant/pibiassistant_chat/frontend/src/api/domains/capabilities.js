import { getCall } from "../_core";

export const capabilities = {
	get: () => getCall("pibiassistant.pibiassistant_chat.api.get_capabilities"),
};
