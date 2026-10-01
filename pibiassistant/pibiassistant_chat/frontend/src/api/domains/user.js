import { baseCall, getCall } from "../_core";

export const user = {
	getCurrent: () =>
		getCall("pibiassistant.pibiassistant_chat.api.can_use_pao"),

	// Per-user registration and MCP server management
	getAuthStatus: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_user_auth_status"),

	connectAIDAServer: () =>
		baseCall("pibiassistant.pibiassistant_chat.api.connect_aida_mcp_server"),

	getMCPServers: () =>
		getCall("pibiassistant.pibiassistant_chat.api.get_user_mcp_servers"),

	reconnectServer: (serverName = "Main Frappe Site") =>
		baseCall("pibiassistant.pibiassistant_chat.api.reconnect_mcp_server", {
			server_name: serverName,
		}),

	disconnectServer: (serverName = "Main Frappe Site") =>
		baseCall("pibiassistant.pibiassistant_chat.api.disconnect_mcp_server", {
			server_name: serverName,
		}),

	listTools: () =>
		getCall("pibiassistant.pibiassistant_chat.api.list_user_tools"),
};
