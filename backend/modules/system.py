"""Display-only system metrics; existing Proxmox authorization remains authoritative."""
import re


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) != {"metric", "node"}:
        raise ValueError("Ongeldige systeemwidget-instellingen.")
    if not isinstance(settings["metric"], str) or settings["metric"] not in ("cpu", "memory", "temperature", "power"):
        raise ValueError("Kies een geldige systeemmeting.")
    if not isinstance(settings["node"], str) or not re.fullmatch(r"[A-Za-z0-9._-]{0,64}", settings["node"]):
        raise ValueError("Kies een geldige node.")
