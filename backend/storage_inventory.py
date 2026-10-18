"""Read-only storage projections. Credentials, serials and mount options never leave the server."""
import hashlib
import json
import re
from backend.guest_inventory import finite, project_inventory

REMOTE_TYPES = {"pbs", "nfs", "cifs", "smb", "glusterfs", "iscsi", "iscsidirect", "rbd", "cephfs"}
LOCAL_TYPES = {"dir", "lvmthin", "lvm", "zfspool", "btrfs"}


def text(value, limit=200):
    return value[:limit] if isinstance(value, str) and not any(ord(c) < 32 for c in value) else None


def storage_inventory(resources, definitions):
    nodes = project_inventory(resources)["nodes"]
    if not isinstance(definitions, list) or len(definitions) > 500:
        raise ValueError("Ongeldige opslagconfiguratie.")
    configs = {d["storage"]: d for d in definitions if isinstance(d, dict) and isinstance(d.get("storage"), str)}
    rows, seen = [], set()
    for resource in resources:
        if not isinstance(resource, dict) or resource.get("type") != "storage":
            continue
        name, node = resource.get("storage"), resource.get("node")
        if not all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", v) for v in (name, node)) or (node, name) in seen:
            continue
        seen.add((node, name))
        config = configs.get(name, {})
        kind = text(resource.get("plugintype") or config.get("type"), 30) or "unknown"
        shared = resource.get("shared") in (True, 1, "1") or config.get("shared") in (True, 1, "1")
        # Use only backing-target identity, never username/password or a frontend-provided URL.
        fields = {key: config[key] for key in ("server", "export", "share", "pool", "datastore", "portal", "target", "vgname", "thinpool", "path") if isinstance(config.get(key), str)}
        if kind in REMOTE_TYPES:
            fields.pop("path", None)  # Different local mountpoints can refer to the same remote share.
        identity = [kind, fields or {"storage": name}, None if shared else node]
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
        total, used = finite(resource.get("maxdisk")), finite(resource.get("disk"))
        known = total is not None and total > 0 and used is not None and used <= total
        rows.append({"key": key, "name": name, "node": node, "type": kind, "shared": shared,
                     "remote": kind in REMOTE_TYPES, "category": "remote" if kind in REMOTE_TYPES else "local" if kind in LOCAL_TYPES else "unknown",
                     "status": "active" if resource.get("status") in ("available", "active") else "inactive",
                     "total": total if known else None, "used": used if known else None, "available": total - used if known else None})
    return {"nodes": nodes, "storage": sorted(rows, key=lambda r: (r["name"].casefold(), r["node"])), "identityComplete": all(row["name"] in configs for row in rows)}


def storage_snapshot(node, storage, mounts):
    """Whitelisted monitor fields for physical devices, pools and host/container mounts."""
    storage = storage if isinstance(storage, dict) else {}
    disks, pools, rows = [], [], []
    raw_disks = storage.get("disks")
    for disk in raw_disks[:512] if isinstance(raw_disks, list) else []:
        if not isinstance(disk, dict) or not text(disk.get("name"), 80):
            continue
        wear = finite(disk.get("percentage_used"))
        life = finite(disk.get("ssd_life_left"))
        temperature = finite(disk.get("temperature"))
        size = finite(disk.get("size_bytes"))
        disks.append({"name": text(disk["name"], 80), "node": node, "model": text(disk.get("model"), 100),
                      "size": size if size is not None else finite((finite(disk.get("size")) or 0) * 1024) or None,
                      "sizeLabel": text(disk.get("size_formatted"), 30), "health": text(disk.get("health"), 30), "smart": text(disk.get("smart_status"), 30),
                      "standby": disk.get("standby") is True, "temperature": temperature if temperature and not disk.get("standby") else None,
                      "wear": wear if wear is not None else 100 - life if life is not None and life <= 100 else None,
                      "connection": text(disk.get("connection_type"), 20), "rotation": finite(disk.get("rotation_rate"))})
    raw_pools = storage.get("zfs_pools")
    for pool in raw_pools[:128] if isinstance(raw_pools, list) else []:
        if isinstance(pool, dict) and text(pool.get("name")):
            pools.append({"node": node, **{key: text(pool.get(key), 100) for key in ("name", "size", "allocated", "free", "health")}})
    mounts = mounts if isinstance(mounts, dict) else {}
    for group in ("mounts", "lxc_mounts"):
        collection = mounts.get(group)
        for mount in collection[:500] if isinstance(collection, list) else []:
            if not isinstance(mount, dict):
                continue
            source, target = text(mount.get("source"), 512), text(mount.get("target"), 512)
            # Never project mount credentials, including userinfo in a source string.
            if not source or not target or "@" in source or "password=" in source.casefold() or not target.startswith("/"):
                continue
            lxc = str(mount.get("lxc_id", ""))
            rows.append({"node": node, "source": source, "target": target, "type": text(mount.get("fstype"), 20),
                         "scope": "container" if group == "lxc_mounts" else "host", "container": lxc if re.fullmatch(r"[0-9]{1,9}", lxc) else None,
                         "reachable": mount.get("reachable") is True, "readonly": mount.get("readonly") is True, "managed": mount.get("proxmox_managed") is True,
                         **{key: finite(mount.get(raw)) for key, raw in (("total", "total_bytes"), ("used", "used_bytes"), ("available", "available_bytes"))}})
    return {"disks": disks, "pools": pools, "mounts": rows, "disksAvailable": isinstance(raw_disks, list), "mountsAvailable": mounts.get("available") is True}
