import { baseCall, getCall } from "../_core";

export const sharedKnowledge = {
	get: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_shared_knowledge"),

	update: (content) =>
		baseCall("pibiassistant.pibiassistant_chat.api.update_shared_knowledge", {
			content,
		}),

	shareMemory: (memoryId) =>
		baseCall(
			"pibiassistant.pibiassistant_chat.api.share_memory_to_knowledge",
			{
				memory_id: memoryId,
			}
		),
};
