#!/bin/sh
# Read-only lookup in macOS Recovery. No disk modification is performed.
set -eu
export LC_ALL=C
expected_uuid=A0315E11-D14A-4AE3-AAE2-B90CD7CD1065
expected_bytes=103077117952
get_value() {
    # plutil can print an error to stdout for a missing key.
    value=$(printf '%s' "$info" | /usr/bin/plutil -extract "$1" raw -o - - 2>/dev/null) || return 1
    printf '%s\n' "$value"
}
matches_field() {
    [ "$2" = "$3" ] && return 0
    printf '%s: %s = %s (expected %s).\n' "$partition" "$1" "${2:-<missing>}" "$3" >&2
    return 1
}
listing=$(/usr/sbin/diskutil list internal physical)
disks=$(printf '%s\n' "$listing" | /usr/bin/awk '$1 ~ /^\/dev\/disk[0-9]+$/ {print $1}')
if [ -z "$disks" ]; then
    printf 'No internal physical disk listed. Stop here.\n' >&2
    exit 1
fi
for disk in $disks; do
    partition="${disk}s6"
    if ! info=$(/usr/sbin/diskutil info -plist "$partition" 2>/dev/null); then
        printf '%s: sixth partition missing or unreadable.\n' "$disk" >&2
        continue
    fi
    uuid=$(get_value DiskUUID | /usr/bin/tr '[:lower:]' '[:upper:]')
    # Size/IOKitSize describe the partition. TotalSize can be the smaller FAT filesystem size.
    size=$(get_value Size || get_value IOKitSize || true)
    content=$(get_value Content || true)
    fs=$(get_value FilesystemType || true)
    matches_field DiskUUID "$uuid" "$expected_uuid" || continue
    matches_field 'partition size in bytes' "$size" "$expected_bytes" || continue
    matches_field Content "$content" 'Microsoft Basic Data' || continue
    matches_field FilesystemType "$fs" msdos || continue
    /usr/sbin/diskutil info "$partition"
    printf '\nMatched original U9311 FAT partition: %s (96 GiB).\n' "$partition"
    printf 'Only if you want to erase THIS partition, type the following command yourself:\n\n'
    printf 'diskutil eraseVolume APFS U9311-Sequoia %s\n' "$partition"
    exit 0
done
printf 'No exact match for the original internal 96 GiB FAT partition. Stop here.\n' >&2
exit 1
