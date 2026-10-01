import { baseCall, getCall } from "../_core";

export const tools = {
	listAvailable: () =>
		getCall(
			"pibiassistant.pibiassistant_chat.api.tools.list_available_tools"
		),

	listPreferences: () =>
		getCall(
			"pibiassistant.pibiassistant_chat.api.tools.list_tool_preferences"
		),

	setPreference: (toolName, preference) =>
		baseCall(
			"pibiassistant.pibiassistant_chat.api.tools.set_tool_preference",
			{
				tool_name: toolName,
				preference,
			}
		),
};
