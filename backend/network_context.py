"""Network hints for link visibility only, never an authentication boundary."""
import os
from ipaddress import ip_address, ip_network

DEFAULT_LOCAL = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7,fe80::/10"


def networks(value):
    try:
        rows = [ip_network(part.strip(), strict=False) for part in value.split(",") if part.strip()]
        if len(rows) > 64 or any(row.prefixlen == 0 for row in rows):
            return []
        return rows
    except (ValueError, AttributeError):
        return []


def address(value):
    try:
        result = ip_address(value)
        return result.ipv4_mapped if result.version == 6 and result.ipv4_mapped else result
    except (ValueError, TypeError):
        return None


def connection_context(request):
    """Only the loopback gateway may assert its real peer; only named edges may forward CF IPs."""
    peer = address(request.remote_addr)
    if peer is None:
        return {"isLocal": False, "scope": "unknown"}
    if peer.is_loopback:
        peer = address(request.headers.get("X-ControlDeck-Peer-IP"))
        if peer is None:
            return {"isLocal": False, "scope": "unknown"}
    edges = networks(os.environ.get("CONTROLDECK_TRUSTED_EDGE_PROXIES", ""))
    trusted_edge = any(peer in net for net in edges if net.version == peer.version)
    if request.headers.get("CF-Connecting-IP") and not trusted_edge:
        return {"isLocal": False, "scope": "unknown"}
    if trusted_edge:
        peer = address(request.headers.get("CF-Connecting-IP"))
        if peer is None:
            return {"isLocal": False, "scope": "unknown"}
    local = networks(os.environ.get("CONTROLDECK_LOCAL_NETWORKS", DEFAULT_LOCAL))
    if not local:
        return {"isLocal": False, "scope": "unknown"}
    is_local = any(peer in net for net in local if net.version == peer.version)
    return {"isLocal": is_local, "scope": "local" if is_local else "external"}
