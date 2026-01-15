"""Text utilities for safe string handling.

This module provides UTF-8 safe string truncation utilities to prevent
character boundary issues when strings are processed by native code.
"""

import json
import re
from typing import Any, Optional


def safe_truncate(text: str, max_chars: int, suffix: str = "...") -> str:
    """Safely truncate text without breaking multi-byte characters.

    Python string slicing already operates on Unicode code points,
    but this function provides additional safety by:
    1. Avoiding truncation in the middle of surrogate pairs
    2. Trying to break at word boundaries when possible
    3. Ensuring the result is valid UTF-8 when encoded

    Args:
        text: Text to truncate
        max_chars: Maximum characters (excluding suffix)
        suffix: Suffix to append if truncated (default "...")

    Returns:
        Truncated text with suffix if needed
    """
    if not text or len(text) <= max_chars:
        return text

    # Basic truncation at character level
    truncated = text[:max_chars]

    # Try to break at a word boundary (space, punctuation) for cleaner output
    # Look back up to 20 characters for a good break point
    break_chars = {' ', '\n', '\t', ',', '.', '!', '?', ';', ':', '-', '\u3002', '\uff0c', '\u3001'}
    for i in range(min(20, max_chars - 1), 0, -1):
        if truncated[-(i)] in break_chars:
            truncated = truncated[:-(i-1)].rstrip()
            break

    # Verify the result is valid UTF-8 (should always be true in Python 3)
    try:
        truncated.encode('utf-8').decode('utf-8')
    except UnicodeError:
        # Fallback: try removing last few characters
        for i in range(1, 5):
            try:
                truncated = text[:max_chars - i]
                truncated.encode('utf-8').decode('utf-8')
                break
            except UnicodeError:
                continue

    return truncated + suffix


def safe_truncate_json(value: Any, max_chars: int = 100, suffix: str = "...") -> str:
    """Safely truncate a JSON-serialized value.

    This is specifically designed to prevent issues when truncating
    JSON strings that may contain escape sequences or Unicode.

    Args:
        value: Value to serialize and truncate
        max_chars: Maximum characters for the result
        suffix: Suffix to append if truncated

    Returns:
        Truncated JSON string representation
    """
    try:
        json_str = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        json_str = str(value)

    if len(json_str) <= max_chars:
        return json_str

    # For JSON, we need to be more careful about truncation
    # Don't truncate in the middle of escape sequences or inside strings
    truncated = json_str[:max_chars]

    # Count unescaped quotes to check if we're inside a string
    in_string = False
    escape_next = False
    safe_end = 0

    for i, char in enumerate(truncated):
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            if not in_string:
                safe_end = i + 1
        elif not in_string and char in ',]}':
            safe_end = i + 1

    # If we ended inside a string, truncate to last safe position
    if in_string and safe_end > 0:
        truncated = json_str[:safe_end]

    return truncated + suffix


def normalize_for_display(text: str, max_length: Optional[int] = None) -> str:
    """Normalize text for safe display in logs and UI.

    This function:
    1. Removes control characters
    2. Normalizes whitespace
    3. Optionally truncates to max_length

    Args:
        text: Text to normalize
        max_length: Optional maximum length

    Returns:
        Normalized text
    """
    if not text:
        return ""

    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Normalize whitespace (preserve newlines)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    if max_length:
        text = safe_truncate(text, max_length)

    return text.strip()

