#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
umask 077

release=03W-24H241-20261121
esp_partuuid=55cc992a-5918-47dd-b593-6cd0916ec7a8
esp_uuid=1061-4E5B
bundle=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
profile=$bundle/payload/U9311Mac.tar
manifest=$bundle/payload/profile.sha256
audio_pkg=$bundle/payload/TGLDmic-0.5.0.1-U9311.pkg
graphics_pkg=$bundle/payload/WhateverXe-Graphics-0.4.4.pkg
hal=/Library/Audio/Plug-Ins/HAL/TGLDmic.driver

manifest_sha=17ff254cd56a83c8e83df38541145d109f679fcf19dba437c80c7989000f2ce7
profile_sha=8e09eeafbc82e17b4593d269333025e91f6294eae47712765362cfaed158c894
audio_sha=aa1dcab0e6b740e1f1ae60914958df665a489a14c5eb739f57e3884b06d77e80
graphics_sha=f4c2d680a7c52c33a3f038ce6945da0aa2cc044e62b935a52ea046c7c473cfec

usage() {
    cat <<EOF
富士通 U9311/F 恢复包 $release
  bash u9311-restore.sh verify         校验外接盘上的恢复包
  sudo bash u9311-restore.sh check-efi 在 Ubuntu 只读核对内置 EFI
  sudo bash u9311-restore.sh efi       在 Ubuntu 恢复内置 OpenCore 及驱动
  bash u9311-restore.sh status         在 macOS 查看音频插件和已加载的驱动
  sudo bash u9311-restore.sh audio      在 macOS 恢复内置麦克风和 Siri 插件
  sudo bash u9311-restore.sh graphics   在 macOS 单独恢复显卡组件
EOF
}

die() {
    printf '错误：%s\n' "$*" >&2
    exit 1
}

hash_file() {
    "${sha[@]}" "$1" | awk '{print $1}'
}

check_hash() {
    [[ -f "$1" && $(hash_file "$1") == "$2" ]]
}

verify_profile() (
    cd -- "$1" || return 1
    unusual=$(find . ! -type d ! -type f -print) || return 1
    actual=$(find . -type f -print | sort) || return 1
    expected=$(sed 's/^[0-9a-f]\{64\}  /\.\//' "$manifest" | sort) || return 1
    [[ -z "$unusual" && "$actual" == "$expected" ]] &&
        "${sha[@]}" -c "$manifest" >/dev/null 2>&1
)

require_profile() {
    check_hash "$manifest" "$manifest_sha" || die 'EFI 校验清单缺失或不属于本版本。'
    check_hash "$profile" "$profile_sha" || die '包内 EFI 归档缺失或校验失败。'
}

require_root() {
    (( EUID == 0 )) || die '本操作需要管理员权限，请按帮助中的 sudo 命令运行。'
}

# Linux writes the FAT directory names. The shared ESP remains intact.
mount_dir=''
stage=''
live=''
committed=0
had_live=0

finish_efi() {
    local result=$?
    trap - EXIT
    trap '' HUP INT TERM
    if [[ -n "$stage" ]]; then
        if (( ! committed )); then
            if [[ -d "$stage/previous" ]]; then
                if { [[ ! -e "$live" ]] || mv -T -- "$live" "$stage/failed"; } &&
                   mv -T -- "$stage/previous" "$live"; then
                    printf '已将原 EFI 目录放回原位。\n' >&2
                else
                    printf '自动回退失败，保留现场目录 %s 与外接盘回退归档。\n' "$stage" >&2
                    stage=''
                    result=1
                fi
            elif (( ! had_live )) && [[ ! -e "$stage/new" && -d "$live" ]]; then
                mv -T -- "$live" "$stage/failed" || result=1
            fi
        fi
        if [[ -n "$stage" ]]; then
            find "$stage" -depth -mindepth 1 -delete && rmdir -- "$stage" || result=1
        fi
        sync -f "$efi" || result=1
    fi
    if [[ -n "$mount_dir" ]]; then
        if mountpoint -q "$mount_dir"; then
            umount "$mount_dir" || result=1
        fi
        rmdir -- "$mount_dir" || result=1
    fi
    exit "$result"
}

efi_operation() {
    local action=$1 target esp_mode mounted backup
    [[ "$os" == Linux ]] || die '请从富士通的 Ubuntu 或 SystemRescue 运行此操作。'
    require_root
    require_profile
    exec 9>/run/lock/u9311-restore-efi.lock
    flock -n 9 || die '另一个 EFI 恢复正在运行。'

    target=$(blkid -c /dev/null -t "PARTUUID=$esp_partuuid" -o device) ||
        die '没有找到这台 U9311 原内置 EFI 的 GPT 分区标识。'
    [[ -b "$target" ]] || die '没有找到这台 U9311 原内置 EFI 的唯一 GPT 分区标识。'
    [[ $(lsblk -dnro TYPE "$target") == part &&
       $(blkid -p -s TYPE -o value "$target") == vfat &&
       $(blkid -p -s UUID -o value "$target") == "$esp_uuid" ]] ||
        die '分区类型或 FAT 卷标识不一致，已停止。'
    [[ $(findmnt -rn -T "$bundle" -o MAJ:MIN) != "$(lsblk -dnro MAJ:MIN "$target")" ]] ||
        die '请将恢复包放在共享 EFI 分区之外。'

    esp_mode=ro
    [[ "$action" != efi ]] || esp_mode=rw
    trap finish_efi EXIT
    trap 'exit 129' HUP
    trap 'exit 130' INT
    trap 'exit 143' TERM
    mounted=$(findmnt -rn -S "$target" -o TARGET || :)
    if [[ -z "$mounted" ]]; then
        mount_dir=$(mktemp -d /run/u9311-esp.XXXXXXXX)
        mount -t vfat -o "$esp_mode",nosuid,nodev,noexec "$target" "$mount_dir"
        mounted=$mount_dir
    fi
    [[ "$mounted" != *$'\n'* && -d "$mounted/EFI" ]] || die 'EFI 挂载状态不明确。'
    [[ "$esp_mode" == ro || $(findmnt -nr -M "$mounted" -o OPTIONS) == rw,* ]] ||
        die 'EFI 当前为只读挂载，请在 Ubuntu 启动后重试。'
    efi=$mounted/EFI
    live=$efi/U9311Mac
    if [[ -d "$live" ]] && verify_profile "$live"; then
        printf '内置 EFI 的 69 个文件均与 %s 一致。\n' "$release"
        return
    fi
    [[ "$action" == efi ]] || die '内置 EFI 与包内版本不一致。'
    [[ ! -e "$live" || -d "$live" ]] || die '内置 U9311Mac 路径异常。'

    if [[ -d "$live" ]]; then
        had_live=1
        mkdir -p -- "$bundle/rollbacks"
        backup=$(mktemp -d "$bundle/rollbacks/EFI-$(date +%Y%m%d-%H%M%S)-XXXXXXXX")
        tar -C "$efi" -cf "$backup/U9311Mac.tar" U9311Mac
        tar -C "$efi" -df "$backup/U9311Mac.tar"
        (cd -- "$backup" && "${sha[@]}" U9311Mac.tar > SHA256SUMS)
        sync -f "$backup"
        printf '原 EFI 已归档到 %s\n' "$backup"
    fi

    stage=$(mktemp -d "$efi/.U9311Stage.XXXXXXXX")
    mkdir "$stage/new"
    tar -xf "$profile" -C "$stage/new" --no-same-owner --no-same-permissions
    verify_profile "$stage/new" || die '写入暂存目录后，EFI 校验未通过。'
    sync -f "$efi"
    if (( had_live )); then
        mv -T -- "$live" "$stage/previous"
    fi
    mv -T -- "$stage/new" "$live"
    sync -f "$efi"
    verify_profile "$live" || die '切换后，EFI 校验未通过。'
    committed=1
    printf '已恢复 %s 的 69 个 EFI 文件。重启选择 macOS Sequoia U9311 → MacOS。\n' "$release"
}

require_macos() {
    local esp_info
    [[ "$os" == Darwin && $(uname -m) == x86_64 ]] || die '请在富士通的 Intel macOS 桌面运行。'
    [[ $(/usr/bin/sw_vers -buildVersion) == 24H241 ]] || die '此包实测适用于 Sequoia 15.8.3 (24H241)。'
    esp_info=$(/usr/sbin/diskutil info -plist "$esp_partuuid" 2>/dev/null) ||
        die '没有找到这台 U9311 原内置 EFI 的 GPT 分区标识。'
    [[ $(/usr/bin/plutil -extract Internal raw -o - - <<< "$esp_info") == true &&
       $(/usr/bin/plutil -extract DiskUUID raw -o - - <<< "$esp_info" | tr 'A-F' 'a-f') == "$esp_partuuid" ]] ||
        die 'EFI 分区身份不符。'
}

check_hal() {
    check_hash "$hal/Contents/MacOS/TGLDmic" 6adbb99e82f52e26fa95e294b6268d3ee4f6f03d8d79c09b49a434682e8c863f &&
        check_hash "$hal/Contents/Info.plist" 8167f126a985ed590268811d4f06e0e818316864b4f0677af83371c07bf091a7
}

audio_status() {
    if check_hal; then
        printf 'macOS 的 TGLDmic/Siri 插件与恢复包一致。\n'
    else
        printf 'macOS 的 TGLDmic/Siri 插件缺失或与恢复包不同。\n'
    fi
    printf '\n当前已加载的相关驱动\n'
    /usr/bin/kmutil showloaded --list-only | grep -Ei 'TGLDmic|AppleALC|IntelBluetooth|BlueToolFixup|BTLEAdvFixup|ForbiddenItlwm|WhateverXe' || :
    printf '\n当前音频设备\n'
    /usr/sbin/system_profiler SPAudioDataType
}

install_macos_package() (
    package=$1
    digest=$2
    check_hash "$package" "$digest" || die '安装包缺失或 SHA-256 不符。'
    work=$(mktemp -d /private/tmp/u9311-install.XXXXXXXX)
    trap 'if [[ -f "$work/staged.pkg" ]]; then unlink "$work/staged.pkg"; fi; rmdir "$work"' EXIT
    cp -- "$package" "$work/staged.pkg"
    check_hash "$work/staged.pkg" "$digest" || die '暂存安装包 SHA-256 不符。'
    /usr/sbin/installer -pkg "$work/staged.pkg" -target /
)

if [[ $# == 0 || ${1:-} == --help || ${1:-} == -h ]]; then
    usage
    exit 0
fi
[[ $# == 1 ]] || die '请只提供一个操作名。'
os=$(uname -s)
case "$os" in
    Linux) sha=(sha256sum) ;;
    Darwin) sha=(/usr/bin/shasum -a 256) ;;
    *) die '支持 Ubuntu、SystemRescue 和 macOS。' ;;
esac

case "$1" in
    verify)
        require_profile
        check_hash "$audio_pkg" "$audio_sha" || die '麦克风与 Siri 安装包校验失败。'
        check_hash "$graphics_pkg" "$graphics_sha" || die '显卡安装包校验失败。'
        printf '恢复包 %s 校验通过（69 个 EFI 文件，2 个 macOS 安装包）。\n' "$release"
        ;;
    check-efi|efi)
        efi_operation "$1"
        ;;
    status)
        require_macos
        audio_status
        ;;
    audio)
        require_root
        require_macos
        check_hash "$audio_pkg" "$audio_sha" || die '麦克风与 Siri 安装包校验失败。'
        if [[ -d "$hal" ]] && ! check_hal; then
            mkdir -p /var/backups/u9311
            saved=$(mktemp -d /var/backups/u9311/audio.XXXXXXXX)
            /usr/bin/ditto -c -k --keepParent "$hal" "$saved/TGLDmic.driver.zip"
            printf '原音频插件已归档到 %s\n' "$saved"
        fi
        install_macos_package "$audio_pkg" "$audio_sha"
        check_hal || die '已安装的音频插件校验失败。'
        printf '已安装并校验麦克风与 Siri 插件。请按恢复说明测试录音和 Siri。\n'
        ;;
    graphics)
        require_root
        require_macos
        csr=$(/usr/sbin/nvram csr-active-config 2>/dev/null) || die '未读取到显卡组件要求的 SIP 配置。'
        anchors=$(/usr/sbin/ioreg -r -c AMFIAnchor -l)
        if [[ "$csr" != *%03%08%00%00 ]] ||
            ! grep -Eq '"InstallStatus" = 1($|[^0-9])' <<< "$anchors" ||
            ! grep -q '"LoadedAnchors"' <<< "$anchors"; then
            die '请先通过已验证的 03W 启动并确认图形驱动的 AMFI 信任配置生效。'
        fi
        install_macos_package "$graphics_pkg" "$graphics_sha"
        printf '显卡组件已安装。请重启后检查 Metal。\n'
        ;;
    *)
        usage >&2
        die '未知操作。'
        ;;
esac
