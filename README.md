# 富士通 U9311/F 安装 macOS Sequoia 15.8.3

本机型号 FMVU34013，主板 FJNB2E2，BIOS 2.47。CPU 为 i5-1145G7，核显为 Iris Xe 80 EU（8086:9A49）。本配置用于 Windows 11、Ubuntu 24.04 和 macOS 三系统。安装介质支持 Ventoy 和普通 GPT U 盘。

已有本机导出包时，安装首选 `01F-Sequoia-15.8.3-Offline.img`，日常启动选 `03W-Sequoia-Desktop.img`。完整苹果安装 App 也在离线镜像中。普通 U 盘可以直接整盘恢复同一份离线 IMG。在 Mac 上也可挂载 IMG 取出 App，用苹果工具重新制作。备份中附有从空白 U 盘制作 Ventoy 的 Linux 工具。[普通安装盘恢复步骤](Media/README.md#从本地恢复普通安装-u-盘) · [Ventoy 使用说明](U9311-Tools/Ventoy导出说明.txt)

| 路径 | 用途 |
| --- | --- |
| `Install/EFI/` | 在线安装入口，保持完整 SIP |
| `EFI/` | 进入桌面后的 Metal 入口，搭配 WhateverXe 0.8.3 和 Graphics 0.4.4 |
| `ACPI-source/` | 根据本机固件编写的 SSDT 源码 |
| `U9311-Tools/` | 苹果下载连通性检查、分区核对、Metal 验证、GRUB 入口、驱动卸载、上游下载地址和哈希 |
| `Media/` | 01F 安装配置、03W 日用配置与驱动构建材料、原普通 U 盘的 EFI 恢复镜像。[目录说明](Media/README.md) |
| `Ventoy-SHA256SUMS.txt` | 早期 Ventoy 介质的校验清单。当前导出包使用包内的 `SHA256SUMS.txt` |

在 Ubuntu 核对早期 Ventoy 介质时，可从仓库目录运行下面两行。第一行比对清单，第二行实际读取两份镜像、工具、说明和备份。仓库用模板保存配置，用下载地址和校验值标识苹果镜像及第三方安装包。本机的 SMBIOS 标识和原引导备份保存在本机及 U 盘。

```sh
cmp Ventoy-SHA256SUMS.txt /media/hengliu/Ventoy/U9311/SHA256SUMS.txt
(cd /media/hengliu/Ventoy/U9311 && sha256sum -c SHA256SUMS.txt)
```

## 复制到 Ventoy 的安装包

联网安装可单独复制 `backup/Ventoy导出/U9311-online/` 到 Ventoy 数据分区，预留 2 GiB 空间。安装时选 `01F-Sequoia-15.8.3-Recovery.img`，富士通通过有线网络从苹果下载安装内容。这个目录自带 03W 日用引导、EFI、安装工具和校验清单。[联网安装步骤](U9311-Tools/Ventoy在线安装说明.txt)

制作盘 Mac 上的 `backup/Ventoy导出/U9311/` 是可直接复制到 Ventoy 数据分区的目录。本次完整离线 IMG 为 19 GiB，版本为 Sequoia 15.8.3（24H241）。Ventoy 1.1.18 的 x86_64 UEFI 虚拟启动验证已到苹果引导程序向 XNU 交接。原 Ventoy 盘当时未接入，实体机安装记录来自普通安装盘。包内另附 01F 联网恢复 IMG、03W 日用 IMG、两份独立 EFI、图形驱动和网络检查工具，以及整包 SHA-256 清单。[复制及启动步骤](U9311-Tools/Ventoy导出说明.txt)

普通安装盘上的 `U9311/Backup/Ventoy-Export/` 保存了小镜像、EFI 和工具。完整离线 IMG 的备份复用数据分区已有的苹果安装文件，附带布局和其余字节。在该盘的 `Offline-IMG` 目录运行还原脚本，可以先验证完整 IMG 的 SHA-256，再导出到空间充足的目标盘。[离线 IMG 还原工具](tools/restore-offline-img.py)

## 从新克隆恢复启动文件

以下命令在仓库根目录执行，适用于 Ubuntu 24.04 和 Python 3.11 或以上。原工作区已保留可用的配置和安装介质。Git 中保存了去掉 SMBIOS 标识的模板。备份和恢复时，两套 EFI 必须使用同一组标识。

1. 在新克隆中生成两份 `config.plist`。已有本机 EFI 备份时，使用第一条命令并替换路径。如果从零开始，下载 OpenCore 1.0.8 RELEASE 并解压，改用第二条命令。二选一。[OpenCore 1.0.8](https://github.com/acidanthera/OpenCorePkg/releases/tag/1.0.8)

   ```sh
   python3 tools/make-config.py --identity-from /path/to/existing/EFI/OC/config.plist
   python3 tools/make-config.py --macserial /path/to/OpenCore/Utilities/macserial/macserial.linux
   ```

2. 还原 Apple 的 Intel 恢复镜像。有备份时，可将原 `BaseSystem.dmg` 复制到 `Install/com.apple.recovery.boot/`。以下脚本会验证已有文件，缺少时从固定版本的 Apple 完整安装包下载 Intel 恢复数据并校验 SHA-256。恢复镜像版本为 15.8.3，构建号 24H241。

   ```sh
   python3 tools/restore-recovery.py
   ```

3. 从已校验的镜像中提取同版本 Apple APFS 驱动。Ubuntu 所需工具可用 `sudo apt install 7zip mtools dosfstools gdisk` 安装。

   ```sh
   7z e -so Install/com.apple.recovery.boot/BaseSystem.dmg Volume1/usr/standalone/i386/apfs.efi > Install/EFI/OC/Drivers/apfs.efi
   echo 'c4739b191bc44629e9f2703ee15c1645825ecb46b9f77a5c08df706060b78287  Install/EFI/OC/Drivers/apfs.efi' | sha256sum -c -
   ```

4. 构建两个 Ventoy 镜像。将生成的两份 `.img` 和仓库的 `安装说明.txt` 复制到 Ventoy 数据卷的 `U9311/` 下。将 `U9311-Tools/` 的内容复制到 U 盘的 `U9311/Tools/`。重建早期 02 时，按清单下载 `WhateverXe-Graphics-0.4.4.pkg` 和 `HeliPort.dmg`，核对哈希后放入当时的 Tools 目录。现在使用的 03W 通过系统 Wi‑Fi 菜单连接。镜像中含本次生成的身份、GPT 标识和 FAT 元数据，重新构建后应为新镜像计算校验值。[组件来源与校验](U9311-Tools/来源与校验.txt)

   ```sh
   bash tools/build-media.sh dist
   (cd dist && sha256sum *.img > SHA256SUMS.txt)
   ```

安装入口含恢复环境，安装时接电源和网线。首次实机安装前，两份配置已通过 OpenCore 1.0.8 的 ocvalidate 检查，模拟启动已到达苹果引导程序向 XNU 交接的阶段。普通 U 盘的实机验证结果见下节。开盖接电自动睡眠曾无法唤醒，复位后系统记录了 EFI 睡眠失败码 0x1F。

## 内置盘三系统启动

这台 U9311/F 已在拔掉 U 盘后，通过 Ubuntu 的 GRUB 菜单分别登录 Ubuntu 24.04、Windows 11 和 macOS Sequoia。内置 OpenCore 的菜单也可选择 `Ubuntu 24.04`，通过 Ubuntu 原有的 shim 进入 GRUB 后选择 `Ubuntu`，已实机进入桌面。日常启动 macOS 时，先选 `macOS Sequoia (OpenCore U9311)`，在 OpenCore 中再选 `MacOS`。固件 F12 菜单保留了原有的 Ubuntu、Windows Boot Manager，并新增了 `macOS Sequoia U9311`。[内置盘 GRUB 配置](U9311-Tools/03W-grub.cfg)

内置盘使用 03W。首次复制到共享 EFI 时，三个驱动目录出现重复的 FAT 短文件名。Ubuntu 开机检查时将目录改名为 `FSCK0000.000`，OpenCore 随后在加载键盘驱动时报告缺少 `Info.plist`。在 Ubuntu 下恢复长文件名后，三个目录都获得了独立的短文件名。当前备份已移除指向旧入口的 `add-to-grub.sh`。内置 03W 目录的 69 个文件已逐项核对，共享 EFI 分区也已通过 FAT 检查。制作盘 Mac 的 `backup/USB-U9311/Backup/InternalBoot/` 下，以 `-FAT-names` 结尾的目录保存本机最新的 `esp-after.img`，包括已经实测的 OpenCore Ubuntu 菜单项。[启动和恢复步骤](安装说明.txt)

## 普通 U 盘直启与备份

U9311/F（BIOS 2.47）已通过普通 GPT U 盘安装 Sequoia 15.8.3。安装基线为 01F。桌面基线包括夏普 1920×1080 内屏的 eDP 速率修复、Metal 计算、AppleALC、Intel 蓝牙与原生 Wi‑Fi。03T 修正了 I²C3 总线编号，使触控板可以枚举；实机反馈仍有输入问题。03P 的轮询恢复了触控输入。03Q 修正了实体右键。后续 03L 测试中内置触控板的指针移动仍会停顿、跳跃，外接鼠标正常。

03W 在 Sequoia 15.8.3（24H241）上使用 ForbiddenItlwm 0.6.0-beta.2、BTLEAdvFixup 0.9.3、IntelBluetoothFirmware 2.5.1、BlueToolFixup 2.7.2。富士通与 iPhone 已双向隔空投送成功，MX Anywhere 3 同时可用。Wi‑Fi 从「系统设置 → Wi‑Fi」连接。HeliPort 只适用于旧 itlwm 引导。安装 macOS 增量更新前，先用下文的回退入口启动一次，以停用 `-btleadv`，并核对新系统构建号的支持状态。[驱动发布及更新说明](https://github.com/retropineaple/ForbiddenItlwm/blob/v0.6.0-beta.2/docs/INSTALL.md)

完成上面的 SMBIOS 和 Apple APFS 驱动准备后，可从项目根目录生成两个独立的 EFI 目录。参数中的压缩包为 OpenCore 1.0.8 DEBUG 官方发布包，脚本会核对组件 SHA-256。

```sh
python3 tools/build-direct-usb.py install /tmp/U9311-01F-EFI --opencore ~/Downloads/OpenCore-1.0.8-DEBUG.zip
python3 tools/build-direct-usb.py desktop /tmp/U9311-03Q-EFI --trackpad-buttons --opencore ~/Downloads/OpenCore-1.0.8-DEBUG.zip
```

03Q 使用 VoodooI2CHID 上游的按键上报修复，空闲轮询间隔为 8 ms，活动时为 2 ms。仓库内附驱动源码和构建依赖版本。[触控板构建说明](DirectUSB/VoodooI2CHID.md)

屏幕亮度快捷键已在 03R 实测生效。富士通固件对内屏发送亮度加减通知，BrightnessKeys 负责交给 macOS 处理。在桌面构建命令中添加 `--brightness-keys ~/Downloads/BrightnessKeys-1.0.3-RELEASE.zip` 即可启用，保留原有系统设置滑块。[BrightnessKeys 1.0.3 官方发布](https://github.com/acidanthera/BrightnessKeys/releases/tag/1.0.3)

03W 在 U9311/F 上通过了接电、开盖的手动睡眠与自动睡眠唤醒测试。自动睡眠的两次记录分别持续 187 秒和 40 秒，均从 Deep Idle 返回；内屏可操作。电池睡眠和合盖唤醒仍待实测。另一次 03L 黑屏时 SSH 仍可用，系统的 Deep Idle 次数为 0。唤屏后 Intel 显卡驱动两次报告内屏链路训练失败，并将内屏标为离线。

从 S0ixStandby v0.5.4 下载 Release ZIP 和 `SSDT-DEEPIDLE.aml`，保存到同一个目录。在桌面 EFI 构建命令中追加 `--deep-idle 下载目录`，脚本会核对两份文件的 SHA-256。重启后用 `kmutil showloaded | grep S0ixStandby` 和 `ioreg -r -c IOPMrootDomain -d 1 -l | grep IOPMDeepIdleSupported` 分别确认驱动已加载、Deep Idle 已启用。[S0ixStandby 官方发布](https://github.com/labrouss/S0ixStandby/releases/tag/v0.5.4)

实测前用 `pmset -g custom` 记录原值，再用 `sudo pmset -c hibernatemode 0 standby 0 powernap 0 tcpkeepalive 0` 设置接电测试条件。此配置在接电睡眠时依赖内存，断电且电池耗尽会丢失睡眠会话。唤醒后可用 `pmset -g log` 核对 `Idle Sleep` 和 `Wake from Deep Idle`。恢复时对照原值逐项设置。[Apple 电源管理参数说明](https://github.com/apple-oss-distributions/PowerManagement/blob/main/pmset/pmset.1)

内置 GRUB 和 F12 的 macOS 项都通过 `EFI/U9311Mac/Bootstrap/Bootstrap.efi` 启动默认 03W。如果需要回退 Wi‑Fi 驱动或准备更新 macOS，在 GRUB 高亮 macOS 项，按 `e` 将该次启动的 `U9311Mac` 改为 `U9311OLD`，再按 `Ctrl+X`。要从源码材料构建原生 Wi‑Fi 的桌面 EFI，在现有桌面构建命令中增加 `--airdrop 下载目录`，目录放入驱动来源清单中的三个 ZIP。[发行包及校验值](U9311-Tools/来源与校验.txt)

这台富士通的内置 macOS EFI 或驱动需要恢复时，从 `Storage512G` 根目录打开 `U9311-Recovery`。这套独立恢复包含最终 03W、蓝牙和 Wi‑Fi 驱动、配套的麦克风与 Siri 插件，以及单独安装的显卡组件。[最终恢复包说明](U9311-Tools/最终恢复包说明.txt)

普通 U 盘接回制作盘的 Mac 后，运行 `python3 tools/sync-usb.py`。新克隆首次同步时加上 `--identify 数据分区的GPT标识 EFI分区的GPT标识`，两个值取自 `diskutil info` 的 Disk / Partition UUID。脚本核对分区身份，同步 01F 安装包、03W 日用引导和通过实机验证的内置三系统 EFI，并从 U 盘上的苹果安装文件重新计算完整离线镜像的 SHA-256。普通盘未连接时，可先只读挂载本地完整 IMG，然后运行 `python3 tools/sync-usb.py --local-from-installer "/实际挂载的安装卷路径"`，仅更新本地备份。同步成功后，本地入口说明为 `backup/从这里开始.txt`。[备份目录说明](U9311-Tools/备份目录说明.txt)

旧版 itlwm 引导所用的 HeliPort 1.5.0 有过连接超时后仍未记住网络的情况。本机验证的补丁会在用户勾选「记住此网络」后立即把凭据写入登录钥匙串，只有不含密码的网络元数据进入备注。连接确认最多等待 120 秒。补丁可在官方 1.5.0 源码根目录用 `git apply /path/to/remember-network.patch` 应用，再以 Xcode 构建 HeliPort scheme 的 macOS Release 版本。实测重启进入桌面后，无需输入密码即可自动联网。 [HeliPort 补丁](DirectUSB/HeliPort/remember-network.patch) · [原版源码](https://github.com/OpenIntelWireless/HeliPort/tree/v1.5.0)
