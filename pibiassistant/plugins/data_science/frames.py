"""Shared pandas helpers for the data science tools."""

import math
from typing import Any, Dict, Iterable, List


def rows_to_dicts(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    """frappe._dict rows make pandas 3 raise 'invalid __array_struct__'; plain dicts do not."""
    return [dict(row) for row in rows]


def clean_number(value: Any) -> Any:
    """NaN/inf are not valid JSON; report them as null."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
