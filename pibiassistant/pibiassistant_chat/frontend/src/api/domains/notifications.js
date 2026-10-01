import { baseCall, getCall } from "../_core";

export const notifications = {
	get: () =>
		getCall(
			"pibiassistant.pibiassistant_chat.api.notifications.get_notifications"
		),

	dismiss: (notificationId) =>
		baseCall(
			"pibiassistant.pibiassistant_chat.api.notifications.dismiss_notification",
			{
				notification_id: notificationId,
			}
		),
};
