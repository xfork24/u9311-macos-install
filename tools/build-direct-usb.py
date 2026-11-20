"""Build a U9311 direct-boot EFI in a new directory, without touching a disk."""
import argparse
import hashlib
from pathlib import Path
import plistlib
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OPENCORE = {
    "BOOT/BOOTx64.efi": "7b26e33bfd84fbc5025fcb16994f7eda3224d15edcfc004d71c8761e08a766fd",
    "OC/OpenCore.efi": "11ba0b763d765fb82187214d1fa2ee5a9330f851461c12e34d532b7b91097875",
    "OC/Drivers/OpenRuntime.efi": "cf2df818f7510ca1be321f1ff6481fcbe246c92b16a905ffc5ff654158e05b66",
    "OC/Drivers/OpenHfsPlus.efi": "ad071af5173d840ad9061a6c62b0f6171fd9f1fda7c44cd95705b432dfdfd1cb",
}


def verified(data, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f"Component differs from the tested SHA-256 {expected}")
    return data


def build(args, target):
    daily = args.profile == "desktop"
    trackpad = ROOT / "DirectUSB/VoodooI2CHID.kext" if args.trackpad_buttons else None
    if trackpad and not daily:
        raise ValueError("The trackpad override requires the desktop profile.")
    source = ROOT / ("EFI/OC" if daily else "Install/EFI/OC")
    # make-config.py supplies the same machine identity for both profiles.
    config = plistlib.loads((source / "config.plist").read_bytes())
    excludes = [".*", "config*.plist"]
    if trackpad:
        excludes.append("VoodooI2CHID.kext")
    shutil.copytree(source, target / "OC", ignore=shutil.ignore_patterns(*excludes))
    (target / "BOOT").mkdir()
    with zipfile.ZipFile(args.opencore) as z:
        for path, checksum in OPENCORE.items():
            (target / path).write_bytes(verified(z.read("X64/EFI/" + path), checksum))
    apfs = verified(args.apfs.read_bytes(), "c4739b191bc44629e9f2703ee15c1645825ecb46b9f77a5c08df706060b78287")
    (target / "OC/Drivers/apfs.efi").write_bytes(apfs)
    config["Booter"]["Quirks"].update(DevirtualiseMmio=False, ForceExitBootServices=True)
    config["Kernel"]["Quirks"]["AppleXcpmExtraMsrs"] = True
    config["Misc"]["Debug"].update(DisplayLevel=2147483714, Target=67)
    patches = plistlib.loads((ROOT / "DirectUSB/acpi-patches.plist").read_bytes())
    config["ACPI"]["Patch"].extend(patches if daily else patches[:1])
    if daily:
        config["UEFI"]["APFS"]["EnableJumpstart"] = False
        install = plistlib.loads((ROOT / "Install/EFI/OC/config.template.plist").read_bytes())
        config["UEFI"]["Drivers"].append(next(d for d in install["UEFI"]["Drivers"] if d["Path"] == "apfs.efi"))
        nv = config["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]
        args_list = nv["boot-args"].split()
        args_list.insert(args_list.index("alcid=3"), "-wex-tgl-edp-cap")
        if trackpad:
            info = plistlib.loads((trackpad / "Contents/Info.plist").read_bytes())
            if info["CFBundleIdentifier"] != "com.alexandred.VoodooI2CHID":
                raise ValueError("Expected a VoodooI2CHID kernel extension.")
            verified((trackpad / "Contents/MacOS/VoodooI2CHID").read_bytes(),
                     "710f896e65ecd62803d7af487f92ff638829c46be5873676a2092f2f541f1cad")
            shutil.copytree(trackpad, target / "OC/Kexts/VoodooI2CHID.kext",
                            ignore=shutil.ignore_patterns("_CodeSignature", ".*"))
            args_list.append("-vi2c-force-polling")
        nv["boot-args"] = " ".join(args_list)
        kext = ROOT / "DirectUSB/WhateverXe.kext"
        verified((kext / "Contents/MacOS/WhateverXe").read_bytes(), "7c024a69c5898f8f297e6ef28c60936ebba973337e2470a0a5d0819090359e94")
        shutil.copytree(kext, target / "OC/Kexts/WhateverXe.kext", dirs_exist_ok=True)
        (target / "OC/Bootstrap").mkdir()
        shutil.copyfile(target / "BOOT/BOOTx64.efi", target / "OC/Bootstrap/Bootstrap.efi")
    (target / "OC/config.plist").write_bytes(plistlib.dumps(config, sort_keys=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=["install", "desktop"])
    parser.add_argument("output", type=Path, help="new EFI directory")
    parser.add_argument("--opencore", type=Path, required=True, help="OpenCore-1.0.8-DEBUG.zip")
    parser.add_argument("--apfs", type=Path, default=ROOT / "Install/EFI/OC/Drivers/apfs.efi")
    parser.add_argument("--trackpad-buttons", action="store_true", help="use the U9311 03Q physical-button driver")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output directory.")
    with tempfile.TemporaryDirectory(dir=args.output.parent) as temp:
        target = Path(temp) / "EFI"
        build(args, target)
        target.rename(args.output)
