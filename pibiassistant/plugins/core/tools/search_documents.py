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
Search Documents Tool for Core Plugin.

The single text-search entry point. It replaces the former search_documents /
search_doctype / search_link trio, which differed only in whether a doctype was
supplied and how results were shaped — a parameter, not three tools. Three
near-identical tool descriptions gave the model nothing to choose between, and
the routing rules now live in this one description instead of in a skill
document written to undo the confusion.
"""

from typing import Any, Dict

from frappe import _

from pibiassistant.core.base_tool import BaseTool
from pibiassistant.plugins.limits import clamp_int
from pibiassistant.plugins.query_errors import log_failure, single_doctype_message

# Hard ceiling on rows returned, whatever the caller asks for.
MAX_LIMIT = 100

DEFAULT_LIMIT = 20


class SearchDocuments(BaseTool):
    """
    Unified document search.

    Routes on its arguments:
    - no ``doctype``            -> full-text search across everything readable
    - ``doctype``               -> text search within that DocType
    - ``purpose="link_value"``  -> autocomplete-style Link field resolution
    """

    def __init__(self):
        super().__init__()
        self.name = "search_documents"
        self.description = (
            "Find documents by text. Omit 'doctype' to search across everything the user can read; "
            "pass 'doctype' to search within one DocType. Set purpose='link_value' to resolve a valid "
            "value for a Link field before creating or updating a document (returns display-ready "
            "candidates). Text search also matches identifiers where the DocType has them: NIF/tax_id, supplier invoice no. (bill_no), po_no, email_id, mobile_no. This is a text search — for exact filtering by status, date range, or amount, "
            "and for counting records, use list_documents instead."
        )
        self.requires_permission = None  # Permission checked dynamically per DocType

        self.inputSchema = {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search for. Short queries work best — a name, code, or single phrase.",
                },
                "doctype": {
                    "type": "string",
                    "description": "Optional DocType to search within (e.g. 'Customer', 'Sales Invoice'). Omit to search globally. Required when purpose is 'link_value'.",
                },
                "purpose": {
                    "type": "string",
                    "enum": ["documents", "link_value"],
                    "default": "documents",
                    "description": "'documents' (default) finds records. 'link_value' resolves a valid value for a Link field, honouring that DocType's custom search query.",
                },
                "filters": {
                    "type": "object",
                    "default": {},
                    "description": "Optional filters narrowing the search, e.g. {'status': 'Active'}. Applied together with the text match. Requires 'doctype'.",
                },
                "limit": {
                    "type": "integer",
                    "default": DEFAULT_LIMIT,
                    "maximum": MAX_LIMIT,
                    "description": f"Maximum results to return. Default {DEFAULT_LIMIT}, maximum {MAX_LIMIT}.",
                },
                "start": {
                    "type": "integer",
                    "default": 0,
                    "description": "Rows to skip, for paging within one doctype. When a result has has_more, pass its next_start here.",
                },
            },
            "required": ["query"],
        }

    def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Route to the search mode implied by the arguments."""
        try:
            from .search_tools import SearchTools

            query = arguments.get("query")
            doctype = arguments.get("doctype")
            purpose = arguments.get("purpose") or "documents"
            filters = arguments.get("filters") or {}
            limit = self._clamp_limit(arguments.get("limit"))
            start = clamp_int(arguments.get("start"), 0, 0, 1_000_000)

            if purpose == "link_value":
                if not doctype:
                    return {
                        "success": False,
                        "error": _("purpose='link_value' needs a doctype — the Link field's target."),
                    }
                return SearchTools.search_link(doctype=doctype, query=query, filters=filters, limit=limit)

            if doctype:
                single_message = single_doctype_message(doctype)
                if single_message:
                    return {"success": False, "error": single_message, "doctype": doctype}
                return SearchTools.search_doctype(
                    doctype=doctype, query=query, limit=limit, filters=filters, start=start
                )

            if filters:
                # Filters need a DocType to resolve fieldnames against, so silently
                # dropping them would return a broader result set than asked for.
                return {
                    "success": False,
                    "error": _("Filters require a doctype. Omit filters for a global search."),
                }

            return SearchTools.global_search(query=query, limit=limit)

        except Exception as e:
            log_failure("Search Documents Error", e)

            return {"success": False, "error": str(e)[:2000]}

    def _clamp_limit(self, limit: Any) -> int:
        """Keep limit within bounds; a non-numeric value falls back to the default."""
        return clamp_int(limit, DEFAULT_LIMIT, 0, MAX_LIMIT) or DEFAULT_LIMIT


# Make sure class name matches file name for discovery
search_documents = SearchDocuments
