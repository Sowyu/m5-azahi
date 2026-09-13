#!/usr/bin/env python3
"""Pin the existing KDE image and produce checksums for bounded Recovery transfers."""
import hashlib
import json
from pathlib import Path
import subprocess
import zlib

ROOT = Path(__file__).resolve().parent.parent
IMAGE = ROOT / 'ramroot/work-kde/root.img'
DEST = ROOT / 'probe/kde-root-transfer-20260906.json'
EXPECTED_SHA = 'bc33421d52f06288c53cba128ccc79b13c077fb90f957fea048a5048cd955f7b'
EXPECTED_BYTES = 14248030208
CHUNK = 33554432


def main():
    if DEST.exists():
        raise SystemExit('Manifest exists; review it rather than overwrite')
    stat = IMAGE.stat()
    if stat.st_size != EXPECTED_BYTES:
        raise ValueError('KDE image size changed')
    digest = hashlib.sha256()
    zip_crc = 0
    chunks = []
    with IMAGE.open('rb') as source:
        while blob := source.read(CHUNK):
            offset = sum(c['bytes'] for c in chunks)
            digest.update(blob)
            zip_crc = zlib.crc32(blob, zip_crc)
            result = subprocess.run(['/usr/bin/cksum'], input=blob, capture_output=True, check=True).stdout.split()
            if int(result[1]) != len(blob):
                raise ValueError('cksum length mismatch')
            chunks.append(dict(index=len(chunks), offset=offset, bytes=len(blob), cksum=int(result[0]),
                               sha256=hashlib.sha256(blob).hexdigest()))
            if len(chunks) % 32 == 0:
                print(f'Manifest: {len(chunks)} chunks, {offset + len(blob)} bytes', flush=True)
    if digest.hexdigest() != EXPECTED_SHA or zip_crc != 0x359c8a1b:
        raise ValueError('Image SHA256 or original ZIP entry CRC mismatch')
    if IMAGE.stat() != stat:
        raise ValueError('Image stat changed during reading')
    manifest = dict(image_bytes=EXPECTED_BYTES, image_sha256=EXPECTED_SHA, chunk_bytes=CHUNK,
                    btrfs_uuid='PRIVATE-UUID-REMOVED', zip_entry_crc32=f'{zip_crc:08x}',
                    chunks=chunks)
    with DEST.open('x') as output:
        json.dump(manifest, output, indent=2)
        output.write('\n')
    print('ROOT_TRANSFER_MANIFEST_READY', len(chunks), EXPECTED_SHA, flush=True)


if __name__ == '__main__':
    main()
