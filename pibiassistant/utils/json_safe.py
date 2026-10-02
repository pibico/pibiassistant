import json
import math


def finite(value):
    """Return value with every NaN/Infinity float replaced by None (recursively)."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(v) for v in value]
    return value


def dumps_strict(obj, **kwargs):
    """json.dumps that never emits the invalid NaN/Infinity tokens."""
    kwargs.setdefault("default", str)
    return json.dumps(finite(obj), **kwargs)
