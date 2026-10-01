import { getCall } from "../_core";

export const analytics = {
	getData: (days = 30) =>
		getCall("pibiassistant.pibiassistant_chat.api.get_analytics_data", {
			days,
		}),

	getConversations: (days = 30, limit = 50, offset = 0) =>
		getCall(
			"pibiassistant.pibiassistant_chat.api.get_conversation_analytics",
			{
				days,
				limit,
				offset,
			}
		),

	getMessageCredits: (conversationId) =>
		getCall("pibiassistant.pibiassistant_chat.api.get_message_credits", {
			conversation_id: conversationId,
		}),
};
