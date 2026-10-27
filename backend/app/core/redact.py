import re
from typing import Any
from app.core.config import settings

# Secret redaction patterns
RE_KEY_QUERY = re.compile(r'(?i)([?&]key=)[^&\s"\'>]+')
RE_AUTH_HEADER = re.compile(r'(?i)(Authorization:\s*)(?:Bearer\s+)?[^\s"\'>\r\n]+')
RE_BEARER = re.compile(r'(?i)(Bearer\s+)[A-Za-z0-9\-_.]+')
RE_GOOG_HEADER = re.compile(r'(?i)(x-goog-api-key["\'\s:=]+)[^\s"\'&,>]+')
RE_AIZA_KEY = re.compile(r'AIza[0-9A-Za-z\-_]{20,}')
RE_AQ_KEY = re.compile(r'AQ\.[0-9A-Za-z\-_]{20,}')


def redact(value: Any) -> str:
    """Removes sensitive keys, tokens, and credentials from strings, URLs, and exception messages."""
    if value is None:
        return ""
    text = str(value)
    if not text:
        return ""

    # 1. Redact configured environment secrets if present and non-trivial
    if settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) >= 6:
        text = text.replace(settings.GEMINI_API_KEY, "[REDACTED]")
    if settings.JWT_SECRET and len(settings.JWT_SECRET) >= 6:
        text = text.replace(settings.JWT_SECRET, "[REDACTED]")

    # 2. Redact patterns: key= query parameters, auth headers, Google API keys
    text = RE_KEY_QUERY.sub(r'\1[REDACTED]', text)
    text = RE_AUTH_HEADER.sub(r'\1[REDACTED]', text)
    text = RE_BEARER.sub(r'\1[REDACTED]', text)
    text = RE_GOOG_HEADER.sub(r'\1[REDACTED]', text)
    text = RE_AIZA_KEY.sub('[REDACTED]', text)
    text = RE_AQ_KEY.sub('[REDACTED]', text)

    return text
