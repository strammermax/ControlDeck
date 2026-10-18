"""Bounded hardware presentation projection; serials and raw configuration stay private."""
import math
from backend.guest_inventory import finite
from backend.storage_inventory import text


def temperature(value):
    return value if type(value) in (int, float) and math.isfinite(value) and -100 <= value <= 300 else None


def hardware_snapshot(node, value):
    value = value if isinstance(value, dict) else {}
    cpu = value.get("cpu") if isinstance(value.get("cpu"), dict) else {}
    board = value.get("motherboard") if isinstance(value.get("motherboard"), dict) else {}
    bios = board.get("bios") or value.get("bios")
    bios = bios if isinstance(bios, dict) else {}
    memory, sensors, gpus, pci, usb, fans, power = [], [], [], [], [], [], []
    def collection(key, maximum=512):
        rows = value.get(key)
        return [r for r in rows[:maximum] if isinstance(r, dict)] if isinstance(rows, list) else []
    for index, row in enumerate(collection("memory_modules", 256)):
        size = finite(row.get("size"))
        memory.append({"node": node, "id": str(index), "slot": text(row.get("slot"), 100), "size": finite(size * 1024) if size is not None else None,
                       **{key: text(row.get(key), 100) for key in ("type", "configured_speed", "max_speed", "manufacturer")}})
    for index, row in enumerate(collection("temperatures")):
        kind = row.get("type")
        if kind not in ("cpu", "gpu", "nvme", "hdd", "ssd", "pci", "other"):
            name = str(row.get("name", "")).lower()
            kind = "cpu" if any(s in name for s in ("cpu", "core", "package")) else "gpu" if "gpu" in name else "nvme" if "nvme" in name else "other"
        sensors.append({"node": node, "id": str(index), "kind": kind, "name": text(row.get("model") or row.get("name"), 160),
                        "adapter": text(row.get("device") or row.get("adapter"), 120),
                        **{key: temperature(row.get(key)) for key in ("current", "high", "critical")}})
    for row in collection("gpus", 128):
        gpus.append({"node": node, **{key: text(row.get(raw), 160) for key, raw in (("name", "name"), ("vendor", "vendor"), ("slot", "slot"), ("driver", "pci_driver"), ("type", "type"))}})
    for row in collection("pci_devices"):
        pci.append({"node": node, **{key: text(row.get(key), 200) for key in ("slot", "device", "vendor", "class", "driver", "kernel_module")}})
    for row in collection("usb_devices"):
        usb.append({"node": node, **{key: text(row.get(key), 160) for key in ("bus_device", "name", "vendor", "class_label", "driver", "speed_label")}})
    for row in collection("fans", 128):
        fans.append({"node": node, "name": text(row.get("name"), 100), "speed": finite(row.get("speed")), "unit": text(row.get("unit"), 20)})
    meter = value.get("power_meter")
    if isinstance(meter, dict):
        power.append({"node": node, "name": text(meter.get("name"), 100), "watts": finite(meter.get("watts"))})
    return {"hardwareAvailable": bool(cpu or board), "cpu": {**{key: text(cpu.get(key), 160) for key in ("model", "l3_cache", "virtualization")},
            **{key: finite(cpu.get(key)) for key in ("sockets", "cores_per_socket", "total_threads")}},
            "motherboard": {**{key: text(board.get(key), 160) for key in ("manufacturer", "model")}, "bios": {key: text(bios.get(key), 160) for key in ("vendor", "version", "date")}},
            "memory": memory, "sensors": sensors, "gpus": gpus, "pci": pci, "usb": usb, "fans": fans, "power": power,
            "memoryAvailable": isinstance(value.get("memory_modules"), list), "sensorsAvailable": isinstance(value.get("temperatures"), list)}
