"""Proxmox widgets reuse the existing cluster API and permission."""


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) != {"view"}:
        raise ValueError("Ongeldige Proxmox-instellingen.")
    if not isinstance(settings["view"], str) or settings["view"] not in ("nodes", "guests", "tasks", "all", "health"):
        raise ValueError("Kies een geldige Proxmox-weergave.")
