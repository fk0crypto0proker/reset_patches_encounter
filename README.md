# Elden Ring Patches Encounter Reset

[中文](#中文) | [English](#english)

A one-file save repair tool for replaying Patches' first Murkwater Cave encounter after accidentally killing him.

---

## 中文

### 功能

误杀帕奇后，重置蒙流洞窟初遇：

```text
打开宝箱 -> 帕奇出现 -> 战斗 -> 约半血停手 -> 帕奇投降并存活
```

**仅验证以下环境：**

- Windows / Steam
- 标题画面 App Ver. 1.17.2
- 存档版本 262
- 第一个角色槽位（Slot 0）
- Python 3.12

其他版本或角色槽位请勿使用。

### 使用方法

1. 在游戏标题画面确认显示 **App Ver. 1.17.2**。
2. 完全退出游戏。脚本检测到 `eldenring.exe` 时会停止。
3. 安装 [Python](https://www.python.org/downloads/windows/)，安装时勾选 **Add Python to PATH**。
4. 下载本项目中的 `reset_patches_encounter.py`。
5. 在脚本文件夹打开 PowerShell，运行：

```powershell
python .\reset_patches_encounter.py
```

按提示输入 `1.17.2`。如果有多个 Steam 账号，再选择正确的存档。

脚本会自动查找并验证存档、分别备份主档和 `.bak`、生成修复文件、自检并完成替换。**出现 `[3/4]` 后，不要启动游戏、强制关闭脚本或关闭电脑，直到显示 `[4/4]`。**

### 游戏内验证

1. 启动游戏，进入第一个角色。
2. 前往蒙流洞窟并打开宝箱。
3. 将帕奇打到约半血后立即停手。
4. 等待投降台词，确认帕奇存活。
5. 退出到标题画面，再完全退出游戏。
6. 运行只读验证：

```powershell
python .\reset_patches_encounter.py --verify
```

看到“验证成功”才表示投降状态已经写入磁盘。

### 备份与回滚

备份目录会显示在脚本结果中，也可在这里找到：

```text
%APPDATA%\EldenRing\PatchesEncounterResetBackups\<时间戳>
```

需要回滚时，完全退出游戏，先确认备份中同时存在 `ER0000.sl2` 和 `ER0000.sl2.bak`，并用 `Get-FileHash` 与 `repair_report.json` 中的两个原始 SHA-256 核对。然后把两份文件**一起**复制回原来的数字 SteamID 存档目录，复制后再次比较哈希。

### 原理

只清除普通 Boss 完成状态只能重置宝箱，帕奇仍可能保持死亡状态。本工具会为当前存档动态定位旗标 family，重置帕奇的 NPC、宝箱、战斗和对话状态，并重新计算角色槽位 MD5。它不会回滚整个世界，也不会复活其他 NPC。

### 风险

- 修改存档始终存在风险，请保留自动备份。
- 建议暂时关闭 Steam 云同步，并离线完成第一次测试。
- 脚本只能自动检查存档版本；标题画面的 App Ver. 必须由你确认。
- 本工具不修改游戏 EXE，但无法保证不存在在线服务风险。

---

## English

### What it does

Resets Patches' first Murkwater Cave encounter after an accidental kill:

```text
Open chest -> Patches appears -> Fight -> Stop near half health -> Patches surrenders and survives
```

**Tested only with:**

- Windows / Steam
- Title-screen App Ver. 1.17.2
- Save version 262
- First character slot (Slot 0)
- Python 3.12

Do not use it with other versions or character slots.

### Usage

1. Confirm that the title screen shows **App Ver. 1.17.2**.
2. Fully close the game. The script stops if `eldenring.exe` is running.
3. Install [Python](https://www.python.org/downloads/windows/) and enable **Add Python to PATH**.
4. Download `reset_patches_encounter.py` from this project.
5. Open PowerShell in the script folder and run:

```powershell
python .\reset_patches_encounter.py
```

Type `1.17.2` when asked. If multiple Steam accounts are found, select the correct save.

The script automatically finds and validates the save, backs up the main file and `.bak` separately, builds and verifies the repair, and installs both files. **After `[3/4]` appears, do not launch the game, force-close the script, or shut down the PC until `[4/4]` is shown.**

### Verify in game

1. Launch the game and load the first character.
2. Enter Murkwater Cave and open the chest.
3. Stop attacking Patches at approximately half health.
4. Wait for the surrender dialogue and confirm that he survives.
5. Return to the title screen, then fully close the game.
6. Run the read-only verification:

```powershell
python .\reset_patches_encounter.py --verify
```

The surrender state is confirmed on disk only when the script reports success.

### Backup and rollback

The script prints the backup directory. Backups are also stored under:

```text
%APPDATA%\EldenRing\PatchesEncounterResetBackups\<timestamp>
```

To roll back, fully close the game. Confirm that the backup contains both `ER0000.sl2` and `ER0000.sl2.bak`, then use `Get-FileHash` to compare them with the two original SHA-256 values in `repair_report.json`. Copy **both** files into the original numeric SteamID save directory and compare the hashes again.

### How it works

Clearing only the generic boss-completion state can reset the chest while leaving Patches dead. This tool dynamically resolves the flag families for the current save, resets the related NPC, chest, battle, and dialogue states, and recalculates the character-slot MD5. It does not roll back the entire world or revive unrelated NPCs.

### Risks

- Save editing always carries risk. Keep the automatic backup.
- Temporarily disable Steam Cloud and perform the first test offline.
- The script can verify only the save version; you must confirm the title-screen App Ver.
- The tool does not modify the game executable, but no guarantee can be made regarding online-service risk.

---

## Disclaimer

This project is not affiliated with FromSoftware, Bandai Namco Entertainment, or Valve. `ELDEN RING` and related names belong to their respective owners. The software is provided as-is; users are responsible for save corruption, progress issues, cloud conflicts, and online-service risks.
