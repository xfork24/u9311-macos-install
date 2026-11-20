# U9311 实体按键

03Q 在 Sequoia 15.8.3 上以轮询模式运行。Synaptics 06CB:CE2B 的 HID 报告 3 使用 Button 2 和 Button 3 表示两个实体键。这个版本向 VoodooInput 转发这些按键的状态，实机已确认实体右键可打开菜单。8 ms 空闲轮询仍会出现光标卡顿。

[上游按键修复](https://github.com/VoodooI2C/VoodooI2CHID/pull/81) · [对应源码归档](VoodooI2CHID-03Q-source.tar.xz) · [许可证](VoodooI2CHID-LICENSE.txt)

源码基于 VoodooI2CHID 提交 `16f765dab5a3`，本地修改仅为 `INTERRUPT_SIMULATOR_TIMEOUT_IDLE` 从 50 调到 8。构建时从 VoodooI2C 提交 `927797d4fcf5aaf2f4ccddd3daafd93f53d3adbf` 检出 VoodooGPIO 子模块，将上面的源码归档展开到其 `VoodooI2C Satellites/VoodooI2CHID`，并在仓库根目录的 `MacKernelSDK` 放入 acidanthera/MacKernelSDK 提交 `05094e5e88cec7caedbfb35e8449ed0db94bf95b`。在该 VoodooI2C 仓库根目录执行：

```sh
xcodebuild -project 'VoodooI2C Satellites/VoodooI2CHID/VoodooI2CHID.xcodeproj' \
  -target VoodooI2CHID -configuration Release ARCHS=x86_64 ONLY_ACTIVE_ARCH=NO \
  MACOSX_DEPLOYMENT_TARGET=15.0 CODE_SIGNING_ALLOWED=NO \
  'OTHER_CFLAGS=$(inherited) -D__MAC_OS_X_VERSION_MIN_REQUIRED=101100 -D_FORTIFY_SOURCE=0' \
  'OTHER_CPLUSPLUSFLAGS=$(inherited) -D__MAC_OS_X_VERSION_MIN_REQUIRED=101100 -D_FORTIFY_SOURCE=0'
```

实测二进制 SHA-256 为 `710f896e65ecd62803d7af487f92ff638829c46be5873676a2092f2f541f1cad`。构建 EFI 时使用 `--trackpad-buttons` 会同时启用轮询和这份驱动。
