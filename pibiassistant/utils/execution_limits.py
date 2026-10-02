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
Execution limit defaults and the PA Core Settings lookup for sandboxed code execution.
"""

from typing import Dict

import frappe

# Default limits
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_MEMORY_MB = 512  # 512 MB
DEFAULT_MAX_CPU_TIME_SECONDS = 60
DEFAULT_MAX_RECURSION_DEPTH = 500
DEFAULT_MAX_OUTPUT_SIZE = 1024 * 1024  # 1 MB output limit


def get_execution_limits_from_settings() -> Dict[str, int]:
    """
    Get execution limits from PA Core Settings.

    Returns:
        Dict with timeout_seconds, max_memory_mb, max_cpu_seconds, max_recursion_depth
    """
    try:
        settings = frappe.get_cached_doc("PA Core Settings")

        return {
            "timeout_seconds": getattr(settings, "code_execution_timeout", DEFAULT_TIMEOUT_SECONDS)
            or DEFAULT_TIMEOUT_SECONDS,
            "max_memory_mb": getattr(settings, "code_execution_max_memory_mb", DEFAULT_MAX_MEMORY_MB)
            or DEFAULT_MAX_MEMORY_MB,
            "max_cpu_seconds": getattr(
                settings, "code_execution_max_cpu_seconds", DEFAULT_MAX_CPU_TIME_SECONDS
            )
            or DEFAULT_MAX_CPU_TIME_SECONDS,
            "max_recursion_depth": getattr(
                settings, "code_execution_max_recursion", DEFAULT_MAX_RECURSION_DEPTH
            )
            or DEFAULT_MAX_RECURSION_DEPTH,
        }
    except Exception:
        # Return defaults if settings can't be loaded
        return {
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
            "max_memory_mb": DEFAULT_MAX_MEMORY_MB,
            "max_cpu_seconds": DEFAULT_MAX_CPU_TIME_SECONDS,
            "max_recursion_depth": DEFAULT_MAX_RECURSION_DEPTH,
        }


