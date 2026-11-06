"""data_layer/filenames.py - small filename helpers shared by the archive classes."""

import re


def safe_filename_component(value) -> str:
    """Turn an arbitrary string (a date, a username, a timestamp) into
    something safe to use inside a filename - letters, numbers, dashes
    and underscores only, everything else replaced with "_"."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value)) or "unknown"


def guess_extension(mime_type: str) -> str:
    """Fallback file extension when the original filename has none."""
    return {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
    }.get(mime_type, "")
