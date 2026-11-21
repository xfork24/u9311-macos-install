#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
umask 077

usage() {
    cat <<'EOF'
用法：bash u9311-backup-boot.sh [外接备份盘分区 | 外接备份盘挂载点]
示例：bash u9311-backup-boot.sh /dev/sdb1
省略参数时使用已挂载的 /mnt/u9311-backup。
从 SystemRescue 的 root 终端运行。请先用 lsblk 确认外接盘。
EOF
}

die() {
    printf '错误：%s\n' "$*" >&2
    exit 1
}

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    usage
    exit 0
fi
[[ $# -le 1 ]] || die '只需要一个外接盘分区或挂载点参数。'
[[ $EUID -eq 0 ]] || die '请从 SystemRescue 的 root 终端运行。'

disk=/dev/nvme0n1
esp=${disk}p1
ubuntu=${disk}p5
for command in lsblk blkid blockdev findmnt sgdisk sfdisk efibootmgr fsck.fat sha256sum tar; do
    command -v "$command" >/dev/null || die "找不到命令 $command。"
done
[[ -b "$disk" && -b "$esp" && -b "$ubuntu" ]] || die '未找到本机预期的 /dev/nvme0n1、p1 和 p5。'
[[ $(blkid -p -s TYPE -o value "$esp") == vfat ]] || die 'p1 的文件系统应为 FAT。'
[[ $(blkid -p -s TYPE -o value "$ubuntu") == ext4 ]] || die 'p5 的文件系统应为 ext4。'
for partition in "$esp" "$ubuntu"; do
    if findmnt -rn -S "$partition" -O rw >/dev/null; then
        die "$partition 正以读写方式挂载，请先卸载它。"
    fi
done

scratch=$(mktemp -d /run/u9311-boot.XXXXXX)
loop_disk=''
cleanup() {
    local status=$?
    local mounted=0
    local directory
    trap - EXIT
    for directory in "$scratch/esp" "$scratch/ubuntu" "$scratch/destination"; do
        if mountpoint -q "$directory" && ! umount "$directory"; then
            printf '未能卸载 %s，请手动卸载。\n' "$directory" >&2
            mounted=1
            status=1
        fi
    done
    if [[ -n "$loop_disk" ]]; then
        losetup -d "$loop_disk" || status=1
    fi
    if ((mounted == 0)); then
        rm -rf --one-file-system -- "$scratch" || status=1
    fi
    exit "$status"
}
trap cleanup EXIT
mkdir "$scratch/esp" "$scratch/ubuntu" "$scratch/destination"

destination=${1:-/mnt/u9311-backup}
if [[ -b "$destination" ]]; then
    destination_device=$destination
else
    destination_device=$(findmnt -n --nofsroot -o SOURCE --mountpoint "$destination") ||
        die "挂载点 $destination 未挂载，请传入外接备份盘分区。"
fi
[[ -b "$destination_device" ]] || die '备份目标应为外接盘分区。'
[[ $(lsblk -dnro TYPE "$destination_device") == part ]] || die '请指定外接盘的数据分区。'
destination_parent=$(lsblk -dnro PKNAME "$destination_device")
[[ -n "$destination_parent" && "$destination_parent" != "${disk##*/}" ]] ||
    die '备份目标必须在另一块磁盘上。'
if [[ -b "$destination" ]]; then
    if findmnt -rn -S "$destination_device" >/dev/null; then
        die '目标分区已挂载，请把它当前的挂载点作为参数。'
    fi
    destination=$scratch/destination
    mount "$destination_device" "$destination"
fi

backup=$(mktemp -d "$destination/U9311-boot-$(date +%Y%m%d-%H%M%S)-XXXXXX")
printf '备份目标 %s\n外接盘上的目录 %s\n' "$destination_device" "${backup##*/}"
report=$backup/restore-check.txt
issues=0
record() {
    printf '%s\n' "$*" | tee -a "$report"
}
issue() {
    issues=$((issues + 1))
    record "待检查：$*" >&2
}

# Capture the partition coordinates and the current firmware entries.
sgdisk --backup="$backup/gpt.bin" "$disk"
sfdisk --dump "$disk" > "$backup/partitions.sfdisk"
lsblk -b -o PATH,SIZE,LOG-SEC,FSTYPE,UUID,PARTUUID,PARTLABEL,MODEL "$disk" > "$backup/disk-layout.txt"
if ! efibootmgr -v > "$backup/uefi-boot.txt" 2>&1 || ! grep -q '^BootOrder:' "$backup/uefi-boot.txt"; then
    issue '未读到固件启动顺序，详见 uefi-boot.txt。'
fi

# Restore the GPT to a sparse scratch file. Only partition-table sectors are written.
truncate -s "$(blockdev --getsize64 "$disk")" "$scratch/gpt-test.img"
gpt_test=$scratch/gpt-test.img
sector_size=$(blockdev --getss "$disk")
if [[ "$sector_size" != 512 ]]; then
    loop_disk=$(losetup --find --show --sector-size "$sector_size" "$gpt_test")
    gpt_test=$loop_disk
fi
normalize_layout() {
    sed -E '/^device:/d; s@^/[^:]+:[[:space:]]*start=@start=@' "$1"
}
if sgdisk --load-backup="$backup/gpt.bin" "$gpt_test" > "$backup/gpt-restore.log" 2>&1 &&
   sgdisk --verify "$gpt_test" >> "$backup/gpt-restore.log" 2>&1 &&
   sfdisk --dump "$gpt_test" > "$scratch/gpt-restored.sfdisk" &&
   diff -u <(normalize_layout "$backup/partitions.sfdisk") \
           <(normalize_layout "$scratch/gpt-restored.sfdisk") >> "$backup/gpt-restore.log"; then
    record 'GPT：已在临时介质恢复，分区起点、大小、类型及 GUID 与原盘一致。'
else
    issue 'GPT 恢复后的分区表未通过比对，详见 gpt-restore.log。'
fi

# Restore the saved EFI image to a separate file and read it back as FAT.
dd if="$esp" of="$backup/shared-efi.img" bs=4M conv=excl,fsync status=progress
if cmp "$esp" "$backup/shared-efi.img" > "$backup/efi-source-compare.txt" 2>&1; then
    record '共享 EFI：备份镜像与内置 p1 逐字节一致。'
else
    issue '共享 EFI 备份镜像与内置 p1 的字节比对失败，详见 efi-source-compare.txt。'
fi
dd if="$backup/shared-efi.img" of="$scratch/efi-restored.img" bs=4M conv=fsync status=none
if cmp "$backup/shared-efi.img" "$scratch/efi-restored.img" > "$backup/efi-copy-compare.txt" 2>&1; then
    record '共享 EFI：恢复副本与备份镜像逐字节一致。'
else
    issue '共享 EFI 恢复副本与备份镜像的字节比对失败，详见 efi-copy-compare.txt。'
fi
if fsck.fat -n "$scratch/efi-restored.img" > "$backup/efi-fat-check.txt" 2>&1; then
    record '共享 EFI：恢复副本通过 FAT 只读检查。'
else
    fat_status=$?
    issue "共享 EFI 的 FAT 只读检查返回 $fat_status，详见 efi-fat-check.txt。"
    cat "$backup/efi-fat-check.txt" >&2
fi
mount -t vfat -o loop,ro "$scratch/efi-restored.img" "$scratch/esp" || issue '恢复出的共享 EFI 无法挂载。'
mount -t ext4 -o ro,noload "$ubuntu" "$scratch/ubuntu" || issue 'Ubuntu p5 无法只读挂载。'

esp_root=$scratch/esp
ubuntu_root=$scratch/ubuntu
cat > "$backup/loader-paths.txt" <<'EOF'
Windows Boot Manager   /dev/nvme0n1p1  \EFI\Microsoft\Boot\bootmgfw.efi
Ubuntu                 /dev/nvme0n1p1  \EFI\ubuntu\shimx64.efi
macOS OpenCore         /dev/nvme0n1p1  \EFI\U9311Mac\Bootstrap\Bootstrap.efi
EOF

restore_archive() {
    local name=$1
    shift
    local archive=$backup/$name.tar
    local restored=$scratch/restored/$name
    mkdir -p "$restored"
    tar -cf "$archive" "$@" &&
        tar -xf "$archive" -C "$restored" &&
        tar -df "$archive" -C "$restored"
}

check_files() {
    local name=$1
    shift
    local path
    for path in "$@"; do
        if [[ ! -s "$scratch/restored/$name/$path" ]]; then
            issue "$name 缺少 $path，或该文件为空。"
        fi
    done
}

previous_issues=$issues
if [[ -d "$esp_root/EFI/Microsoft" ]]; then
    restore_archive windows-boot -C "$esp_root" EFI/Microsoft || issue 'Windows 引导归档未通过解包比对。'
fi
check_files windows-boot EFI/Microsoft/Boot/bootmgfw.efi EFI/Microsoft/Boot/BCD
if ((issues == previous_issues)); then
    record 'Windows：Boot Manager 和 BCD 已从引导归档解包并通过检查。'
fi

previous_issues=$issues
ubuntu_paths=()
if [[ -d "$esp_root/EFI/ubuntu" ]]; then
    ubuntu_paths+=(-C "$esp_root" EFI/ubuntu)
fi
for path in boot/grub etc/default/grub etc/default/grub.d etc/grub.d etc/fstab; do
    if [[ -e "$ubuntu_root/$path" ]]; then
        ubuntu_paths+=(-C "$ubuntu_root" "$path")
    fi
done
if ((${#ubuntu_paths[@]})); then
    restore_archive ubuntu-grub "${ubuntu_paths[@]}" || issue 'Ubuntu GRUB 归档未通过解包比对。'
fi
check_files ubuntu-grub EFI/ubuntu/shimx64.efi EFI/ubuntu/grubx64.efi EFI/ubuntu/grub.cfg \
    boot/grub/grub.cfg boot/grub/custom.cfg etc/default/grub etc/fstab
ubuntu_custom=$scratch/restored/ubuntu-grub/boot/grub/custom.cfg
if [[ -s "$ubuntu_custom" ]] && ! grep -Fiq '/EFI/U9311Mac/Bootstrap/Bootstrap.efi' "$ubuntu_custom"; then
    issue 'Ubuntu 的 custom.cfg 找不到本机原有的 OpenCore 启动路径。'
fi
if ((issues == previous_issues)); then
    record 'Ubuntu：EFI 引导文件、GRUB 菜单和配置已从归档解包并通过检查。'
fi

previous_issues=$issues
mac_paths=()
for path in EFI/U9311Mac EFI/U9311OLD; do
    if [[ -d "$esp_root/$path" ]]; then
        mac_paths+=("$path")
    fi
done
if ((${#mac_paths[@]})); then
    restore_archive macos-opencore -C "$esp_root" "${mac_paths[@]}" || issue 'macOS OpenCore 归档未通过解包比对。'
fi
check_files macos-opencore EFI/U9311Mac/Bootstrap/Bootstrap.efi EFI/U9311Mac/OpenCore.efi \
    EFI/U9311Mac/config.plist EFI/U9311Mac/Drivers/OpenRuntime.efi
if ((issues == previous_issues)); then
    record 'macOS：OpenCore 入口、配置和驱动已从归档解包并通过检查。'
fi

if ((issues == 0)); then
    record 'Windows、Ubuntu、macOS 的引导归档均通过解包和关键文件检查。'
else
    record '已保留可取得的备份，以上待检查项需要补齐。'
fi
(
    cd "$backup"
    files=(*.bin *.sfdisk *.txt *.img *.log)
    for archive in *.tar; do
        if [[ -f "$archive" ]]; then
            files+=("$archive")
        fi
    done
    sha256sum -- "${files[@]}" > SHA256SUMS
    sync
    sha256sum -c SHA256SUMS
)
printf '请在外接盘的 %s 目录查看 restore-check.txt 和 SHA256SUMS。\n' "${backup##*/}"
((issues == 0))
