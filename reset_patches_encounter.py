#!/usr/bin/env python3
"""Create a separate save candidate with Patches' first encounter reset."""

import argparse
import hashlib
import json
from pathlib import Path

from inspect_patches import (
    FAMILY_LEGACY_DUNGEON,
    GA_ITEMS_MAX,
    HEADER_SIZE,
    LEGACY_ALLOC_SLOTS,
    LEGACY_SLOT_STRIDE,
    SLOT_RECORD_SIZE,
    SLOT_SIZE,
    detect_event_flags_start,
    find_flag_list_end,
    find_ga_items_end,
)

FAMILY_LEGACY_DUNGEON_PICKUP = 1_500_442

# Low-numbered flags live in a second flag bank inside the EventFlags blob.
# This delta is stable across the pre-repair and game-rewritten 1.17.2 saves.
SIMPLE_FLAGS_BASE_DELTA = 145_877

# Reset to the state controller's initial boss-mode state.
SIMPLE_FLAGS = {
    1232: False,
    3680: False,
    3681: False,
    3682: True,
    3683: False,
    3684: False,
    3685: True,
    3686: False,
    3687: False,
    3688: False,
    3689: False,
    3690: False,
    3691: False,
    3692: False,
    3693: False,
    3694: False,
    3695: False,
    9232: False,
    61232: False,
    520320: False,
}

# Map-local encounter state. IDs >= 7000 use the second allocated family.
MAP_FLAGS = {
    31000800: False,  # encounter/boss defeated
    31000801: False,  # map-local death state
    31000811: False,  # arena music state
    31000850: False,  # alternate completion state
    31007010: False,  # bait chest item taken
    31008521: False,  # bait chest opened
    31008820: False,  # Patches aggression
    31009210: False,  # Patches dialogue
}


def set_bit(buf: bytearray, offset: int, bit: int, value: bool):
    before = buf[offset]
    mask = 1 << bit
    buf[offset] = before | mask if value else before & ~mask
    return before, buf[offset]


def map_flag_location(flag_id: int, origin: int):
    prefix = flag_id // 10_000
    alloc_slot = LEGACY_ALLOC_SLOTS[prefix]
    local_id = flag_id % 10_000
    family = FAMILY_LEGACY_DUNGEON if local_id < 7000 else FAMILY_LEGACY_DUNGEON_PICKUP
    rel = alloc_slot * LEGACY_SLOT_STRIDE + local_id // 8
    bit = 7 - local_id % 8
    return origin + family + rel, bit


def reset(input_path: Path, output_path: Path, slot_index: int):
    data = bytearray(input_path.read_bytes())
    record_start = HEADER_SIZE + slot_index * SLOT_RECORD_SIZE
    slot_start = record_start + 0x10
    slot = bytearray(data[slot_start : slot_start + SLOT_SIZE])
    if len(slot) != SLOT_SIZE:
        raise ValueError("save slot is truncated")

    original_md5 = bytes(data[record_start : record_start + 0x10])
    if hashlib.md5(slot).digest() != original_md5:
        raise ValueError("input slot MD5 is invalid")

    ga_end = find_ga_items_end(slot)
    if ga_end is None:
        raise ValueError("GaItems end could not be resolved")
    ef = detect_event_flags_start(slot, ga_end)
    if ef is None or ef["tier1"] < 2:
        raise ValueError("EventFlags start could not be resolved confidently")
    list_end = find_flag_list_end(slot, ga_end)
    if list_end is None:
        raise ValueError("event-flag family origin could not be resolved")

    changes = []
    simple_base = ef["offset"] + SIMPLE_FLAGS_BASE_DELTA
    for flag_id, value in SIMPLE_FLAGS.items():
        offset = simple_base + flag_id // 8
        bit = 7 - flag_id % 8
        before, after = set_bit(slot, offset, bit, value)
        changes.append({"id": flag_id, "family": "simple", "value": value,
                        "slot_offset": offset, "bit": bit,
                        "byte_before": before, "byte_after": after})

    for flag_id, value in MAP_FLAGS.items():
        offset, bit = map_flag_location(flag_id, list_end)
        before, after = set_bit(slot, offset, bit, value)
        changes.append({"id": flag_id, "family": "map", "value": value,
                        "slot_offset": offset, "bit": bit,
                        "byte_before": before, "byte_after": after})

    new_md5 = hashlib.md5(slot).digest()
    data[record_start : record_start + 0x10] = new_md5
    data[slot_start : slot_start + SLOT_SIZE] = slot
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)

    verify = output_path.read_bytes()
    out_slot = verify[slot_start : slot_start + SLOT_SIZE]
    verified = hashlib.md5(out_slot).digest() == verify[record_start : record_start + 0x10]
    changed = [c for c in changes if c["byte_before"] != c["byte_after"]]
    return {
        "input": str(input_path),
        "output": str(output_path),
        "slot": slot_index,
        "event_flags_start": ef,
        "simple_flags_base": simple_base,
        "flag_list_end": list_end,
        "old_md5": original_md5.hex(),
        "new_md5": new_md5.hex(),
        "md5_verified": verified,
        "effective_changes": changed,
        "requested_flags": len(changes),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--slot", type=int, default=0)
    args = parser.parse_args()
    print(json.dumps(reset(args.input, args.output, args.slot), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
