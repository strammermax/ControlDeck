"""Read-only, bounded ProxMenux network projection; no raw monitor configuration."""
import ipaddress
import re
from collections import Counter
from backend.guest_inventory import finite
from backend.storage_inventory import text

LATENCY_PATH = "network/latency/history?target=gateway&timeframe=hour"
HISTORY_STEPS = {"hour": 60, "day": 300, "week": 1800, "month": 1800, "year": 21600}
GROUPS = {"physical_interfaces": "physical", "bond_interfaces": "bond", "bridge_interfaces": "bridge", "vm_lxc_interfaces": "virtual"}
COUNTERS = ("bytes_recv", "bytes_sent", "packets_recv", "packets_sent", "errors_in", "errors_out", "drops_in", "drops_out", "rx_Bps", "tx_Bps", "speed", "max_speed", "mtu")


def interface_name(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:@-]{1,64}", value) else None


def network_history(node, value, timeframe):
    """Project the same node RRD rates used by ProxMenux's historical traffic chart."""
    result = {"history": [], "historyAvailable": False, "timeframe": timeframe, "step": HISTORY_STEPS[timeframe]}
    if not isinstance(value, dict) or value.get("node", node) != node or value.get("timeframe", timeframe) != timeframe:
        return result
    rows = value.get("data")
    if not isinstance(rows, list) or len(rows) > 5000:
        return result
    seen, points = set(), []
    for row in rows:
        timestamp = finite(row.get("time")) if isinstance(row, dict) else None
        if timestamp is None or timestamp <= 0 or timestamp > 1e11 or timestamp != int(timestamp) or timestamp in seen:
            return result
        seen.add(timestamp)
        points.append({"time": int(timestamp), "received": finite(row.get("netin")), "sent": finite(row.get("netout"))})
    points.sort(key=lambda p: p["time"])
    differences = [b["time"] - a["time"] for a, b in zip(points, points[1:])]
    if differences:
        result["step"] = min(HISTORY_STEPS[timeframe], Counter(differences).most_common(1)[0][0])
    if result["step"] < 1 or result["step"] > 86400:
        return result
    return {**result, "history": points, "historyAvailable": True}


def network_rates(current, previous, seconds):
    """Older monitors omit rates: derive only from consecutive, non-reset counters."""
    if not previous or not 1 <= seconds <= 180:
        return current
    before = {i["name"]: i for i in previous.get("interfaces", [])}
    for item in current["interfaces"]:
        old = before.get(item["name"])
        if not old or old["node"] != item["node"] or old["kind"] != item["kind"]:
            continue
        for rate, counter in (("rx_Bps", "bytes_recv"), ("tx_Bps", "bytes_sent")):
            now, then = item[counter], old[counter]
            if item[rate] is None and now is not None and then is not None and now >= then:
                item[rate] = round((now - then) / seconds, 2)
    return current


def network_snapshot(node, network, latency):
    """Keep independent interface counters: physical totals never include bridges/bonds/taps."""
    network = network if isinstance(network, dict) else {}
    rows, seen = [], set()
    for key, kind in GROUPS.items():
        collection = network.get(key)
        for item in collection[:2048] if isinstance(collection, list) else []:
            if not isinstance(item, dict):
                continue
            name = interface_name(item.get("name"))
            if not name or name in seen:
                continue
            seen.add(name)
            addresses = []
            for address in item.get("addresses", [])[:32] if isinstance(item.get("addresses"), list) else []:
                try:
                    addresses.append(str(ipaddress.ip_address(address["ip"])))
                except (ValueError, KeyError, TypeError):
                    continue
            relations = {}
            for field in ("used_by_bridges", "bond_slaves", "bridge_members"):
                values = item.get(field)
                relations[field] = list(dict.fromkeys(v for v in values[:128] if interface_name(v))) if isinstance(values, list) else []
            mac = item.get("mac_address")
            rows.append({"node": node, "name": name, "kind": kind,
                         "status": item.get("status") if item.get("status") in ("up", "down") else "unknown",
                         "addresses": list(dict.fromkeys(addresses)), "mac": mac if isinstance(mac, str) and re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", mac) else None,
                         "duplex": item.get("duplex") if item.get("duplex") in ("full", "half") else None,
                         **{field: finite(item.get(field)) for field in COUNTERS}, **relations,
                         **{field: interface_name(item.get(field)) for field in ("bridge_owner", "bond_master", "bond_active_slave", "bridge_physical_interface")},
                         "bond_mode": text(item.get("bond_mode"), 64), "vmid": finite(item.get("vmid")),
                         "bond_role": item.get("bond_role") if item.get("bond_role") in ("active", "standby", "member") else None,
                         "bond_link": item.get("bond_link") if item.get("bond_link") in ("up", "down") else None,
                         "vm_status": item.get("vm_status") if item.get("vm_status") in ("running", "stopped", "paused") else None,
                         "vm_name": text(item.get("vm_name"), 100), "vm_type": item.get("vm_type") if item.get("vm_type") in ("vm", "lxc") else None})
    latency = latency if isinstance(latency, dict) else {}
    stats = latency.get("stats") if isinstance(latency.get("stats"), dict) else {}
    history = []
    values = latency.get("data")
    for point in values[-240:] if isinstance(values, list) else []:
        if not isinstance(point, dict):
            continue
        timestamp, value = finite(point.get("timestamp")), finite(point.get("value"))
        if timestamp is not None and value is not None:
            history.append({"time": timestamp, "value": value})
    dns = []
    for value in network.get("dns_servers", [])[:16] if isinstance(network.get("dns_servers"), list) else []:
        try:
            dns.append(str(ipaddress.ip_address(value)))
        except ValueError:
            continue
    return {"interfaces": rows, "networkAvailable": isinstance(network.get("physical_interfaces"), list),
            "hostname": text(network.get("hostname"), 100), "domain": text(network.get("domain"), 100), "dns": dns,
            "latency": {**{key: finite(stats.get(key)) for key in ("current", "avg", "max", "min")}, "history": sorted(history, key=lambda p: p["time"])}}
