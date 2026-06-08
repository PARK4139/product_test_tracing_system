from __future__ import annotations

import re

CANONICAL_TOPOLOGIES = {
    "1HDC", "1HDC_1ROUTER", "1HDR_1CABLE_1HIIS", "1HDR_1ROUTER", "1HDR_1ROUTER_1HDC",
    "1HDR_25ROUTER", "1HDR_25ROUTER_1HDC", "1HLM_1ROUTER", "1HLM_1ROUTER_1HDR",
    "1HLM_1ROUTER_4HDR", "1HLM_25ROUTER", "1HLM_25ROUTER_1HDR", "1HRK_1ROUTER",
    "1HRK_1ROUTER_1HDR", "1HRK_1ROUTER_1HTR_1HLM_4HDR", "1HRK_1ROUTER_3HDR",
    "1HRK_1ROUTER_4HDR", "1HRK_25ROUTER", "1HRK_25ROUTER_1HDR", "1HTR_1ROUTER",
    "1HTR_1ROUTER_1HDR", "1HTR_1ROUTER_2HDR", "1HTR_25ROUTER", "1HTR_25ROUTER_1HDR",
    "2HDR_1ROUTER", "4HDR_1ROUTER", "4HDR_1ROUTER_1HDC", "4HDR_1ROUTER_1HIIS",
}
DEVICE_ORDER = ["HRK", "HTR", "HLM", "HDR", "HDC", "HIIS"]
TOKEN_PATTERN = re.compile(r"(\d*)(AP|ROUTER|HRK|HTR|HLM|HDR|HDC|HIIS|CABLE)")


def normalize_combo(raw: str | None) -> str:
    if not raw:
        return "UNCLASSIFIED"
    compact = str(raw).strip().replace(" ", "")
    if compact in {"", "TBD", "VARIOUS_CONNECTIONS"}:
        return "UNCLASSIFIED"
    compact = compact.replace("1AP_1HDC", "1HDC_1ROUTER") if compact == "1AP_1HDC" else compact
    parts = TOKEN_PATTERN.findall(compact)
    if not parts:
        return "UNCLASSIFIED"
    router_count = 0
    cable_count = 0
    device_counts: dict[str, int] = {}
    for count_str, token in parts:
        count = int(count_str) if count_str else 1
        if token in {"AP", "ROUTER"}:
            router_count += count
        elif token == "CABLE":
            cable_count += count
        else:
            device_counts[token] = device_counts.get(token, 0) + count
    ordered_devices = []
    if cable_count:
        ordered_devices.append(f"{cable_count}CABLE")
    for token in DEVICE_ORDER:
        if token in device_counts:
            ordered_devices.append(f"{device_counts[token]}{token}")
    if router_count and ordered_devices:
        normalized = "_".join([ordered_devices[0], f"{router_count}ROUTER", *ordered_devices[1:]])
    elif router_count:
        normalized = f"{router_count}ROUTER"
    else:
        normalized = "_".join(ordered_devices)
    return normalized if normalized in CANONICAL_TOPOLOGIES else "UNCLASSIFIED"
