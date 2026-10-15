"""Widget references contain no connection details."""
import re


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) != {"sourceId"} or not isinstance(settings["sourceId"], str) or not re.fullmatch(r"[a-z0-9-]{0,64}", settings["sourceId"]):
        raise ValueError("Kies een geldige widgetbron.")
