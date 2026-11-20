"""Verify or reconstruct the U9311 offline IMG from its USB backup and Apple installer files."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
from contextlib import ExitStack

APPLE_FILES = (
    "BaseSystem/BaseSystem.dmg",
    "Install macOS Sequoia.app/Contents/SharedSupport/SharedSupport.dmg",
)


def transfer(source, size, digest, output):
    while size:
        chunk = source.read(min(size, 4 * 1024 * 1024))
        if not chunk:
            raise ValueError("A backup file ended early.")
        digest.update(chunk)
        if output:
            output.write(chunk)
        size -= len(chunk)


def restore(backup, installer, output):
    layout = json.loads((backup / "layout.json").read_text())
    if layout["version"] != 1 or layout["size"] <= 0:
        raise ValueError("Unknown or invalid IMG layout.")
    digest = hashlib.sha256()
    position = 0
    with ExitStack() as stack:
        sources = {name: stack.enter_context((installer / name).open("rb")) for name in APPLE_FILES}
        rest = stack.enter_context(gzip.open(backup / "remaining-bytes.gz", "rb"))
        for entry in layout["extents"]:
            offset, length = entry["offset"], entry["length"]
            source_offset = entry["source_offset"]
            source = sources[entry["source"]]
            if offset < position or length <= 0 or source_offset < 0 or offset + length > layout["size"]:
                raise ValueError("Invalid IMG extent.")
            transfer(rest, offset - position, digest, output)
            source.seek(source_offset)
            transfer(source, length, digest, output)
            position = offset + length
        transfer(rest, layout["size"] - position, digest, output)
        if rest.read(1) or digest.hexdigest() != layout["sha256"]:
            raise ValueError("The reconstructed IMG does not match the recorded SHA-256.")
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path, help="directory containing layout.json and remaining-bytes.gz")
    parser.add_argument("installer", type=Path, help="root of the ordinary installer USB or backup/OfflineInstaller")
    parser.add_argument("--output", type=Path, help="new IMG path; omit to verify without writing a file")
    args = parser.parse_args()
    if args.output:
        # Exclusive creation also prevents replacing an existing partition or backup file.
        output = args.output.open("xb")
        try:
            with output:
                result = restore(args.backup, args.installer, output)
        except BaseException:
            args.output.unlink()
            raise
    else:
        result = restore(args.backup, args.installer, None)
    print(f"Verified IMG SHA-256  {result}")


if __name__ == "__main__":
    main()
