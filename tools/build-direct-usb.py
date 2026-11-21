"""Build a U9311 direct-boot EFI in a new directory, without touching a disk."""
import argparse
import hashlib
import io
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


def install_release_kext(archive, expected, name, kexts):
    with zipfile.ZipFile(io.BytesIO(verified(archive.read_bytes(), expected))) as z:
        for relative in ("Contents/Info.plist", "Contents/MacOS/" + name):
            member = Path(name + ".kext") / relative
            dest = kexts / member
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(member.as_posix()))
            if relative.startswith("Contents/MacOS/"):
                dest.chmod(0o755)


def enable_airdrop(oc, config, archives):
    kexts = oc / "Kexts"
    releases = (
        ("IntelBluetoothFirmware", "IntelBluetooth-2.5.1-RELEASE.zip",
         "0e58a31993657ee2227fd548dff6d0cdf38bc9e4cb1495816e148c8d6ab43e5c"),
        ("BTLEAdvFixup", "BTLEAdvFixup-0.9.3-Sequoia.zip",
         "1418f643c939208b3930d5a333c9ea5b7e055dcf9b0c6ceece2a87cdda5fde31"),
        ("ForbiddenItlwm", "ForbiddenItlwm-0.6.0-beta.2-Sequoia.zip",
         "91251e1ac187794b1669cd8f81529e56ddc3040349575afde751b9e030e309d3"),
    )
    for name, filename, checksum in releases:
        install_release_kext(archives / filename, checksum, name, kexts)

    entries = config["Kernel"]["Add"]
    template = next(e for e in entries if e["BundlePath"] == "itlwm.kext")
    retired = {"itlwm.kext", "IntelBTPatcher.kext"}
    entries[:] = [e for e in entries if e["BundlePath"] not in retired]
    for bundle in retired:
        shutil.rmtree(kexts / bundle)
    index = next(i for i, e in enumerate(entries) if e["BundlePath"] == "BlueToolFixup.kext") + 1
    entries[index:index] = [
        dict(template, BundlePath=name + ".kext", ExecutablePath="Contents/MacOS/" + name,
             MinKernel="24.0.0", MaxKernel="24.99.99", Enabled=True)
        for name in ("BTLEAdvFixup", "ForbiddenItlwm")
    ]
    guid = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
    config["NVRAM"]["Add"][guid]["boot-args"] += (
        " -btleadv -itlawdlcoexprobe -itlawdliface -itlawdlnativeup -itlawdlcoexrx"
        " -itlawdlcoextx -itlawdlcoexmulti -itlawdlcoexdata -itlawdlmitx -itlawdlelicit"
        " -itlawdlcaps -itlawdlsvcmerge -itlawdlawsync itlawdlintcoal=4 -itlawdlcoexbatx"
        " -itlawdlcoexpeerpause -itlawdlcoexbatrace itlawdltxqueue=4096"
    )


def build(args, target):
    daily = args.profile == "desktop"
    trackpad = ROOT / "DirectUSB/VoodooI2CHID.kext" if args.trackpad_buttons else None
    if (trackpad or args.brightness_keys or args.deep_idle or args.airdrop) and not daily:
        raise ValueError("Input, brightness, sleep and AirDrop options require the desktop profile.")
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
        if args.brightness_keys:
            install_release_kext(args.brightness_keys,
                                 "c9a80f6275e39c18886087a70ba0fe615ce45f83b7afa254b74335f7a92b8544",
                                 "BrightnessKeys", target / "OC/Kexts")
            entry = next(e.copy() for e in config["Kernel"]["Add"] if e["BundlePath"] == "Lilu.kext")
            entry.update(BundlePath="BrightnessKeys.kext", ExecutablePath="Contents/MacOS/BrightnessKeys",
                         Comment="U9311 LCD brightness keys")
            config["Kernel"]["Add"].append(entry)
        if args.deep_idle:
            aml = "SSDT-DEEPIDLE.aml"
            data = verified((args.deep_idle / aml).read_bytes(),
                            "477c92c60a767cde3baef858932d652a91b962f5e01cd7baf6467c544c7a46f0")
            (target / "OC/ACPI" / aml).write_bytes(data)
            archive = args.deep_idle / "S0ixStandby-0.5.4-v0.5.3-5-gc52f172-Release.zip"
            install_release_kext(archive, "266598d8613bf841568a0611c6b463fcdff7aac9afd27d7b036c84f34ca01553",
                                 "S0ixStandby", target / "OC/Kexts")
            config["ACPI"]["Add"].append(dict(Path=aml, Enabled=True,
                                              Comment="Darwin LPS0 and LXEN for a Deep Idle sleep trial"))
            config["Kernel"]["Add"].append(dict(Arch="x86_64", BundlePath="S0ixStandby.kext",
                                                Comment="S0ixStandby 0.5.4, Intel Modern Standby trial for macOS 15",
                                                Enabled=True, ExecutablePath="Contents/MacOS/S0ixStandby",
                                                MinKernel="24.0.0", MaxKernel="24.99.99", PlistPath="Contents/Info.plist"))
        nv["boot-args"] = " ".join(args_list)
        if args.airdrop:
            enable_airdrop(target / "OC", config, args.airdrop)
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
    parser.add_argument("--brightness-keys", type=Path, metavar="ZIP", help="BrightnessKeys-1.0.3-RELEASE.zip")
    parser.add_argument("--deep-idle", type=Path, metavar="DIR",
                        help="directory with the v0.5.4 S0ixStandby release ZIP and SSDT-DEEPIDLE.aml")
    parser.add_argument("--airdrop", type=Path, metavar="DIR",
                        help="directory with the three tested Sequoia Wi-Fi and Bluetooth release ZIPs")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output directory.")
    with tempfile.TemporaryDirectory(dir=args.output.parent) as temp:
        target = Path(temp) / "EFI"
        build(args, target)
        target.rename(args.output)
