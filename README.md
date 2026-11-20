# 富士通 U9311/F 安装 macOS Sequoia 15.8.3

本机型号 FMVU34013，主板 FJNB2E2，BIOS 2.47。CPU 为 i5-1145G7，核显为 Iris Xe 80 EU（8086:9A49）。本配置用于 Windows 11、Ubuntu 24.04 和 macOS 三系统，使用 Ventoy 的 UEFI 启动菜单。

**重启前先把中文指南存到手机。** U 盘上的同一份文件在 `U9311/安装说明.txt`，开头列出了每次重启应选的菜单项。安装系统需要接网线。抹盘前先在恢复环境检查联网情况，再用随附脚本核对内置 Micron 第 6 分区的 UUID 和精确容量。[完整安装说明](安装说明.txt)

| 路径 | 用途 |
| --- | --- |
| `Install/EFI/` | 在线安装入口，保持完整 SIP |
| `EFI/` | 进入桌面后的 Metal 入口，搭配 WhateverXe 0.8.3 和 Graphics 0.4.4 |
| `ACPI-source/` | 根据本机固件编写的 SSDT 源码 |
| `U9311-Tools/` | 苹果下载连通性检查、分区核对、Metal 验证、GRUB 入口、驱动卸载、上游下载地址和哈希 |
| `Media/SHA256SUMS.txt` | 最初写入 Ventoy 的两份镜像的校验值 |
| `Ventoy-SHA256SUMS.txt` | 本次交付到这支 U 盘的完整清单，与盘上 `U9311/SHA256SUMS.txt` 内容一致 |

在本机 Ubuntu 核对整支安装盘时，可从仓库目录运行下面两行。第一行比对清单，第二行实际读取两份镜像、工具、说明和备份。仓库用模板保存配置，用下载地址和校验值标识苹果镜像及第三方安装包。本机的 SMBIOS 标识和原引导备份保存在本机及 U 盘。

```sh
cmp Ventoy-SHA256SUMS.txt /media/hengliu/Ventoy/U9311/SHA256SUMS.txt
(cd /media/hengliu/Ventoy/U9311 && sha256sum -c SHA256SUMS.txt)
```

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

4. 构建两个 Ventoy 镜像。将生成的两份 `.img` 和仓库的 `安装说明.txt` 复制到 Ventoy 数据卷的 `U9311/` 下。将 `U9311-Tools/` 的内容复制到 U 盘的 `U9311/Tools/`。按清单下载 `WhateverXe-Graphics-0.4.4.pkg` 和 `HeliPort.dmg`，核对哈希后放入同一个 Tools 目录。镜像中含本次生成的身份、GPT 标识和 FAT 元数据，重新构建后应为新镜像计算校验值。[组件来源与校验](U9311-Tools/来源与校验.txt)

   ```sh
   bash tools/build-media.sh dist
   (cd dist && sha256sum *.img > SHA256SUMS.txt)
   ```

安装入口含恢复环境，安装时接电源和网线。首次实机安装前，两份配置已通过 OpenCore 1.0.8 的 ocvalidate 检查，模拟启动已到达苹果引导程序向 XNU 交接的阶段。普通 U 盘的实机验证结果见下节。开盖接电自动睡眠曾无法唤醒，复位后系统记录了 EFI 睡眠失败码 0x1F。

## 普通 U 盘直启与备份

U9311/F（BIOS 2.47）已通过普通 GPT U 盘安装 Sequoia 15.8.3。安装基线为 01F。桌面基线包括夏普 1920×1080 内屏的 eDP 速率修复、Metal 计算、AppleALC、Intel 蓝牙和 itlwm。03T 修正了 I²C3 总线编号，使触控板可以枚举；实机反馈仍有输入问题。03P 的轮询恢复了触控输入。03Q 修正了实体右键，指针移动仍偶有卡顿和跳跃。内置三系统引导须在确认日用 EFI 后部署。

完成上面的 SMBIOS 和 Apple APFS 驱动准备后，可从项目根目录生成两个独立的 EFI 目录。参数中的压缩包为 OpenCore 1.0.8 DEBUG 官方发布包，脚本会核对组件 SHA-256。

```sh
python3 tools/build-direct-usb.py install /tmp/U9311-01F-EFI --opencore ~/Downloads/OpenCore-1.0.8-DEBUG.zip
python3 tools/build-direct-usb.py desktop /tmp/U9311-03Q-EFI --trackpad-buttons --opencore ~/Downloads/OpenCore-1.0.8-DEBUG.zip
```

03Q 使用 VoodooI2CHID 上游的按键上报修复，空闲轮询间隔为 8 ms，活动时为 2 ms。仓库内附驱动源码和构建依赖版本。[触控板构建说明](DirectUSB/VoodooI2CHID.md)

屏幕亮度快捷键已在 03R 实测生效。富士通固件对内屏发送亮度加减通知，BrightnessKeys 负责交给 macOS 处理。在桌面构建命令中添加 `--brightness-keys ~/Downloads/BrightnessKeys-1.0.3-RELEASE.zip` 即可启用，保留原有系统设置滑块。[BrightnessKeys 1.0.3 官方发布](https://github.com/acidanthera/BrightnessKeys/releases/tag/1.0.3)

03W 在 U9311/F 上通过了接电、开盖的手动睡眠与自动睡眠唤醒测试。自动睡眠的两次记录分别持续 187 秒和 40 秒，均从 Deep Idle 返回；内屏可操作。电池睡眠和合盖唤醒仍待实测。

从 S0ixStandby v0.5.4 下载 Release ZIP 和 `SSDT-DEEPIDLE.aml`，保存到同一个目录。在桌面 EFI 构建命令中追加 `--deep-idle 下载目录`，脚本会核对两份文件的 SHA-256。重启后用 `kmutil showloaded | grep S0ixStandby` 和 `ioreg -r -c IOPMrootDomain -d 1 -l | grep IOPMDeepIdleSupported` 分别确认驱动已加载、Deep Idle 已启用。[S0ixStandby 官方发布](https://github.com/labrouss/S0ixStandby/releases/tag/v0.5.4)

实测前用 `pmset -g custom` 记录原值，再用 `sudo pmset -c hibernatemode 0 standby 0 powernap 0 tcpkeepalive 0` 设置接电测试条件。此配置在接电睡眠时依赖内存，断电且电池耗尽会丢失睡眠会话。唤醒后可用 `pmset -g log` 核对 `Idle Sleep` 和 `Wake from Deep Idle`。恢复时对照原值逐项设置。[Apple 电源管理参数说明](https://github.com/apple-oss-distributions/PowerManagement/blob/main/pmset/pmset.1)

桌面入口使用 WhateverXe 的 eDP 速率表修复。Wi-Fi 从 HeliPort 菜单连接，连接时勾选“记住此网络”，安装 HeliPort 后以桌面用户运行 `sh U9311-Tools/enable-heliport.sh`，使 HeliPort 随登录启动并隐藏系统无线菜单。[显卡修复源码](https://github.com/Karthik1268/WhateverXe/commit/d1bc03d25ea2c8adc6660172cca455fa138b9eb6) · [itlwm 使用说明](https://openintelwireless.github.io/itlwm/FAQ.html)

这支普通 U 盘接回制作盘的 Mac 后，运行 `python3 tools/sync-usb.py`。新克隆首次同步时加上 `--identify 数据分区的GPT标识 EFI分区的GPT标识`，两个值取自 `diskutil info` 的 Disk / Partition UUID，并保存在本机的忽略目录。脚本按 GPT 分区标识确认目标，回收盘上独有的安装工具，并逐文件校验备份内容。项目工具和说明以仓库为准。EFI 文件树、IMG、配置和项目工具在本机 `backup/USB-U9311/` 与普通盘 `U9311/` 各有一份，启动备份在各自的 `Backup/BootFiles/`。发生覆盖时保留旧版本。实机确认的通用改动进入 Git，个性化 SMBIOS、整盘镜像、现场日志留在本机与普通盘。

在 U9311/F 上，HeliPort 1.5.0 有过连接超时后仍未记住网络的情况。本机验证的补丁会在用户勾选「记住此网络」后立即把凭据写入登录钥匙串，只有不含密码的网络元数据进入备注。连接确认最多等待 120 秒。补丁可在官方 1.5.0 源码根目录用 `git apply /path/to/remember-network.patch` 应用，再以 Xcode 构建 HeliPort scheme 的 macOS Release 版本。实测重启进入桌面后，无需输入密码即可自动联网。 [HeliPort 补丁](DirectUSB/HeliPort/remember-network.patch) · [原版源码](https://github.com/OpenIntelWireless/HeliPort/tree/v1.5.0)
