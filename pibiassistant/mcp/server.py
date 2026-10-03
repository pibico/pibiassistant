# pibiAssistant - AI Assistant integration for Frappe Framework
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Custom MCP Server Implementation

A streamlined MCP server that fixes serialization issues and provides
full control over the implementation. Based on the MCP specification
with Frappe-specific optimizations.

Key improvements over frappe-mcp:
- Proper JSON serialization with `default=str` (handles datetime, Decimal, etc.)
- No Pydantic dependency (simpler, faster)
- Tracebacks stay in the server log, clients get short messages
- Optional Bearer token authentication
- Frappe-native integration
"""

import json
import traceback
from collections import OrderedDict
from typing import Any, Dict, Optional

from werkzeug.wrappers import Request, Response

from pibiassistant.utils.json_safe import dumps_strict
from pibiassistant.utils.result_limits import fit_result

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

SERVER_INSTRUCTIONS = (
    "ERPNext/Frappe assistant. Tools run with the permissions of the user who authorised this connection. "
    "Use get_doctype_info before creating or updating documents, search or search_documents to resolve names, "
    "list_documents/aggregate_documents for data and totals, and prefer get_document_pdf for the printable "
    "version of a document. Writes (create, update, cancel, rename, email...) change real business data: "
    "state what you are about to change. Results can be large; narrow filters or aggregate instead. Skills "
    "(get_skill, pa://skills/...) may bundle references, templates and scripts (get_skill_file or "
    "pa://skills/{skill_id}/{path}): this server never runs scripts or fills templates, so write deliverables as Markdown."
)

# Tool results above this many characters are trimmed (rows dropped, said clearly) so one call cannot flood a client.
DEFAULT_MAX_RESULT_CHARS = 200_000
# structuredContent duplicates the text block, so it is skipped for big payloads.
MAX_STRUCTURED_CHARS = 50_000
# ChatGPT connectors and deep research read these two tools' text as the bare {"results"} / document object.
BARE_RESULT_TOOLS = {"search": "results", "fetch": "text"}


class InvalidParams(Exception):
    """Raised by handlers for bad request params; mapped to JSON-RPC -32602."""



def _max_result_chars() -> int:
    import frappe

    try:
        value = int(frappe.conf.get("mcp_max_result_chars") or DEFAULT_MAX_RESULT_CHARS)
    except Exception:  # no site bound (threads in tests) or a bad value: use the default
        value = DEFAULT_MAX_RESULT_CHARS
    return max(2_000, value)


class MCPServer:
    """
    Lightweight MCP server for Frappe.

    This class implements the Model Context Protocol (MCP) specification
    for tool calling with StreamableHTTP transport.

    Example:
        ```python
        from pibiassistant.mcp.server import MCPServer
        from pibiassistant.mcp.tool_adapter import register_base_tool
        from pibiassistant.plugins.core.tools.list_documents import DocumentList

        mcp = MCPServer("my-server")

        @mcp.register()
        def handle_mcp():
            # Import and register BaseTool instances
            register_base_tool(mcp, DocumentList())
        ```

    Note:
        Tools are implemented as BaseTool subclasses and registered using
        the tool_adapter. The @mcp.tool decorator pattern is not supported.
    """

    def __init__(self, name: str = "pibiassistant", name_resolver=None):
        """
        Initialize MCP server.

        Args:
            name: Server name for identification
            name_resolver: Optional callable returning the live server name per request
        """
        self._name = name
        self._name_resolver = name_resolver
        self._tool_registry = OrderedDict()
        self._entry_fn = None

    @property
    def name(self) -> str:
        if self._name_resolver:
            try:
                return self._name_resolver() or self._name
            except Exception:
                pass
        return self._name

    def register(
        self,
        allow_guest: bool = False,
        xss_safe: bool = True,
        methods: list = None,
    ):
        """
        Decorator to register MCP endpoint with Frappe.

        This creates a whitelisted Frappe endpoint that handles MCP requests.

        Args:
            allow_guest: If True, allows unauthenticated access
            xss_safe: If True, response will not be sanitized for XSS
            methods: List of allowed HTTP methods (default: ["POST"])

        Example:
            ```python
            @mcp.register()
            def handle_mcp():
                # Import tool modules here
                pass
            ```
        """
        import frappe

        if methods is None:
            methods = ["POST"]

        whitelister = frappe.whitelist(
            allow_guest=allow_guest,
            xss_safe=xss_safe,
            methods=methods,
        )

        def decorator(fn):
            if self._entry_fn is not None:
                raise Exception("Only one MCP endpoint allowed per MCPServer instance")

            self._entry_fn = fn

            def wrapper() -> Response:
                # Run user's function to perform auth checks and build the
                # per-request tool registry. The registry is returned to keep it
                # off any shared/global state, so concurrent requests stay
                # isolated (see issue #197).
                result = fn()

                # If fn() returned a Response (e.g., 401 auth failure), use that.
                if isinstance(result, Response):
                    return result

                # Otherwise fn() returns the per-request tool registry (a dict),
                # a zero-arg callable that builds it on demand, or None to fall
                # back to the shared registry.
                tool_registry = result if isinstance(result, dict) or callable(result) else None

                # Handle MCP request
                request = frappe.request
                response = Response()
                return self.handle(request, response, tool_registry=tool_registry)

            return whitelister(wrapper)

        return decorator

    def handle(self, request: Request, response: Response, tool_registry: Optional[Dict] = None) -> Response:
        """
        Handle MCP request - main entry point.

        Processes JSON-RPC 2.0 requests according to MCP specification.

        Args:
            request: Werkzeug Request object
            response: Werkzeug Response object
            tool_registry: Per-request tool registry (name -> tool_dict). When
                provided, all tool routing for this request reads from it instead
                of the shared ``self._tool_registry``. This is what keeps
                concurrent requests isolated: each request builds its own
                registry on the call stack rather than mutating a process-global
                one. Falls back to ``self._tool_registry`` when not supplied
                (e.g. tools registered directly via ``add_tool``).

        Returns:
            Populated Response object with MCP response
        """
        import frappe

        # Only POST allowed
        if request.method != "POST":
            response.status_code = 405
            return response

        # Parse JSON request
        try:
            data = request.get_json(force=True)
        except Exception as e:
            frappe.logger().error(
                f"MCP Parse Error: {str(e)}, Raw data: {request.get_data(as_text=True)[:500]}"
            )
            return self._error_response(response, None, -32700, "Parse error")

        if not isinstance(data, dict):
            return self._error_response(response, None, -32600, "Invalid Request: expected a JSON object")
        frappe.logger().debug(f"MCP Request: method={data.get('method')}, id={data.get('id')}")

        # Populate correlation ids on frappe.local so downstream audit logging
        # can tag every tool execution with the MCP session and client. See
        # _populate_correlation_ids for header/initialize param fallback order.
        self._populate_correlation_ids(request, data)

        # Check if notification (no response needed)
        if self._is_notification(data):
            response.status_code = 202  # Accepted
            # Echo MCP-Protocol-Version header if present (2025-06-18 spec)
            incoming_version = frappe.request.headers.get("mcp-protocol-version")
            if incoming_version:
                response.headers["mcp-protocol-version"] = incoming_version
            return response

        # Get request ID
        request_id = data.get("id")
        if request_id is None:
            return self._error_response(response, None, -32600, "Invalid Request: missing id")

        # Route method
        method = data.get("method")
        params = data.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return self._error_response(response, request_id, -32602, "Invalid params: expected an object")

        result = None

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list(params, self._resolve_registry(tool_registry))
            elif method == "tools/call":
                arguments = params.get("arguments")
                arg_keys = sorted(arguments) if isinstance(arguments, dict) else []
                frappe.logger().info(f"MCP tools/call: tool={params.get('name')}, arg_keys={arg_keys}")
                result = self._handle_tools_call(params, self._resolve_registry(tool_registry))
            elif method == "resources/list":
                result = self._handle_resources_list(params, request_id)
            elif method == "resources/read":
                result = self._handle_resources_read(params, request_id)
            elif method == "resources/templates/list":
                from pibiassistant.api.handlers.resources import handle_resource_templates_list

                result = handle_resource_templates_list()
            elif method == "prompts/list":
                result = self._handle_prompts_list(params, request_id)
            elif method == "prompts/get":
                result = self._handle_prompts_get(params, request_id)
            elif method == "ping":
                result = {}
            else:
                frappe.logger().warning(f"MCP Unknown method: {method}")
                return self._error_response(response, request_id, -32601, f"Method not found: {method}")
        except InvalidParams as e:
            return self._error_response(response, request_id, -32602, f"Invalid params: {e}")
        except Exception as e:
            frappe.logger().error(
                f"MCP Handler Error for method '{method}': {str(e)}\n{traceback.format_exc()}"
            )
            return self._error_response(response, request_id, -32603, "Internal error")

        # Success response
        return self._success_response(response, request_id, result)

    def _resolve_registry(self, tool_registry) -> Dict:
        """Per-request registry (built on first need); falls back to the shared one."""
        if callable(tool_registry):
            return tool_registry()
        return self._tool_registry if tool_registry is None else tool_registry

    def add_tool(self, tool_dict: Dict):
        """
        Programmatically add a tool.

        Used by tool_adapter to register BaseTool instances.

        Args:
            tool_dict: Dict with keys: name, description, inputSchema, fn, annotations
        """
        self._tool_registry[tool_dict["name"]] = tool_dict

    def _populate_correlation_ids(self, request: Request, data: Dict):
        """
        Set `frappe.local.assistant_session_id` and `assistant_client_id`.

        Resolution order for session id:
            1. `Mcp-Session-Id` request header (MCP streamable HTTP transport)
            2. `X-Assistant-Session-Id` request header (explicit override)
            3. A freshly-generated UUID4 (per-request fallback)

        Resolution order for client id:
            1. `X-Assistant-Client-Id` request header
            2. `clientInfo.name` from the `initialize` params when present
            3. `None`
        """
        import uuid

        import frappe

        session_id = (
            request.headers.get("Mcp-Session-Id")
            or request.headers.get("X-Assistant-Session-Id")
            or str(uuid.uuid4())
        )

        client_id = request.headers.get("X-Assistant-Client-Id")
        if not client_id:
            params = data.get("params")
            client_info = params.get("clientInfo") if isinstance(params, dict) else None
            client_id = client_info.get("name") if isinstance(client_info, dict) else None

        frappe.local.assistant_session_id = session_id
        frappe.local.assistant_client_id = client_id

    def _handle_initialize(self, params: Dict) -> Dict:
        """
        Handle initialize request.

        Declares server capabilities according to MCP 2025-06-18 spec.
        We only support tools (not prompts, resources, or sampling).
        """
        import frappe

        # Echo the client's version when we speak it, else offer our configured one.
        protocol_version = SUPPORTED_PROTOCOL_VERSIONS[0]
        try:
            protocol_version = (
                frappe.db.get_single_value("PA Core Settings", "mcp_protocol_version") or protocol_version
            )
        except Exception:
            pass
        requested = params.get("protocolVersion")
        if requested in SUPPORTED_PROTOCOL_VERSIONS:
            protocol_version = requested

        return {
            "protocolVersion": protocol_version,
            "capabilities": {
                "tools": {},  # We support tools
                "prompts": {},  # We support prompts (database-driven templates)
                "resources": {},  # We support resources (skill documents)
            },
            "serverInfo": {"name": self.name, "title": "AIDA by pibiCo", "version": "2.0.0"},
            "instructions": SERVER_INSTRUCTIONS,
        }

    def _handle_tools_list(self, params: Dict, tool_registry: Optional[Dict] = None) -> Dict:
        """Handle tools/list request with optional token optimization."""
        import frappe

        if tool_registry is None:
            tool_registry = self._tool_registry

        tools_list = []

        # Check skill_mode for token optimization
        skill_replace_map = {}
        try:
            settings = frappe.get_single("PA Core Settings")
            if getattr(settings, "skill_mode", "supplementary") == "replace":
                from pibiassistant.api.handlers.resources import get_skill_manager

                skill_replace_map = get_skill_manager().get_tool_skill_map(user=frappe.session.user)
        except Exception:
            pass

        for tool in tool_registry.values():
            description = tool["description"]

            # In replace mode, minimize descriptions for tools with linked skills
            if skill_replace_map and tool["name"] in skill_replace_map:
                skill_info = skill_replace_map[tool["name"]]
                description = f"{tool['name']}: {skill_info['description']}. Detailed guidance: pa://skills/{skill_info['skill_id']}"

            tool_spec = {
                "name": tool["name"],
                "description": description,
                "inputSchema": tool["inputSchema"],
            }
            if tool.get("title"):
                tool_spec["title"] = tool["title"]

            # Add annotations if present
            if tool.get("annotations"):
                tool_spec["annotations"] = tool["annotations"]

            tools_list.append(tool_spec)

        return {"tools": tools_list}

    def _handle_tools_call(self, params: Dict, tool_registry: Optional[Dict] = None) -> Dict:
        """
        Handle tools/call request.

        This is the CRITICAL method that fixes the serialization issue.
        Uses json.dumps with default=str to handle datetime, Decimal, etc.
        """
        import frappe

        if tool_registry is None:
            tool_registry = self._tool_registry

        tool_name = params.get("name")
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise InvalidParams("arguments must be an object")
        if not isinstance(tool_name, str):
            raise InvalidParams("name must be a string")

        # Check tool exists
        if tool_name not in tool_registry:
            error_msg = f"Tool '{tool_name}' not found. Call tools/list to see the available tools."
            frappe.logger().error(f"MCP Tool Not Found: {tool_name}")
            return {
                "content": [{"type": "text", "text": error_msg}],
                "isError": True,
            }

        tool = tool_registry[tool_name]
        fn = tool["fn"]

        try:
            # Execute tool
            frappe.logger().info(f"MCP Executing tool: {tool_name}")
            result = fn(**arguments)
            frappe.logger().info(
                f"MCP Tool {tool_name} executed successfully, result type: {type(result).__name__}"
            )

            # Extract image content for vision API (e.g., screenshot tool).
            # Tools can include _image_content in their result to have the LLM
            # see the image directly via vision, rather than just getting metadata.
            # Note: BaseTool._safe_execute() wraps tool output as:
            #   {"success": True, "result": <tool_output>, "execution_time": ...}
            # so _image_content lives inside result["result"], not at the top level.
            image_content = None
            if isinstance(result, dict):
                inner = result.get("result")
                if isinstance(inner, dict) and "_image_content" in inner:
                    image_content = inner.pop("_image_content")

            # ChatGPT connectors read the text of search and fetch as the bare {"results": [...]} / document
            # object, not wrapped in the {"success", "result"} envelope every other tool returns.
            payload = result
            key = BARE_RESULT_TOOLS.get(tool_name)
            if key and isinstance(result, dict) and isinstance(result.get("result"), dict) and key in result["result"]:
                payload = result["result"]

            # Serialize the text result (default=str handles datetime, Decimal, etc.); compact JSON saves tokens.
            if isinstance(payload, str):
                result_text = payload
            else:
                result_text = dumps_strict(payload, separators=(",", ":"), ensure_ascii=False)

            limit = _max_result_chars()
            truncated = len(result_text) > limit
            if truncated:
                result_text = fit_result(result_text, limit)

            # Build MCP content blocks
            content = [{"type": "text", "text": result_text}]

            # Add image block for vision API if tool provided one
            if image_content and isinstance(image_content, dict):
                mime_map = {
                    "jpeg": "image/jpeg",
                    "jpg": "image/jpeg",
                    "png": "image/png",
                    "gif": "image/gif",
                    "webp": "image/webp",
                }
                fmt = image_content.get("format", "jpeg")
                content.append(
                    {
                        "type": "image",
                        "mimeType": mime_map.get(fmt, f"image/{fmt}"),
                        "data": image_content["data"],
                    }
                )

            tool_failed = isinstance(result, dict) and result.get("success") is False
            response = {"content": content, "isError": tool_failed}
            if isinstance(payload, dict) and not truncated and len(result_text) <= MAX_STRUCTURED_CHARS:
                response["structuredContent"] = json.loads(result_text)
            return response

        except Exception as e:
            frappe.logger().error(
                f"MCP Tool Execution Error: {tool_name}: {str(e)}\n{traceback.format_exc()}"
            )
            return {
                "content": [{"type": "text", "text": f"Error executing {tool_name}: {str(e)}"}],
                "isError": True,
            }

    def _success_response(self, response: Response, request_id: Any, result: Dict) -> Response:
        """Create JSON-RPC success response."""
        import frappe

        response_data = {"jsonrpc": "2.0", "id": request_id, "result": result}

        # Use default=str here too for consistency
        response.data = json.dumps(response_data, default=str)
        response.mimetype = "application/json"
        response.status_code = 200

        # Echo MCP-Protocol-Version header if present (2025-06-18 spec)
        incoming_version = frappe.request.headers.get("mcp-protocol-version")
        if incoming_version:
            response.headers["mcp-protocol-version"] = incoming_version

        return response

    def _error_response(
        self, response: Response, request_id: Optional[Any], code: int, message: str
    ) -> Response:
        """Create JSON-RPC error response."""
        import frappe

        response_data = {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}

        response.data = json.dumps(response_data)
        response.mimetype = "application/json"
        response.status_code = 400

        # Echo MCP-Protocol-Version header if present (2025-06-18 spec)
        incoming_version = frappe.request.headers.get("mcp-protocol-version")
        if incoming_version:
            response.headers["mcp-protocol-version"] = incoming_version

        return response

    def _handle_prompts_list(self, params: Dict, request_id: Any) -> Dict:
        """
        Handle prompts/list request.

        Returns available prompt templates from the database.
        """
        from pibiassistant.api.handlers.prompts import handle_prompts_list

        # The handler returns a full JSON-RPC response, extract just the result
        response = handle_prompts_list(request_id)
        if "result" in response:
            return response["result"]
        # If there's an error, return empty prompts list
        return {"prompts": []}

    def _handle_prompts_get(self, params: Dict, request_id: Any) -> Dict:
        """
        Handle prompts/get request.

        Returns a specific prompt template rendered with provided arguments.
        """
        from pibiassistant.api.handlers.prompts import handle_prompts_get

        # The handler returns a full JSON-RPC response, extract just the result
        response = handle_prompts_get(params, request_id)
        if "result" in response:
            return response["result"]
        # If there's an error, re-raise it
        if "error" in response:
            err = response["error"]
            message = err.get("message", "Unknown prompt error")
            if err.get("code") in (-32602, -32000):  # validation / permission denied
                raise InvalidParams(message)
            raise Exception(message)
        return {}

    def _handle_resources_list(self, params: Dict, request_id: Any) -> Dict:
        """
        Handle resources/list request.

        Returns available skill documents as MCP resources.
        """
        from pibiassistant.api.handlers.resources import handle_resources_list

        return handle_resources_list(request_id)

    def _handle_resources_read(self, params: Dict, request_id: Any) -> Dict:
        """
        Handle resources/read request.

        Returns the content of a specific skill resource by URI.
        """
        import frappe

        from pibiassistant.api.handlers.resources import handle_resources_read

        try:
            return handle_resources_read(params, request_id)
        except (ValueError, frappe.PermissionError) as e:
            raise InvalidParams(str(e))

    def _is_notification(self, data: Dict) -> bool:
        """A notification is a notifications/* message without an id; with an id it is a request."""
        method = data.get("method", "")
        return "id" not in data and isinstance(method, str) and method.startswith("notifications/")
