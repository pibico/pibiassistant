"""Row-limit clamping shared by plugin tools."""

from typing import Any


def clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    """Return an int in minimum..maximum; missing or non-numeric input gives the default."""
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(minimum, min(number, maximum))


def clamp_limit(value: Any, default: int = 20, maximum: int = 1000) -> int:
    """Return an int in 1..maximum; missing, non-numeric or non-positive input gives the default."""
    fallback = min(default, maximum)
    return clamp_int(clamp_int(value, fallback, 0, maximum) or fallback, fallback, 1, maximum)
