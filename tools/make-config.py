"""Populate both U9311 profiles with the same SMBIOS identity in a fresh clone."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import uuid

root = Path(__file__).resolve().parents[1]
profiles = [root / 'Install/EFI/OC', root / 'EFI/OC']
fields = ('MLB', 'ROM', 'SystemSerialNumber', 'SystemUUID')

parser = argparse.ArgumentParser(description=__doc__)
sources = parser.add_mutually_exclusive_group(required=True)
sources.add_argument('--identity-from', type=Path, help='existing U9311 config.plist')
sources.add_argument('--macserial', type=Path, help='OpenCore macserial executable')
args = parser.parse_args()
configs = [plistlib.loads((p / 'config.template.plist').read_bytes()) for p in profiles]
model = configs[0]['PlatformInfo']['Generic']['SystemProductName']

if args.identity_from:
    generic = plistlib.loads(args.identity_from.read_bytes())['PlatformInfo']['Generic']
    if generic['SystemProductName'] != model:
        parser.error(f'Expected {model} in --identity-from.')
    identity = {key: generic[key] for key in fields}
    if not all(identity.values()) or len(identity['ROM']) != 6:
        parser.error('Incomplete SMBIOS identity.')
else:
    pair = subprocess.check_output([str(args.macserial.resolve()), '-m', model, '-n', '1'], text=True)
    serial, mlb = (value.strip() for value in pair.strip().split('|'))
    rom = bytearray(os.urandom(6))
    rom[0] = (rom[0] & 0xfe) | 0x02
    identity = dict(MLB=mlb, ROM=bytes(rom), SystemSerialNumber=serial,
                    SystemUUID=str(uuid.uuid4()).upper())

outputs = {}
for folder, config in zip(profiles, configs):
    config['PlatformInfo']['Generic'].update(identity)
    path = folder / 'config.plist'
    if path.exists():
        if plistlib.loads(path.read_bytes()) != config:
            parser.error(f'Existing configuration differs: {path}')
    else:
        outputs[path] = plistlib.dumps(config, sort_keys=False)
for path, data in outputs.items():
    with path.open('xb') as file:
        file.write(data)
print('Both OpenCore profiles are ready.')
