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
API handlers for different MCP methods
Modular organization for better maintainability
"""

from .initialize import handle_initialize
from .prompts import handle_prompts_get, handle_prompts_list
from .tools import handle_tool_call, handle_tools_list

__all__ = [
    "handle_initialize",
    "handle_tools_list",
    "handle_tool_call",
    "handle_prompts_list",
    "handle_prompts_get",
]
