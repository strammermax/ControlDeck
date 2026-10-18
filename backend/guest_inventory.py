"""Safe guest projection shared by the Proxmox inventory and monitor enrichment."""
import ipaddress
import math
import re

METRICS = ("cpu", "maxcpu", "mem", "maxmem", "disk", "maxdisk", "uptime", "netin", "netout", "diskread", "diskwrite")


def finite(value):
    return value if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 2**53 - 1 else None


def project_guests(value, node=None):
    if not isinstance(value, list) or len(value) > 5000:
        raise ValueError("Ongeldige gastenlijst.")
    rows, seen = [], set()
    for guest in value:
        if not isinstance(guest, dict) or guest.get("type") not in ("qemu", "vm", "lxc"):
            continue
        identifier = guest.get("vmid")
        host = node or guest.get("node")
        if type(identifier) is not int or not 1 <= identifier <= 999999999 or identifier in seen or not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,62}", host):
            continue
        seen.add(identifier)
        name = guest.get("name")
        row = {"vmid": identifier, "node": host, "name": name[:100] if isinstance(name, str) else str(identifier),
               "type": "qemu" if guest["type"] == "vm" else guest["type"],
               "status": guest.get("status") if guest.get("status") in ("running", "stopped", "paused") else "unknown",
               **{key: finite(guest.get(key)) for key in METRICS}, "ip": None,
               "tags": guest.get("tags", "")[:500] if isinstance(guest.get("tags", ""), str) else ""}
        check = guest.get("update_check")
        row["updates"] = finite(check.get("count")) if isinstance(check, dict) and check.get("available") else None
        rows.append(row)
    return sorted(rows, key=lambda row: row["vmid"])


def config_ip(config):
    """Only explicit valid LXC addresses; never infer an address from a container id."""
    for key, value in sorted(config.items()):
        if not re.fullmatch(r"net[0-9]+", key) or not isinstance(value, str):
            continue
        for part in value.split(","):
            name, _, address = part.partition("=")
            if name not in ("ip", "ip6"):
                continue
            try:
                ip = ipaddress.ip_interface(address).ip
                if not ip.is_loopback and not ip.is_link_local and not ip.is_unspecified:
                    return str(ip)
            except ValueError:
                pass
    return None


def project_inventory(resources):
    guests = project_guests(resources)
    nodes = []
    for resource in resources:
        if not isinstance(resource, dict) or resource.get("type") != "node":
            continue
        name = resource.get("node")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,62}", name) or any(n["name"] == name for n in nodes):
            continue
        nodes.append({"name": name, "online": resource.get("status") == "online", **{key: finite(resource.get(key)) for key in ("cpu", "maxcpu", "mem", "maxmem")}})
    return {"guests": guests, "nodes": sorted(nodes, key=lambda n: n["name"])}
