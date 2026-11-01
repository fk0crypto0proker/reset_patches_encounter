#!/usr/bin/env python3
"""Safely reset Patches' first encounter in an Elden Ring PC save."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

HEADER_SIZE = 0x300
SLOT_SIZE = 0x280000
SLOT_RECORD_SIZE = 0x10 + SLOT_SIZE
GA_ITEMS_MAX = 0x1400
SUPPORTED_SAVE_VERSION = 262
SUPPORTED_SLOT = 0
ORIGIN_PROBE_START = 50_000
ORIGIN_ZERO_RUN = 64
ORIGIN_MIN_LEAD_ZEROS = 256
ORIGIN_MIN_GAP = 63_000
ORIGIN_MAX_GAP = 66_500
FAMILY_WORLD_STATE_B = 117_192
FAMILY_LEGACY_DUNGEON = 1_500_567
FAMILY_LEGACY_DUNGEON_PICKUP = 1_500_442
LEGACY_SLOT_STRIDE = 1125
LEGACY_ALLOC_SLOTS = {3100: 110}
SIMPLE_FLAGS = {
    1232: False, 3680: False, 3681: False, 3682: True, 3683: False,
    3684: False, 3685: True, 3686: False, 3687: False, 3688: False,
    3689: False, 3690: False, 3691: False, 3692: False, 3693: False,
    3694: False, 3695: False, 9232: False,
}
MAP_FLAGS = {
    31000800: False, 31000801: False, 31000811: False, 31000850: False,
    31007010: False, 31008521: False, 31008820: False, 31009210: False,
}
VERIFY_FLAGS = {
    3682: True, 3683: False, 3685: True, 3691: False,
    31000800: False, 31000801: False, 31000850: False,
}
POST_SURRENDER_FLAGS = {
    3680: True,
    3682: False,
    3683: False,
    31000800: True,
    31000801: False,
    31000850: False,
}


class RepairError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def u32(data: bytes | bytearray, pos: int) -> int:
    return struct.unpack_from("<I", data, pos)[0]


def is_game_running() -> bool:
    if os.name != "nt":
        raise RepairError("This tool currently supports Windows only. / 当前仅支持 Windows。")
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq eldenring.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise RepairError(f"Unable to check the game process: {exc}") from exc
    if result.returncode != 0:
        raise RepairError(
            "无法检查 eldenring.exe 是否运行，已停止。\n"
            f"Could not check the game process; stopped. {result.stderr.strip()}"
        )
    return any(
        any("eldenring.exe" in field.lower() for field in row)
        for row in csv.reader(result.stdout.splitlines())
    )


def require_game_closed() -> None:
    if is_game_running():
        raise RepairError(
            "检测到 eldenring.exe 正在运行。请完全退出游戏后重试。\n"
            "eldenring.exe is running. Fully close the game and try again."
        )


def discover_saves(explicit_save: Path | None) -> list[Path]:
    if explicit_save is not None:
        return [explicit_save.expanduser().resolve()]
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RepairError("APPDATA is unavailable; the save directory cannot be located.")
    root = Path(appdata) / "EldenRing"
    if not root.is_dir():
        raise RepairError(f"未找到存档目录 / Save directory not found: {root}")
    saves = []
    for directory in root.iterdir():
        if directory.is_dir() and directory.name.isdigit():
            save = directory / "ER0000.sl2"
            if save.is_file():
                saves.append(save.resolve())
    return sorted(saves, key=lambda path: path.parent.name)


def validate_save_path(save: Path) -> None:
    if save.name.lower() != "er0000.sl2" or not save.is_file():
        raise RepairError(f"无效的存档路径 / Invalid save path: {save}")
    if not save.parent.name.isdigit() or save.parent.parent.name.lower() != "eldenring":
        raise RepairError(
            "存档必须位于 EldenRing\\<数字 SteamID>\\ER0000.sl2。\n"
            f"Save must be inside EldenRing\\<numeric SteamID>\\ER0000.sl2: {save}"
        )


def prompt_user(message: str) -> str:
    try:
        return input(message).strip()
    except EOFError as exc:
        raise RepairError("当前终端无法读取输入，请在 PowerShell 中运行。/ Interactive input is unavailable.") from exc


def choose_save(saves: list[Path]) -> Path:
    if not saves:
        raise RepairError("未找到 ER0000.sl2。/ No ER0000.sl2 save was found.")
    for save in saves:
        validate_save_path(save)
    if len(saves) == 1:
        return saves[0]
    print("检测到多个 Steam 存档 / Multiple Steam saves found:")
    for index, save in enumerate(saves, 1):
        stat = save.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"  {index}. {save}  ({stat.st_size / 1024 / 1024:.1f} MiB, {modified})")
    while True:
        answer = prompt_user("请选择编号 / Select a number: ")
        if answer.isdigit() and 1 <= int(answer) <= len(saves):
            return saves[int(answer) - 1]
        print("输入无效，请重试。/ Invalid selection, try again.")


def find_ga_items_end(slot: bytes | bytearray) -> int | None:
    if len(slot) < 12:
        return None
    pos = 8 + (0x8 if u32(slot, 0) == 81 else 0x18)
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


def find_flag_list_end(slot: bytes | bytearray, ga_end: int) -> int | None:
    probe = ga_end + ORIGIN_PROBE_START
    if probe + ORIGIN_MIN_LEAD_ZEROS > len(slot) or any(slot[probe:probe + ORIGIN_MIN_LEAD_ZEROS]):
        return None
    pos = probe
    while pos < len(slot) and slot[pos] == 0:
        pos += 1
    if pos >= len(slot):
        return None
    run = 0
    while pos < len(slot):
        if slot[pos] == 0:
            run += 1
            if run >= ORIGIN_ZERO_RUN:
                end = pos + 1 - run
                gap = end - ga_end
                return end if ORIGIN_MIN_GAP <= gap <= ORIGIN_MAX_GAP else None
        else:
            run = 0
        pos += 1
    return None


def set_bit(buf: bytearray, offset: int, bit: int, value: bool) -> tuple[int, int]:
    if not 0 <= offset < len(buf):
        raise RepairError(f"Flag offset is outside the save slot: {offset}")
    before = buf[offset]
    mask = 1 << bit
    buf[offset] = before | mask if value else before & ~mask
    return before, buf[offset]


def map_flag_location(flag_id: int, origin: int) -> tuple[int, int]:
    prefix = flag_id // 10_000
    if prefix not in LEGACY_ALLOC_SLOTS:
        raise RepairError(f"Unsupported map flag: {flag_id}")
    local_id = flag_id % 10_000
    family = FAMILY_LEGACY_DUNGEON if local_id < 7000 else FAMILY_LEGACY_DUNGEON_PICKUP
    offset = origin + family + LEGACY_ALLOC_SLOTS[prefix] * LEGACY_SLOT_STRIDE + local_id // 8
    return offset, 7 - local_id % 8


def resolve_family_base(slot: bytes | bytearray, origin: int, family_constant: int) -> int:
    base = origin + family_constant
    if not 0 <= base < len(slot):
        raise RepairError(f"Flag family is outside the save slot: {family_constant}")
    return base


def prepare_slot(data: bytes, slot_index: int) -> tuple[int, int, bytearray, dict[str, int]]:
    record_start = HEADER_SIZE + slot_index * SLOT_RECORD_SIZE
    slot_start = record_start + 0x10
    slot = bytearray(data[slot_start:slot_start + SLOT_SIZE])
    if len(slot) != SLOT_SIZE:
        raise RepairError("存档槽位不完整。/ The save slot is truncated.")
    version = u32(slot, 0)
    if version != SUPPORTED_SAVE_VERSION:
        raise RepairError(
            f"不支持的存档版本：{version}。当前仅验证版本 {SUPPORTED_SAVE_VERSION}。\n"
            f"Unsupported save version. Only version {SUPPORTED_SAVE_VERSION} is verified."
        )
    if hashlib.md5(slot).digest() != data[record_start:record_start + 0x10]:
        raise RepairError("原存档 MD5 无效，已停止。/ The input slot MD5 is invalid; stopped.")
    ga_end = find_ga_items_end(slot)
    if ga_end is None:
        raise RepairError("无法定位 GaItems。/ Could not locate GaItems.")
    origin = find_flag_list_end(slot, ga_end)
    if origin is None:
        raise RepairError("无法可靠定位旗标 family origin。/ Could not resolve the flag-family origin.")
    families = {
        "origin": origin,
        "world_state": resolve_family_base(slot, origin, FAMILY_WORLD_STATE_B),
        "dungeon": resolve_family_base(slot, origin, FAMILY_LEGACY_DUNGEON),
        "dungeon_pickup": resolve_family_base(slot, origin, FAMILY_LEGACY_DUNGEON_PICKUP),
    }
    required_offsets = [families["world_state"] + flag_id // 8 for flag_id in SIMPLE_FLAGS]
    required_offsets.extend(map_flag_location(flag_id, origin)[0] for flag_id in MAP_FLAGS)
    if any(not 0 <= offset < len(slot) for offset in required_offsets):
        raise RepairError("Required flag positions are outside the save slot; stopped.")
    return record_start, slot_start, slot, families


def flag_value(slot: bytes | bytearray, flag_id: int, families: dict[str, int]) -> bool:
    if flag_id < 1_000_000:
        offset = families["world_state"] + flag_id // 8
        bit = 7 - flag_id % 8
    else:
        offset, bit = map_flag_location(flag_id, families["origin"])
    if not 0 <= offset < len(slot):
        raise RepairError(f"Flag offset is outside the save slot: {flag_id}")
    return bool(slot[offset] & (1 << bit))


def build_candidate(source: bytes, slot_index: int) -> tuple[bytes, dict]:
    data = bytearray(source)
    record_start, slot_start, slot, families = prepare_slot(source, slot_index)
    changes = []
    for flag_id, value in SIMPLE_FLAGS.items():
        offset = families["world_state"] + flag_id // 8
        bit = 7 - flag_id % 8
        before, after = set_bit(slot, offset, bit, value)
        if before != after:
            changes.append({"id": flag_id, "value": value, "slot_offset": offset, "bit": bit})
    for flag_id, value in MAP_FLAGS.items():
        offset, bit = map_flag_location(flag_id, families["origin"])
        before, after = set_bit(slot, offset, bit, value)
        if before != after:
            changes.append({"id": flag_id, "value": value, "slot_offset": offset, "bit": bit})
    data[record_start:record_start + 0x10] = hashlib.md5(slot).digest()
    data[slot_start:slot_start + SLOT_SIZE] = slot
    candidate = bytes(data)

    _, _, verify_slot, verify_families = prepare_slot(candidate, slot_index)
    if verify_families != families:
        raise RepairError("Candidate flag-family origins changed unexpectedly.")
    incorrect = {}
    for flag_id, expected in VERIFY_FLAGS.items():
        actual = flag_value(verify_slot, flag_id, verify_families)
        if actual != expected:
            incorrect[flag_id] = actual
    if incorrect:
        raise RepairError(f"Candidate flag verification failed: {incorrect}")

    allowed = set(range(record_start, record_start + 0x10))
    allowed.update(slot_start + change["slot_offset"] for change in changes)
    actual_changes = {index for index, (old, new) in enumerate(zip(source, candidate)) if old != new}
    if actual_changes - allowed:
        raise RepairError(f"Candidate contains unexpected byte changes: {sorted(actual_changes - allowed)[:10]}")

    report = {
        "slot": slot_index,
        "save_version": u32(verify_slot, 0),
        "flag_families": verify_families,
        "md5_verified": hashlib.md5(verify_slot).digest() == candidate[record_start:record_start + 0x10],
        "effective_changes": changes,
        "verified_flags": {str(flag_id): expected for flag_id, expected in VERIFY_FLAGS.items()},
    }
    return candidate, report


def write_verified(path: Path, data: bytes) -> None:
    with path.open("wb") as file:
        file.write(data)
        file.flush()
        os.fsync(file.fileno())
    if sha256(path) != hashlib.sha256(data).hexdigest().upper():
        raise RepairError(f"File verification failed: {path}")


def create_backup(main_save: Path, backup_save: Path, backup_dir: Path) -> tuple[str, str]:
    partial_dir = backup_dir.with_name(f".{backup_dir.name}.partial")
    partial_dir.mkdir(parents=True, exist_ok=False)
    main_hash = sha256(main_save)
    bak_hash = sha256(backup_save)
    try:
        main_copy = partial_dir / "ER0000.sl2"
        bak_copy = partial_dir / "ER0000.sl2.bak"
        shutil.copy2(main_save, main_copy)
        shutil.copy2(backup_save, bak_copy)
        if (
            sha256(main_save) != main_hash
            or sha256(backup_save) != bak_hash
            or sha256(main_copy) != main_hash
            or sha256(bak_copy) != bak_hash
        ):
            raise RepairError("备份校验失败。/ Backup verification failed.")
        partial_dir.rename(backup_dir)
    except Exception:
        shutil.rmtree(partial_dir, ignore_errors=True)
        raise
    return main_hash, bak_hash


def current_hash(path: Path) -> str:
    try:
        return sha256(path) if path.is_file() else "MISSING"
    except OSError as exc:
        return f"UNREADABLE ({exc})"


def restore_backup(main_save: Path, backup_save: Path, backup_dir: Path,
                   original_main_hash: str, original_bak_hash: str) -> None:
    main_source = backup_dir / "ER0000.sl2"
    bak_source = backup_dir / "ER0000.sl2.bak"
    if sha256(main_source) != original_main_hash or sha256(bak_source) != original_bak_hash:
        raise RepairError("自动备份已改变或损坏，拒绝回滚。/ Backup changed or is corrupt; rollback refused.")

    token = uuid.uuid4().hex
    main_temp = main_save.with_name(f".{main_save.name}.{token}.restore")
    bak_temp = backup_save.with_name(f".{backup_save.name}.{token}.restore")
    try:
        shutil.copy2(main_source, main_temp)
        shutil.copy2(bak_source, bak_temp)
        if sha256(main_temp) != original_main_hash or sha256(bak_temp) != original_bak_hash:
            raise RepairError("回滚临时文件校验失败。/ Rollback temporary-file verification failed.")
        os.replace(main_temp, main_save)
        os.replace(bak_temp, backup_save)
        if sha256(main_save) != original_main_hash or sha256(backup_save) != original_bak_hash:
            raise RepairError("回滚后的存档校验失败。/ Restored save verification failed.")
    finally:
        main_temp.unlink(missing_ok=True)
        bak_temp.unlink(missing_ok=True)


def install_candidate(candidate: bytes, main_save: Path, backup_save: Path, backup_dir: Path,
                      original_main_hash: str, original_bak_hash: str) -> str:
    require_game_closed()
    if sha256(main_save) != original_main_hash or sha256(backup_save) != original_bak_hash:
        raise RepairError("备份后存档发生变化，已停止。/ Save changed after backup; stopped.")
    token = uuid.uuid4().hex
    main_temp = main_save.with_name(f".{main_save.name}.{token}.tmp")
    bak_temp = backup_save.with_name(f".{backup_save.name}.{token}.tmp")
    expected_hash = hashlib.sha256(candidate).hexdigest().upper()
    try:
        write_verified(main_temp, candidate)
        write_verified(bak_temp, candidate)
        require_game_closed()
        if sha256(main_save) != original_main_hash or sha256(backup_save) != original_bak_hash:
            raise RepairError("安装前存档发生变化，已停止。/ Save changed before installation; stopped.")
        os.replace(bak_temp, backup_save)
        require_game_closed()
        if sha256(main_save) != original_main_hash:
            raise RepairError("Main save changed during installation; stopped.")
        os.replace(main_temp, main_save)
        if sha256(main_save) != expected_hash or sha256(backup_save) != expected_hash:
            raise RepairError("安装后哈希验证失败。/ Installed save verification failed.")
    except Exception as install_error:
        try:
            restore_backup(
                main_save, backup_save, backup_dir, original_main_hash, original_bak_hash
            )
        except Exception as rollback_error:
            raise RepairError(
                "严重错误：安装失败且自动回滚未完成。不要启动游戏。\n"
                "CRITICAL: installation and automatic rollback both failed. Do not launch the game.\n"
                f"Main: {main_save} [{current_hash(main_save)}]\n"
                f"BAK:  {backup_save} [{current_hash(backup_save)}]\n"
                f"Backup: {backup_dir}\n"
                f"Install error: {install_error}\nRollback error: {rollback_error}"
            ) from rollback_error
        raise RepairError(
            f"安装失败，但两份原存档已成功恢复。/ Installation failed; both originals were restored.\n{install_error}"
        ) from install_error
    finally:
        main_temp.unlink(missing_ok=True)
        bak_temp.unlink(missing_ok=True)
    return expected_hash


def verify_post_surrender(save: Path) -> None:
    validate_save_path(save)
    print(f"正在验证 / Verifying: {save}")
    _, _, slot, families = prepare_slot(save.read_bytes(), SUPPORTED_SLOT)
    actual = {
        flag_id: flag_value(slot, flag_id, families)
        for flag_id in POST_SURRENDER_FLAGS
    }
    for flag_id, expected in POST_SURRENDER_FLAGS.items():
        print(f"  {flag_id}: {str(actual[flag_id]).lower()} (expected {str(expected).lower()})")
    incorrect = {
        flag_id: value for flag_id, value in actual.items()
        if value != POST_SURRENDER_FLAGS[flag_id]
    }
    if incorrect:
        raise RepairError(
            f"尚未检测到完整的投降写回状态。/ Final surrender state not verified: {incorrect}"
        )
    print("验证成功：帕奇已存活并完成投降写回。/ Verified: Patches survived and the surrender state was saved.")


def run(save: Path, confirmed_app_version: str | None = None) -> Path:
    validate_save_path(save)
    backup_save = save.with_name("ER0000.sl2.bak")
    if not backup_save.is_file():
        raise RepairError(f"缺少 ER0000.sl2.bak / Missing backup save: {backup_save}")
    print(f"存档 / Save: {save}")
    for label, path in (("Main", save), ("BAK", backup_save)):
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{label}: {path}")
        print(f"  {stat.st_size / 1024 / 1024:.1f} MiB | {modified} | SHA-256 {sha256(path)}")
    print("注意：.bak 会先被单独备份，再由主档生成的修复候选覆盖。")
    print("Note: .bak is backed up separately, then replaced with the candidate built from Main.")
    print("脚本会验证 save version 262 和 Slot 0，但无法自动读取标题画面的 App Ver。")
    print("The script verifies save version 262 and Slot 0, but cannot detect the title-screen App Ver.")
    version = confirmed_app_version or prompt_user(
        "请先确认标题画面显示 App Ver. 1.17.2，然后输入 1.17.2：\n"
        "Confirm the title screen says App Ver. 1.17.2, then type 1.17.2: "
    )
    if version != "1.17.2":
        raise RepairError("未确认 App Ver. 1.17.2，已取消。/ App Ver. 1.17.2 was not confirmed; cancelled.")

    print("正在验证主档与 .bak / Validating the main save and .bak...")
    prepare_slot(save.read_bytes(), SUPPORTED_SLOT)
    prepare_slot(backup_save.read_bytes(), SUPPORTED_SLOT)

    root = save.parent.parent
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = root / "PatchesEncounterResetBackups" / f"{timestamp}-{uuid.uuid4().hex[:8]}"
    print("[1/4] 正在备份并验证 / Backing up and verifying...")
    original_main_hash, original_bak_hash = create_backup(save, backup_save, backup_dir)
    print("[2/4] 正在生成并检查候选存档 / Building and checking candidate...")
    candidate, report = build_candidate(save.read_bytes(), SUPPORTED_SLOT)
    candidate_path = backup_dir / "ER0000_patches_reset.sl2"
    write_verified(candidate_path, candidate)
    report.update({
        "source": str(save), "backup_directory": str(backup_dir),
        "source_sha256": original_main_hash, "source_bak_sha256": original_bak_hash,
        "candidate_sha256": sha256(candidate_path), "confirmed_app_version": version,
    })
    (backup_dir / "repair_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("[3/4] 正在安装主档与 .bak / Installing both save files...")
    installed_hash = install_candidate(
        candidate, save, backup_save, backup_dir, original_main_hash, original_bak_hash
    )
    print("[4/4] 修复完成 / Repair completed")
    print(f"备份目录 / Backup: {backup_dir}")
    print(f"安装 SHA-256: {installed_hash}")
    print("完成前不要启动游戏。现在可前往蒙流洞窟，打到约半血后立即停手。")
    print("Do not launch the game before completion. Now enter Murkwater Cave and stop near half health.")
    return backup_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset Patches' first Murkwater Cave encounter safely.")
    parser.add_argument("--save", type=Path, help="Optional path to ER0000.sl2; normally found automatically.")
    parser.add_argument("--assume-app-version", choices=["1.17.2"], help="Caller assertion for the title-screen App Ver; the EXE is not inspected.")
    parser.add_argument("--verify", action="store_true", help="Read only: verify the saved post-surrender state.")
    args = parser.parse_args()
    exit_code = 0
    try:
        require_game_closed()
        save = choose_save(discover_saves(args.save))
        if args.verify:
            verify_post_surrender(save)
        else:
            run(save, args.assume_app_version)
    except (RepairError, OSError, ValueError, EOFError) as exc:
        print(f"\n错误 / ERROR:\n{exc}", file=sys.stderr)
        exit_code = 1
    if sys.stdin.isatty():
        try:
            input("\n按回车键退出 / Press Enter to exit...")
        except EOFError:
            pass
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
