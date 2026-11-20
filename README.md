# 富士通 U9311/F 安装 macOS Sequoia 15.8.3

本机型号 FMVU34013，主板 FJNB2E2，BIOS 2.47。CPU 为 i5-1145G7，核显为 Iris Xe 80 EU（8086:9A49）。本配置用于 Windows 11、Ubuntu 24.04 和 macOS 三系统，使用 Ventoy 的 UEFI 启动菜单。

**已有制作好的 U 盘时，直接按中文指南安装。** 目标是内置 Micron 最后的 96 GiB 分区。抹盘前用随附脚本核对 GPT 分区 UUID；Windows 分区与目标容量接近。[完整安装说明](安装说明.txt)

| 路径 | 用途 |
| --- | --- |
| `Install/EFI/` | 在线安装入口，保持完整 SIP |
| `EFI/` | 进入桌面后的 Metal 入口，搭配 WhateverXe 0.8.3 和 Graphics 0.4.4 |
| `ACPI-source/` | 根据本机固件编写的 SSDT 源码 |
| `U9311-Tools/` | 分区核对、Metal 验证、GRUB 入口、驱动卸载、上游下载地址和哈希 |
| `Media/SHA256SUMS.txt` | 最初写入 Ventoy 的两份镜像的校验值 |

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

4. 构建两个 Ventoy 镜像。将生成的两份 `.img` 文件复制到 Ventoy 数据卷的 `U9311/` 下。将 `U9311-Tools/` 的内容复制到 U 盘的 `U9311/Tools/`。按清单下载 `WhateverXe-Graphics-0.4.4.pkg` 和 `HeliPort.dmg`，核对哈希后放入同一个 Tools 目录。镜像中含本次生成的身份、GPT 标识和 FAT 元数据，重新构建后应为新镜像计算校验值。[组件来源与校验](U9311-Tools/来源与校验.txt)

   ```sh
   bash tools/build-media.sh dist
   (cd dist && sha256sum *.img > SHA256SUMS.txt)
   ```

安装入口含恢复环境，安装时接电源和网线。首次实机安装前，两份配置已通过 OpenCore 1.0.8 的 ocvalidate 检查，模拟启动已到达苹果引导程序向 XNU 交接的阶段。内屏、声音、睡眠和 Metal 仍需在这台富士通上验证。
