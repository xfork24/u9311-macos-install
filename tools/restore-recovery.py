"""Retrieve the Intel recovery image from Apple's Sequoia 15.8.3 (24H241) installer."""
import concurrent.futures
import hashlib
import lzma
from pathlib import Path
import struct
import tempfile
import time
from urllib.request import Request, urlopen

root = Path(__file__).resolve().parents[1]
recovery = root / 'Install/com.apple.recovery.boot'
target = recovery / 'BaseSystem.dmg'
url = ('https://swcdn.apple.com/content/downloads/35/30/142-54123-A_L1FDSOKH17/'
       '4v632s6ip8ranyhu7hc09akv6d5239x9tq/InstallAssistant.pkg')
digest = '54bd71da910666f676ada5b46316d9865726789e861b7b22d92ff90edeadb903'
# Byte extents of the ZIP's stored x86_64BaseSystem.dmg BXDIFF50 payload
# in this exact XAR/SharedSupport.dmg. Ranges are (offset, length).
extents = [(5592552939, 151742367), (5744393610, 131072), (5744627594, 393216),
           (5745082250, 131072), (5745241994, 614090649)]
package_size = 15667278673


def download(job):
    remote_offset, length, local_offset, patch = job
    end = remote_offset + length - 1
    requested = f'bytes={remote_offset}-{end}'
    for attempt in range(4):
        try:
            with urlopen(Request(url, headers={'Range': requested}), timeout=60) as r:
                if r.status != 206 or r.headers['Content-Range'] != f'bytes {remote_offset}-{end}/{package_size}':
                    raise ValueError('The server did not return the expected installer range.')
                data = r.read(length + 1)
                if len(data) != length:
                    raise OSError('Incomplete response')
            break
        except (OSError, EOFError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    with patch.open('r+b') as output:
        output.seek(local_offset)
        output.write(data)


def restore():
    chunklist = recovery / 'BaseSystem.chunklist'
    if hashlib.sha256(chunklist.read_bytes()).hexdigest() != '0ddd8edad00640cf40c27d378e0a64fde22a0838880811c3bc0bef1b070adc10':
        raise ValueError('Unexpected chunklist.')
    if target.exists():
        with target.open('rb') as image:
            if hashlib.file_digest(image, 'sha256').hexdigest() == digest:
                print('Existing 24H241 recovery image verified.')
                return
        raise FileExistsError(f'Existing image differs: {target}')
    with tempfile.TemporaryDirectory(dir=recovery) as temp:
        patch = Path(temp) / 'intel.patch'
        patch.touch()
        jobs = []
        offset = 0
        for start, size in extents:
            for pos in range(0, size, 2**21):
                length = min(2**21, size - pos)
                jobs.append((start + pos, length, offset + pos, patch))
            offset += size
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as workers:
            for _ in workers.map(download, jobs):
                pass
        image = Path(temp) / 'BaseSystem.dmg'
        checksum = hashlib.sha256()
        with patch.open('rb') as src, image.open('wb') as dst:
            header = src.read(60)
            if header[:8] != b'BXDIFF50' or src.read(4) != b'pbzx':
                raise ValueError('Unexpected Intel recovery patch format.')
            src.read(8)  # nominal PBZX block size
            while sizes := src.read(16):
                raw_size, packed_size = struct.unpack('>QQ', sizes)
                if max(raw_size, packed_size) > 16 * 2**20:
                    raise ValueError('Unexpected PBZX block size.')
                block = src.read(packed_size)
                if block.startswith(b'\xfd7zXZ\0'):
                    block = lzma.decompress(block)
                if len(block) != raw_size:
                    raise ValueError('Incomplete PBZX data.')
                checksum.update(block)
                dst.write(block)
        if checksum.hexdigest() != digest:
            raise ValueError('Recovery image SHA-256 mismatch.')
        image.replace(target)
    print('Restored and verified the Intel 24H241 recovery image.')


if __name__ == '__main__':
    restore()
