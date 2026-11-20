"""Back up the U9311 project on this Mac and its identified installer USB."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import shutil
import sys
import tempfile
import zipfile

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


INTERNAL = Path("Backup/InternalBoot/20261120-220252-FAT-names")
VENTOY = Path("Backup/Ventoy-Export")
COMPACT = VENTOY / "Offline-IMG"
PACKAGE = VENTOY / "U9311"
SUMS = "SHA256SUMS.txt"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def manifest(path):
    entries = {}
    for line in path.read_text().splitlines():
        checksum, name = line.split("  ", 1)
        item = Path(name)
        if (len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum)
                or item.is_absolute() or ".." in item.parts or name in entries):
            raise ValueError(f"Invalid checksum entry in {path}")
        entries[name] = checksum
    if not entries:
        raise ValueError(f"Empty checksum file: {path}")
    return entries


def existing(*paths):
    for path in paths:
        if path.is_file():
            return path
    raise FileNotFoundError(paths[0])


def store_file(source, target, expected):
    if source == target or (target.is_file() and digest(target) == expected):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".sync-", delete=False) as tmp:
        temp = Path(tmp.name)
    try:
        shutil.copy2(source, temp)
        if digest(temp) != expected:
            raise OSError(f"Checksum mismatch for {source}")
        temp.replace(target)
    finally:
        temp.unlink(missing_ok=True)


def synchronize(backup, usb=None, *, installer=None):
    mirror = backup / "USB-U9311"
    export = backup / "Ventoy导出/U9311"
    targets = (mirror, usb) if usb is not None else (mirror,)
    installer = usb.parent if usb is not None else installer
    entries = {}

    def copy_item(relative, expected=None, preferred=None, export_path=None):
        sources = [base / relative for base in targets]
        if preferred is not None:
            sources.insert(0, preferred)
        if expected is None:
            source = existing(*sources)
            expected = digest(source)
        else:
            source = next((p for p in sources if p.is_file() and digest(p) == expected), None)
            if source is None:
                raise ValueError(f"No verified copy of {relative}")
        for base in targets:
            store_file(source, base / relative, expected)
        if export_path is not None:
            store_file(source, export_path, expected)
        entries[relative.as_posix()] = expected

    # The full offline IMG is already present on the USB as reconstructible extents.
    sums = existing(export / SUMS, *(base / PACKAGE / SUMS for base in targets))
    package = manifest(sums)
    failures = []
    for base in targets:
        compact = base / COMPACT
        try:
            layout = json.loads((compact / "layout.json").read_text())
            offline = layout["image"]
            if offline not in package or package[offline] != layout["sha256"]:
                raise ValueError("offline IMG checksum differs from export manifest")
            subprocess.run([sys.executable, str(ROOT / "tools/restore-offline-img.py"),
                            str(compact), str(installer)], check=True)
            break
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
            failures.append(f"{compact}: {error}")
    else:
        raise ValueError("No valid offline backup: " + ", ".join(failures))
    image = export / offline
    if not image.is_file() or digest(image) != package[offline]:
        export.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=export) as work:
            temp = Path(work) / "offline.img"
            subprocess.run([sys.executable, str(ROOT / "tools/restore-offline-img.py"),
                            str(compact), str(installer), "--output", str(temp)], check=True)
            temp.replace(image)

    for name in ("layout.json", "remaining-bytes.gz"):
        copy_item(COMPACT / name, digest(compact / name), compact / name)
    copy_item(COMPACT / "restore-offline-img.py", preferred=ROOT / "tools/restore-offline-img.py")
    for name, checksum in package.items():
        if name != offline:
            copy_item(PACKAGE / name, checksum, export / name, export / name)
    copy_item(PACKAGE / SUMS, preferred=sums, export_path=export / SUMS)

    for name, prefix in (("esp-after.img.sha256", INTERNAL), ("profile.sha256", INTERNAL / "U9311Mac")):
        listing = existing(*(base / INTERNAL / name for base in targets))
        for member, checksum in manifest(listing).items():
            copy_item(prefix / member, checksum)
        copy_item(INTERNAL / name, preferred=listing)
    # The original USB's rEFInd selector opens this path on the installer data volume.
    media = Path("Backup/BootFiles/Media")
    loader = media / "03W-Sleep-DirectUSB/OC03W"
    with zipfile.ZipFile(mirror / PACKAGE / "EFI-03W.zip") as archive, tempfile.TemporaryDirectory(dir=backup) as work:
        archive.getinfo("EFI/OC/OpenCore.efi")
        source = Path(work) / "member"
        for member in archive.infolist():
            if member.is_dir() or not member.filename.startswith("EFI/OC/"):
                continue
            relative = Path(member.filename.removeprefix("EFI/OC/"))
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Invalid OpenCore path: {member.filename}")
            source.write_bytes(archive.read(member))
            copy_item(loader / relative, preferred=source)

    # The menu snapshot belongs to the original stick; new sticks can use standalone 01F.
    esp = media / "USB-ESP"
    original = ROOT / "Media/USB-ESP"
    receipt = "EFI-03L-USB.sha256"
    receipts = [original / receipt, *(base / esp / receipt for base in targets)]
    if any(path.is_file() for path in receipts):
        listing = existing(*receipts)
        for name, checksum in manifest(listing).items():
            copy_item(esp / name, checksum, original / name)
        copy_item(esp / receipt, preferred=listing)
    grub = mirror / PACKAGE / "Tools/03W-grub.cfg"
    copy_item(INTERNAL / "grub-custom.cfg", digest(grub), grub)
    copy_item(Path("使用说明.txt"), preferred=ROOT / "U9311-Tools/备份目录说明.txt",
              export_path=backup / "从这里开始.txt")

    listing = "".join(f"{checksum}  {name}\n" for name, checksum in sorted(entries.items()))
    with tempfile.TemporaryDirectory(dir=backup) as work:
        source = Path(work) / SUMS
        source.write_text(listing)
        for base in targets:
            store_file(source, base / SUMS, digest(source))
    print(f"Verified {len(entries)} files in " + " and ".join(map(str, targets)), flush=True)


def main():
    os.umask(0o077)
    backup = ROOT / "backup"
    backup.mkdir(exist_ok=True)
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--local-from-installer", type=Path, metavar="VOLUME",
                      help="verify against a mounted installer volume and update only the local backup")
    mode.add_argument("--identify", nargs=2, metavar=("DATA_GPT_UUID", "EFI_GPT_UUID"),
                        help="remember the two GPT partition IDs of the installer USB")
    args = parser.parse_args()
    ids_file = backup / "usb-partition-ids"
    with (backup / ".sync.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.local_from_installer:
            synchronize(backup, installer=args.local_from_installer)
            return
        if args.identify:
            ids = [value.upper() for value in args.identify]
        elif ids_file.exists():
            ids = ids_file.read_text().splitlines()
        else:
            parser.error("Use --identify with the two diskutil info GPT partition UUIDs.")
        usb = usb_payload(*ids)
        if args.identify:
            ids_file.write_text("\n".join(ids) + "\n")
        synchronize(backup, usb)
        if usb_payload(*ids) != usb:
            raise RuntimeError("The installer USB mount changed during backup.")


if __name__ == "__main__":
    main()
