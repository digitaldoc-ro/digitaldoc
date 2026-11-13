"""Regenerate responsive WebP assets from the original PNG (requires cwebp).

This optional asset-authoring step is separate from the dependency-free build.
"""
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    encoder = shutil.which('cwebp')
    if encoder is None:
        raise SystemExit('Install the WebP cwebp encoder before regenerating image assets.')
    source = ROOT / 'demo-document-1.png'
    width, height = struct.unpack('>II', source.read_bytes()[16:24])
    target = ROOT / 'assets/images'
    target.mkdir(parents=True, exist_ok=True)
    for size in (400, 560, 768, 1024):
        if size > width:
            raise ValueError('Responsive images must not upscale the source screenshot.')
        destination = target / f'digitaldoc-document-workspace-{size}.webp'
        subprocess.run([encoder, '-quiet', '-q', '90', '-m', '6', '-sharp_yuv',
                        '-metadata', 'all', '-resize', str(size), '0',
                        str(source), '-o', str(destination)], check=True)
        print(f'{size}px: {destination.stat().st_size:,} bytes (original {width}×{height}: {source.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
