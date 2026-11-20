#!/bin/sh
# Read-only lookup in macOS Recovery. No disk modification is performed.
set -eu
export LC_ALL=C
expected_uuid=A0315E11-D14A-4AE3-AAE2-B90CD7CD1065
expected_bytes=103077117952
get_value() { printf '%s' "$info" | /usr/bin/plutil -extract "$1" raw -o - - 2>/dev/null; }
for disk in $(/usr/sbin/diskutil list internal physical | /usr/bin/awk '/^\/dev\/disk[0-9]+ / {print $1}'); do
    partition="${disk}s6"
    info=$(/usr/sbin/diskutil info -plist "$partition" 2>/dev/null) || continue
    uuid=$(get_value DiskUUID | /usr/bin/tr '[:lower:]' '[:upper:]')
    size=$(get_value TotalSize || get_value Size || true)
    content=$(get_value Content || true)
    fs=$(get_value FilesystemType || true)
    [ "$uuid" = "$expected_uuid" ] && [ "$size" = "$expected_bytes" ] && [ "$content" = "Microsoft Basic Data" ] && [ "$fs" = "msdos" ] || continue
    /usr/sbin/diskutil info "$partition"
    printf '\nMatched original U9311 FAT partition: %s (96 GiB).\n' "$partition"
    printf 'Only if you want to erase THIS partition, type the following command yourself:\n\n'
    printf 'diskutil eraseVolume APFS U9311-Sequoia %s\n' "$partition"
    exit 0
done
printf 'No exact match for the original internal 96 GiB FAT partition. Stop here.\n' >&2
exit 1
