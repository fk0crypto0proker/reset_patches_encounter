# Elden Ring Patches Encounter Reset

[中文](#中文) | [English](#english)

Reset Patches' first encounter in Murkwater Cave after accidentally killing him, allowing the chest, fight, surrender, and friendly outcome to be played again.

> This is not a full save rollback or a general NPC revival tool.

---

## 中文

### 功能与支持范围

修复误杀帕奇后的蒙流洞窟初遇状态，让玩家重新完成：

```text
打开宝箱 -> 帕奇出现 -> Boss 战 -> 约半血停手 -> 帕奇投降并存活
```

| 项目 | 已验证环境 |
| --- | --- |
| 平台 | Windows PC / Steam |
| 游戏版本 | App Ver. 1.17.2 |
| 存档版本 | 262 |
| 角色槽位 | Slot 0（`--slot 0`） |
| Python | 3.12，仅使用标准库 |

其他版本、平台和角色槽位尚未完成实际验证。

### 风险

- 操作前必须完全退出游戏，确认 `eldenring.exe` 已结束。
- 必须同时备份 `ER0000.sl2` 和 `ER0000.sl2.bak`。
- 建议暂时关闭 Steam 云同步，并离线完成首次测试。
- 不要直接覆盖原存档，应先生成并检查候选文件。
- 本工具不修改游戏 EXE，但无法保证修改存档不存在在线服务风险。
- 如果游戏或存档版本与已验证环境不同，请停止使用。

### 原理

普通 Boss 复活工具通常只清除地图完成位 `31000800`，因此宝箱可能重新可用，但帕奇仍不出现。

在 1.17.2 的 `m31_00_00_00` 事件脚本中，事件 `31002810` 会检查：

- `31000800`：初遇完成
- `3683`：帕奇死亡
- `3691`：帕奇后续状态之一

任一条件为真时，游戏都会禁用帕奇实体。即使清除了 `31000800`，只要 `3683` 或 `3691` 仍为真，游戏还会重新设置完成位。

本工具会动态定位 EventFlags，而不是依赖固定文件绝对偏移，然后重置帕奇的 NPC 状态、蒙流洞窟初遇、宝箱、战斗、对话及相关奖励状态，并重新计算目标角色槽位的 MD5。

它不会让整个世界回到十分钟前，也不会恢复其他 NPC。

### 使用教程

#### 1. 准备环境

将两个脚本放在同一目录：

```text
inspect_patches.py
reset_patches_encounter.py
```

检查 Python：

```powershell
python --version
```

#### 2. 找到存档并退出游戏

Steam 版默认存档位置：

```text
%APPDATA%\EldenRing\<SteamID>\ER0000.sl2
```

确认游戏未运行：

```powershell
Get-Process eldenring -ErrorAction SilentlyContinue
```

命令没有输出才表示进程已经结束。

#### 3. 备份

把 `<SteamID>` 替换为自己的数字目录：

```powershell
$saveDir = "$env:APPDATA\EldenRing\<SteamID>"
$backupDir = Join-Path $env:APPDATA ("EldenRing\patches-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $backupDir
Copy-Item "$saveDir\ER0000.sl2" "$backupDir\ER0000.sl2"
Copy-Item "$saveDir\ER0000.sl2.bak" "$backupDir\ER0000.sl2.bak"
```

确认备份目录中同时存在两份文件。建议使用 `Get-FileHash` 比较原文件与备份的 SHA-256。

#### 4. 检查原存档

```powershell
python .\inspect_patches.py "$env:APPDATA\EldenRing\<SteamID>\ER0000.sl2"
```

`md5_valid` 必须为 `true`。如果 MD5 无效或工具无法定位 EventFlags，请停止操作。

#### 5. 生成候选存档

```powershell
python .\reset_patches_encounter.py `
  "$env:APPDATA\EldenRing\<SteamID>\ER0000.sl2" `
  ".\ER0000_patches_reset.sl2" `
  --slot 0
```

脚本不会自动替换正式存档。输出报告中的 `md5_verified` 必须为 `true`。

#### 6. 检查候选存档

```powershell
python .\inspect_patches.py .\ER0000_patches_reset.sl2
```

预期关键状态：

```text
3682 = true
3683 = false
3685 = true
3691 = false
31000800 = false
31000801 = false
31000850 = false
md5_valid = true
```

#### 7. 安装候选存档

再次确认游戏已退出且备份存在，然后同时替换主档和 `.bak`：

```powershell
$saveDir = "$env:APPDATA\EldenRing\<SteamID>"
Copy-Item .\ER0000_patches_reset.sl2 "$saveDir\ER0000.sl2" -Force
Copy-Item .\ER0000_patches_reset.sl2 "$saveDir\ER0000.sl2.bak" -Force
```

如果任一复制失败，不要启动游戏，立即恢复两份备份。

#### 8. 游戏内验证

1. 进入蒙流洞窟并打开宝箱。
2. 确认帕奇出现并进入 Boss 战。
3. 打到约半血后立即停止攻击。
4. 等待投降台词和战斗结束。
5. 确认帕奇存活且可以友好对话。
6. 退出到标题画面，让游戏写回存档。
7. 完全退出游戏后再次运行检查器。

成功写回后的实测状态：

```text
3680 = true
3682 = false
3683 = false
31000800 = true
31000801 = false
31000850 = false
```

### 回滚

完全退出游戏后，把备份目录中的两个文件一起恢复：

```powershell
$saveDir = "$env:APPDATA\EldenRing\<SteamID>"
$backupDir = "<你的备份目录>"
Copy-Item "$backupDir\ER0000.sl2" "$saveDir\ER0000.sl2" -Force
Copy-Item "$backupDir\ER0000.sl2.bak" "$saveDir\ER0000.sl2.bak" -Force
```

不要只恢复其中一个文件，也不要在游戏运行时回滚。

---

## English

### Features and compatibility

Repairs Patches' first encounter in Murkwater Cave after an accidental kill, allowing the player to replay:

```text
Open chest -> Patches appears -> Boss fight -> Stop near half health -> Surrender and survival
```

| Item | Tested environment |
| --- | --- |
| Platform | Windows PC / Steam |
| Game version | App Ver. 1.17.2 |
| Save version | 262 |
| Character slot | Slot 0 (`--slot 0`) |
| Python | 3.12, standard library only |

Other versions, platforms, and character slots have not been fully tested.

### Risks

- Fully close the game and confirm that `eldenring.exe` is no longer running.
- Back up both `ER0000.sl2` and `ER0000.sl2.bak`.
- Temporarily disable Steam Cloud and perform the first test offline.
- Generate and inspect a separate candidate before replacing the live save.
- The tool does not modify the game executable, but no guarantee can be made regarding online-service risk.
- Stop if your game or save version differs from the tested environment.

### How it works

Generic boss-revival tools often clear only `31000800`, the map completion flag. This can reset the chest while Patches remains absent.

In the App Ver. 1.17.2 `m31_00_00_00` event script, event `31002810` checks:

- `31000800`: encounter completed
- `3683`: Patches dead
- `3691`: a later Patches state

If any condition is enabled, the game disables Patches' entity. If `31000800` is cleared while `3683` or `3691` remains enabled, the game can set the completion flag again.

The tool dynamically locates EventFlags instead of relying on one fixed absolute file offset. It resets the relevant NPC, encounter, chest, battle, dialogue, and reward states, then recalculates the MD5 checksum for the selected character slot.

It does not roll the entire save back in time or revive unrelated NPCs.

### Usage

#### 1. Requirements

Keep both scripts in the same directory:

```text
inspect_patches.py
reset_patches_encounter.py
```

Check Python:

```powershell
python --version
```

#### 2. Locate the save and close the game

Default Steam save location:

```text
%APPDATA%\EldenRing\<SteamID>\ER0000.sl2
```

Confirm that the game is not running:

```powershell
Get-Process eldenring -ErrorAction SilentlyContinue
```

No output means the process has stopped.

#### 3. Back up both files

Replace `<SteamID>` with your numeric directory name:

```powershell
$saveDir = "$env:APPDATA\EldenRing\<SteamID>"
$backupDir = Join-Path $env:APPDATA ("EldenRing\patches-backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $backupDir
Copy-Item "$saveDir\ER0000.sl2" "$backupDir\ER0000.sl2"
Copy-Item "$saveDir\ER0000.sl2.bak" "$backupDir\ER0000.sl2.bak"
```

Confirm that both files exist in the backup directory. Comparing the source and backup SHA-256 values with `Get-FileHash` is recommended.

#### 4. Inspect the original save

```powershell
python .\inspect_patches.py "$env:APPDATA\EldenRing\<SteamID>\ER0000.sl2"
```

`md5_valid` must be `true`. Stop if the checksum is invalid or EventFlags cannot be located.

#### 5. Create a repaired candidate

```powershell
python .\reset_patches_encounter.py `
  "$env:APPDATA\EldenRing\<SteamID>\ER0000.sl2" `
  ".\ER0000_patches_reset.sl2" `
  --slot 0
```

The script does not replace the live save automatically. The report must show `md5_verified: true`.

#### 6. Inspect the candidate

```powershell
python .\inspect_patches.py .\ER0000_patches_reset.sl2
```

Expected key states:

```text
3682 = true
3683 = false
3685 = true
3691 = false
31000800 = false
31000801 = false
31000850 = false
md5_valid = true
```

#### 7. Install the candidate

Confirm that the game is closed and your backups exist, then replace both files:

```powershell
$saveDir = "$env:APPDATA\EldenRing\<SteamID>"
Copy-Item .\ER0000_patches_reset.sl2 "$saveDir\ER0000.sl2" -Force
Copy-Item .\ER0000_patches_reset.sl2 "$saveDir\ER0000.sl2.bak" -Force
```

If either copy fails, do not launch the game. Restore both backup files immediately.

#### 8. Verify in game

1. Enter Murkwater Cave and open the chest.
2. Confirm that Patches appears and the boss fight starts.
3. Stop attacking at approximately half health.
4. Wait for the surrender dialogue and the fight to end.
5. Confirm that Patches remains alive and friendly.
6. Return to the title screen so the game writes the save.
7. Fully close the game and inspect the save again.

Verified post-surrender state:

```text
3680 = true
3682 = false
3683 = false
31000800 = true
31000801 = false
31000850 = false
```

### Rollback

Fully close the game, then restore both files from your backup directory:

```powershell
$saveDir = "$env:APPDATA\EldenRing\<SteamID>"
$backupDir = "<your backup directory>"
Copy-Item "$backupDir\ER0000.sl2" "$saveDir\ER0000.sl2" -Force
Copy-Item "$backupDir\ER0000.sl2.bak" "$saveDir\ER0000.sl2.bak" -Force
```

Never restore only one file, and never roll back while the game is running.

---

## Disclaimer

This project is not affiliated with FromSoftware, Bandai Namco Entertainment, or Valve. `ELDEN RING` and related names belong to their respective owners. The software is provided as-is; users are responsible for save corruption, progress issues, cloud conflicts, and online-service risks.
