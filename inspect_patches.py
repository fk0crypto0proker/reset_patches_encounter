#!/usr/bin/env python3
"""Read Patches-related event flags from an Elden Ring PC save. Never writes."""

import hashlib
import json
import struct
import sys
from pathlib import Path

HEADER_SIZE = 0x300
SLOT_SIZE = 0x280000
SLOT_RECORD_SIZE = 0x10 + SLOT_SIZE
SLOT_COUNT = 10
GA_ITEMS_MAX = 0x1400
ORIGIN_PROBE_START = 50_000
ORIGIN_ZERO_RUN = 64
ORIGIN_MIN_LEAD_ZEROS = 256
ORIGIN_MIN_GAP = 55_000
ORIGIN_MAX_GAP = 80_000
FAMILY_LEGACY_DUNGEON = 1_500_567
SIMPLE_FLAGS_BASE_DELTA = 145_877
LEGACY_SLOT_STRIDE = 1125
LEGACY_ALLOC_SLOTS = {3100: 110}
POSITIVE_VALIDATION_FLAGS = [
    (2725, 7, 1), (2725, 6, 1), (3262, 3, 1), (3262, 2, 1),
    (3262, 1, 2), (3263, 7, 2), (3263, 5, 2),
]
NEGATIVE_VALIDATION_FLAGS = [
    (3277, 0), (3278, 7), (3278, 6), (3287, 3), (3287, 2), (3293, 5),
]

PATCHES_NPC_FLAGS = {
    3680: "Patches alive, friendly",
    3681: "Patches alive, hostile",
    3682: "Patches alive, initial boss mode",
    3683: "Patches dead",
    3684: "Patches unknown state",
    3685: "Patches Limgrave quest start",
    3686: "Patches at Murkwater Cave",
    3687: "Patches at Scenic Isle",
    3688: "Patches quest state 3688",
    3689: "Patches quest state 3689",
    3690: "Patches quest state 3690",
    3691: "Patches quest state 3691",
    3692: "Patches Limgrave last quest step",
    3693: "Patches quest state 3693",
    3694: "Patches crouch gesture state",
    3695: "Patches quest state 3695",
}

PATCHES_FLAGS = {
    31000040: "Murkwater Cave map event 0040",
    31000800: "Patches encounter/boss completion",
    31000801: "Patches death",
    31000850: "Patches alternate battle completion",
}


def u32(data: bytes, pos: int) -> int:
    return struct.unpack_from("<I", data, pos)[0]


def find_ga_items_end(slot: bytes):
    if len(slot) < 12:
        return None
    version = u32(slot, 0)
    header_padding = 0x8 if version == 81 else 0x18
    pos = 8 + header_padding
    for _ in range(GA_ITEMS_MAX):
        if pos + 8 > len(slot):
            return None
        pos += 4
        item_id = u32(slot, pos)
        pos += 4
        if item_id in (0, 0xFFFFFFFF):
            continue
        kind = item_id & 0xF0000000
        if kind == 0:
            pos += 13
        elif kind == 0x10000000:
            pos += 8
        if pos > len(slot):
            return None
    return pos


def find_flag_list_end(slot: bytes, ga_end: int):
    probe = ga_end + ORIGIN_PROBE_START
    if probe + ORIGIN_MIN_LEAD_ZEROS > len(slot):
        return None
    if any(slot[probe : probe + ORIGIN_MIN_LEAD_ZEROS]):
        return None
    i = probe
    while i < len(slot) and slot[i] == 0:
        i += 1
    if i >= len(slot):
        return None
    run = 0
    while i < len(slot):
        if slot[i] == 0:
            run += 1
            if run >= ORIGIN_ZERO_RUN:
                end = i + 1 - run
                gap = end - ga_end
                return end if ORIGIN_MIN_GAP <= gap <= ORIGIN_MAX_GAP else None
        else:
            run = 0
        i += 1
    return None


def detect_event_flags_start(slot: bytes, ga_end: int):
    lo = ga_end + 30_000
    hi = min(ga_end + 45_000, len(slot) - 4096)
    best = None
    for offset in range(lo, hi):
        tier1 = 0
        positive = 0
        negative = 0
        for rel, bit, tier in POSITIVE_VALIDATION_FLAGS:
            if slot[offset + rel] & (1 << bit):
                positive += 1
                if tier == 1:
                    tier1 += 1
        if tier1 < 2:
            continue
        for rel, bit in NEGATIVE_VALIDATION_FLAGS:
            if not slot[offset + rel] & (1 << bit):
                negative += 1
        score = (tier1, positive, negative)
        if best is None or score > best[0]:
            best = (score, offset)
    return None if best is None else {"offset": best[1], "tier1": best[0][0], "positive": best[0][1], "negative": best[0][2]}


def simple_flag(slot: bytes, ef_start: int, flag_id: int):
    offset = ef_start + SIMPLE_FLAGS_BASE_DELTA + flag_id // 8
    bit = 7 - flag_id % 8
    return offset, bit, bool(slot[offset] & (1 << bit))


def legacy_flag_location(flag_id: int, origin: int):
    prefix = flag_id // 10_000
    slot_no = LEGACY_ALLOC_SLOTS.get(prefix)
    if slot_no is None or flag_id % 10_000 >= 7000:
        return None
    rel_byte = slot_no * LEGACY_SLOT_STRIDE + (flag_id % 10_000) // 8
    bit = 7 - (flag_id % 8)
    return origin + FAMILY_LEGACY_DUNGEON + rel_byte, bit


def inspect(path: Path):
    data = path.read_bytes()
    result = {"save": str(path), "size": len(data), "slots": []}
    for index in range(SLOT_COUNT):
        record_start = HEADER_SIZE + index * SLOT_RECORD_SIZE
        checksum = data[record_start : record_start + 0x10]
        slot = data[record_start + 0x10 : record_start + SLOT_RECORD_SIZE]
        if len(slot) != SLOT_SIZE:
            continue
        version = u32(slot, 0)
        md5_valid = hashlib.md5(slot).digest() == checksum
        if version == 0 and not any(slot[:4096]):
            continue
        entry = {"slot": index, "version": version, "md5_valid": md5_valid}
        ga_end = find_ga_items_end(slot)
        entry["ga_items_end"] = ga_end
        ef_detection = detect_event_flags_start(slot, ga_end) if ga_end is not None else None
        entry["event_flags_detection"] = ef_detection
        if ef_detection is not None:
            entry["simple_flags_base"] = ef_detection["offset"] + SIMPLE_FLAGS_BASE_DELTA
            entry["npc_flags"] = []
            for flag_id, name in PATCHES_NPC_FLAGS.items():
                offset, bit, value = simple_flag(slot, ef_detection["offset"], flag_id)
                entry["npc_flags"].append({
                    "id": flag_id,
                    "name": name,
                    "set": value,
                    "slot_offset": offset,
                    "file_offset": record_start + 0x10 + offset,
                    "bit": bit,
                })
        list_end = find_flag_list_end(slot, ga_end) if ga_end is not None else None
        entry["flag_list_end"] = list_end
        if list_end is None:
            entry["error"] = "event-flag origin could not be resolved"
            result["slots"].append(entry)
            continue
        entry["origin_gap"] = list_end - ga_end
        entry["flags"] = []
        for flag_id, name in PATCHES_FLAGS.items():
            location = legacy_flag_location(flag_id, list_end)
            if location is None:
                continue
            offset, bit = location
            value = bool(slot[offset] & (1 << bit)) if offset < len(slot) else None
            entry["flags"].append({
                "id": flag_id,
                "name": name,
                "set": value,
                "slot_offset": offset,
                "file_offset": record_start + 0x10 + offset,
                "bit": bit,
            })
        result["slots"].append(entry)
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: inspect_patches.py ER0000.sl2")
    print(json.dumps(inspect(Path(sys.argv[1])), indent=2, ensure_ascii=False))
