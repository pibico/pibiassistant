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
Error codes and message strings used by the MCP prompt handlers
"""


# API Error Codes
class ErrorCodes:
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    AUTHENTICATION_REQUIRED = -32000


class ErrorMessages:
    MISSING_PROMPT_NAME = "Missing prompt name"
    UNKNOWN_PROMPT = "Unknown prompt: {}"
    INTERNAL_ERROR = "Internal error"


class LogMessages:
    PROMPTS_LIST_REQUEST = "Handling prompts/list request"
    PROMPTS_GET_REQUEST = "Handling prompts/get request with params: {}"
