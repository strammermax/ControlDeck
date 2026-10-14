"""URL validation shared by explicitly configured service login adapters."""
from urllib.parse import urlsplit


def secure_origin(value):
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or c == "\\" for c in value):
        raise ValueError("Ongeldig dienstadres.")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Gebruik een HTTPS-basisadres zonder aanmeldgegevens.")
    _ = parsed.port
    return value.rstrip("/")


def empty_settings(settings):
    if not isinstance(settings, dict) or settings:
        raise ValueError("Deze module heeft geen persoonlijke instellingen.")
