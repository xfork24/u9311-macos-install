"""Back up the U9311 project on this Mac and its identified installer USB."""
import argparse
import datetime
import fcntl
import os
from pathlib import Path
import plistlib
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def disk_info(identifier):
    return plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", identifier]))


def usb_payload(data_uuid, efi_uuid):
    data, efi = disk_info(data_uuid), disk_info(efi_uuid)
    drive = disk_info(data["ParentWholeDisk"])
    parent = drive["DeviceIdentifier"]
    if not (drive["WholeDisk"] and not drive["Internal"] and drive["BusProtocol"] == "USB"
            and data["DiskUUID"] == data_uuid and efi["DiskUUID"] == efi_uuid
            and data["DeviceIdentifier"] == parent + "s2" and efi["DeviceIdentifier"] == parent + "s1"
            and data["VolumeName"] == "Install macOS Sequoia" and data.get("WritableVolume")
            and data.get("MountPoint") and Path(data["MountPoint"]).is_mount()):
        raise RuntimeError("The mounted volume does not match the U9311 installer USB.")
    folder = Path(data["MountPoint"]) / "U9311"
    if not folder.is_dir() or folder.is_symlink():
        raise RuntimeError("Missing U9311 data folder.")
    return folder


def copy_and_check(source, target, history, excludes=()):
    target.mkdir(parents=True, exist_ok=True)
    # No --delete. Keep older contents when a file changes on either replica.
    common = ["rsync", "-rltpc", "--exclude", "._*", "--exclude", ".DS_Store"]
    for pattern in excludes:
        common.extend(["--exclude", pattern])
    src = str(source) + ("/" if source.is_dir() else "")
    paths = [src, str(target) + "/"]
    subprocess.run(common + ["--backup", "--backup-dir=" + str(history)] + paths, check=True)
    pending = subprocess.check_output(common + ["-ni", "--out-format=%i %n"] + paths, text=True)
    if any(line and not line.startswith((".d", "cd")) for line in pending.splitlines()):
        raise RuntimeError(f"Read-back mismatch for {target}: {pending[:400]}")


def main():
    os.umask(0o077)
    backup = ROOT / "backup"
    mirror = backup / "USB-U9311"
    backup.mkdir(exist_ok=True)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identify", nargs=2, metavar=("DATA_GPT_UUID", "EFI_GPT_UUID"),
                        help="remember the two GPT partition IDs of the installer USB")
    args = parser.parse_args()
    ids_file = backup / "usb-partition-ids"
    with (backup / ".sync.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.identify:
            ids = [value.upper() for value in args.identify]
        elif ids_file.exists():
            ids = ids_file.read_text().splitlines()
        else:
            parser.error("Use --identify with the two diskutil info GPT partition UUIDs.")
        usb = usb_payload(*ids)
        if args.identify:
            ids_file.write_text("\n".join(ids) + "\n")
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        local_history = backup / "history" / stamp
        usb_history = usb / "Backup" / "Previous" / stamp
        # USB-only tools and recovery files belong on the local copy as well.
        copy_and_check(usb, mirror, local_history / "usb", ("/Backup/BootFiles/", "/Backup/Previous/"))
        bootfiles = mirror / "Backup" / "BootFiles"
        # Keep complete EFI bundles with their configs, drivers and kexts.
        for relative in ("EFI", "Install/EFI", "DirectUSB", "tools", "Media", "dist"):
            source = ROOT / relative
            if source.is_dir():
                copy_and_check(source, bootfiles / relative, local_history / "boot" / relative,
                               ("__pycache__/", "*-capture-*/", "u9311-02f-black-*/", "opencore-*.txt", "*.log"))
        for source in [ROOT / "U9311-Tools", ROOT / "安装说明.txt", ROOT / "README.md"]:
            destination = mirror / "Tools" if source.is_dir() else mirror
            copy_and_check(source, destination, local_history / "published" / destination.name)
        if usb_payload(*ids) != usb:
            raise RuntimeError("The installer USB mount changed during backup.")
        copy_and_check(mirror, usb, usb_history, ("/Backup/Previous/",))
        print(f"Verified local and USB project copies:\n{mirror}\n{usb}", flush=True)


if __name__ == "__main__":
    main()
