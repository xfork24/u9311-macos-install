# U9311 安装与引导材料

这台富士通使用 **01F 安装 Sequoia，03W 启动已装好的 MacOS**。平时重装或制作 Ventoy 盘，直接使用制作盘 Mac 上的最终导出包 `backup/Ventoy导出/U9311/`。以下目录留给核对配置、重建引导和恢复原普通 U 盘。含本机身份的配置和镜像保存在本地，公开仓库只发布本说明。

| 本地目录 | 用途 |
| --- | --- |
| `01F-DirectUSB/` | 实机安装成功的 `config.plist` 参考副本，已与导出包的 `EFI-01F.zip` 核对。制作安装盘时使用 ZIP 中完整的 `EFI/`。 |
| `03W-Sleep-DirectUSB/OC03W/` | 含原生 Wi‑Fi 和双向隔空投送的日用 OpenCore，共 64 个文件，与 `EFI-03W.zip` 中的 `EFI/OC/` 一致。原普通 U 盘的 03W 菜单从数据卷的 `U9311/Backup/BootFiles/Media/03W-Sleep-DirectUSB/OC03W/OpenCore.efi` 启动。运行 `python3 tools/sync-usb.py` 可从最终配置恢复这个目录。 |
| `03W-Sleep-DirectUSB/Sources/` | 03W 使用的 S0ixStandby 发布包、SSDT 和校验值。`Trackpad/` 保存 03W 沿用的 VoodooI2CHID、VoodooInput 源码及补丁。 |
| `USB-ESP/` | 原普通安装 U 盘的小 EFI 分区镜像及 SHA-256。文件名中的 03L 是留档时最后加入的测试项。菜单通过原数据分区的 GPT 标识定位 03W，适用于修复原盘。新盘可直接恢复完整 01F 镜像。富士通内置三系统 EFI 的备份另见 [备份目录说明](../U9311-Tools/备份目录说明.txt)。 |

## 从本地恢复普通安装 U 盘

两种盘共用 `backup/Ventoy导出/U9311/01F-Sequoia-15.8.3-Offline.img`，备份中只需一份完整离线安装器。

- **普通 U 盘**。在 Ubuntu「磁盘」中选中可清空的外置整盘，选择「恢复磁盘映像」，写入上述 IMG。GPT、01F EFI 和苹果安装卷会一起恢复。若用 Mac 制作，可只读挂载 IMG，取出 `Install macOS Sequoia.app`，用其中的 `createinstallmedia` 创建安装卷，再把 `EFI-01F.zip` 中的 `EFI/` 放在新 U 盘的小 EFI 分区根目录。
- **Ventoy U 盘**。空白盘可在 Ubuntu 用备份所附 `Tools/ventoy-1.1.18-linux.tar.gz` 安装 Ventoy，然后把整个导出文件夹 `U9311/` 复制到 Ventoy 大数据分区。新装手动选 01F Offline，联网恢复选 01F Recovery，启动已安装的 MacOS 选 03W Desktop。
- **原普通盘的文件镜像**。`backup/USB-U9311/` 保存旧盘的 `U9311/` 子目录。整份本地备份中的完整 IMG 位于它旁边的 `Ventoy导出/U9311/`。

目标盘容量、校验命令、App 挂载命令和每次重启的选择见[两种安装盘的重建步骤](../U9311-Tools/Ventoy导出说明.txt)。
