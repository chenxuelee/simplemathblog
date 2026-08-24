"""Small, deliberately limited Front Matter parser shared by Python tools.

The browser renderer implements the same documented subset: scalars, inline
lists and dash lists.  Keeping this parser in one module prevents the blog
builder and single-page exporter from silently disagreeing.
"""

from __future__ import annotations

import re
from typing import Any


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    match = re.match(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n?", text)
    if not match:
        return {}, text
    meta: dict[str, Any] = {}
    key: str | None = None
    for line in match.group(1).splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        item = re.match(r"^-\s+(.+)$", trimmed)
        if item and key:
            previous = meta.get(key, [])
            meta[key] = previous if isinstance(previous, list) else [previous]
            meta[key].append(item.group(1).strip().strip("\"'"))
            continue
        pair = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", trimmed)
        if not pair:
            continue
        key, value = pair.group(1), pair.group(2).strip()
        array = re.match(r"^\[(.*)\]$", value)
        if array:
            meta[key] = [part.strip().strip("\"'") for part in array.group(1).split(",") if part.strip()]
        else:
            meta[key] = "" if value == "" else value.strip("\"'")
    return meta, text[match.end():]
