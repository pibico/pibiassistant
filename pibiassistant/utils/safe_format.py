"""Rendering for user-authored Format String templates.

Plain ``str.format`` lets a template walk attributes (``{a.__class__}``), index into
objects and size output through nested fields (``{n:>{n}}``). Only flat ``{name}`` fields
with a short, literal format spec are accepted here.
"""

import re
import string

MAX_OUTPUT_CHARS = 200_000
_FIELD = re.compile(r"^\w+$")
_SPEC = re.compile(r"^[<>^=+\- ]?[#0]?\d{0,3}[,_]?(\.\d{1,2})?[sdfeEgGn%]?$")


def safe_format(template: str, arguments: dict) -> str:
    out = []
    size = 0
    for literal, field, spec, conversion in string.Formatter().parse(template):
        out.append(literal)
        size += len(literal)
        if field is None:
            continue
        if not _FIELD.match(field):
            raise ValueError(f"Unsupported field '{field}': only plain names are allowed")
        if spec and not _SPEC.match(spec):
            raise ValueError(f"Unsupported format spec '{spec}'")
        if conversion not in (None, "s", "r", "a"):
            raise ValueError(f"Unsupported conversion '{conversion}'")
        value = arguments[field]
        if conversion == "r":
            value = repr(value)
        elif conversion == "a":
            value = ascii(value)
        elif conversion == "s":
            value = str(value)
        text = format(value, spec or "")
        out.append(text)
        size += len(text)
        if size > MAX_OUTPUT_CHARS:
            raise ValueError("Rendered template is too large")
    return "".join(out)
