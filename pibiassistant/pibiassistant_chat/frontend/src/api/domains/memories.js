import { baseCall, getCall } from "../_core";

export const memories = {
	list: (memoryType = null, limit = 50, offset = 0) =>
		getCall("pibiassistant.pibiassistant_chat.api.list_memories", {
			memory_type: memoryType,
			limit,
			offset,
		}),

	delete: (memoryId) =>
		baseCall("pibiassistant.pibiassistant_chat.api.delete_memory", {
			memory_id: memoryId,
		}),

	update: (memoryId, content) =>
		baseCall("pibiassistant.pibiassistant_chat.api.update_memory", {
			memory_id: memoryId,
			content,
		}),

	deleteAll: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.delete_all_memories"),

	getStats: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_memory_stats"),

	getSummary: (force = false) => {
		const params = {};
		if (force) params.force = true;
		return getCall(
			"pibiassistant.pibiassistant_chat.api.memories.get_memory_summary",
			params
		);
	},
};
