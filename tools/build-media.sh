#!/usr/bin/env bash
# Build both Ventoy images in a new output directory. Uses regular files only.
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
output=${1:?Pass a new output directory for the Ventoy images}
for tool in mkfs.fat sgdisk mcopy mdel truncate dd; do command -v "$tool" >/dev/null; done
for input in EFI/OC/config.plist Install/EFI/OC/config.plist Install/EFI/OC/Drivers/apfs.efi \
             Install/com.apple.recovery.boot/BaseSystem.dmg Install/com.apple.recovery.boot/BaseSystem.chunklist; do
    test -s "$root/$input" || { echo "Missing $input" >&2; exit 1; }
done
mkdir -- "$output"
scratch=$(mktemp -d -- "$output/.build.XXXXXXXX")
trap 'rm -rf -- "$scratch"' EXIT

build() {
    local name=$1 size=$2 label=$3 efi=$4
    local fat="$scratch/$label.fat" img="$scratch/$name"
    truncate -s "${size}M" "$fat"
    mkfs.fat -F 32 -n "$label" "$fat" >/dev/null
    mcopy -si "$fat" "$efi" ::/
    mdel -i "$fat" ::/EFI/OC/config.template.plist
    if [[ "$label" == U9311INST ]]; then
        mcopy -si "$fat" "$root/Install/com.apple.recovery.boot" ::/
    fi
    truncate -s "$((size + 2))M" "$img"
    sgdisk -o -n "1:2048:+${size}M" -t 1:ef00 -c 1:OpenCore "$img" >/dev/null
    dd if="$fat" of="$img" bs=1M seek=1 conv=notrunc status=none
    sgdisk -v "$img"
}
build 01-U9311-Sequoia-15.8.3-Install.img 1380 U9311INST "$root/Install/EFI"
build 02-U9311-Sequoia-Metal.img 80 U9311METAL "$root/EFI"
mv -- "$scratch"/*.img "$output/"
