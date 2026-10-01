import { baseCall, getCall } from "../_core";

export const templates = {
	getAll: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_prompt_templates"),

	updatePinned: (pinnedTemplates) =>
		baseCall("pibiassistant.pibiassistant_chat.api.update_pinned_templates", {
			pinned_templates: JSON.stringify(pinnedTemplates),
		}),

	getRendered: (promptName, args = {}) =>
		getCall("pibiassistant.pibiassistant_chat.api.get_rendered_prompt", {
			prompt_name: promptName,
			arguments: JSON.stringify(args),
		}),
};
