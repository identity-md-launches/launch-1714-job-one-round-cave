#!/usr/bin/env python3
"""Transfer generated pigment only, conserving the inherited cave pixel for pixel."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zlib

ROOT = Path.cwd().resolve()
WALL = ROOT / 'artifacts/line-4/wall.png'
OUTPUT = ROOT / 'artifacts/line-4/wall-v16.png'
PATCH = (220, 965, 320, 1065)


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def encode(width, height, rows):
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b''.join(b'\0'+bytes(row) for row in rows), 9))
            + chunk(b'IEND', b''))


def pigment(red, green, blue, x, y, width, height):
    if green < 105 and red < 140:
        return min(0.9, max(0, (135-green)/85)), (43, 29, 20)
    if red > 1.45 * green and 95 < red < 210 and green < 145:
        return min(0.85, max(0, (red-green-35)/65)), (147, 53, 27)
    if ((x/width-0.49)**2 + (y/height-0.50)**2 < 0.0016
            and red > 220 and green > 197 and blue > 140):
        return min(0.8, max(0, (green-180)/65)), (227, 202, 153)
    return 0, (0, 0, 0)


def main():
    original_hash = hashlib.sha256(WALL.read_bytes()).hexdigest()
    assert original_hash == 'bf38393dfe0a94c570c51761af9c44c2dc8677eea7f54ad9037d19dbe2dd2f80'
    spec = importlib.util.spec_from_file_location(
        'wall36_codec', ROOT / 'line-4/tools/call-rehearsal/thumbnail.py')
    codec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(codec)
    width, height, old = codec.png_rgb(WALL)
    sw, sh, source = codec.png_rgb(OUTPUT)
    source_hash = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    assert width == height == 1254
    rows = [bytearray(row) for row in old]
    left, top, right, bottom = PATCH
    # Crop only blank margins from the generated motif; its original rock is discarded.
    for y in range(top, bottom):
        y0 = round(sh * (0.10 + 0.80*(y-top)/(bottom-top)))
        y1 = round(sh * (0.10 + 0.80*(y-top+1)/(bottom-top)))
        for x in range(left, right):
            x0 = round(sw * (0.10 + 0.80*(x-left)/(right-left)))
            x1 = round(sw * (0.10 + 0.80*(x-left+1)/(right-left)))
            sums, alpha = [0.0]*3, 0.0
            count = (x1-x0)*(y1-y0)
            for sy in range(y0, y1):
                for sx in range(x0, x1):
                    a, color = pigment(*source[sy][3*sx:3*sx+3], sx, sy, sw, sh)
                    alpha += a
                    for c in range(3):
                        sums[c] += a*color[c]
            if alpha > 0:
                a = alpha/count
                # Retain rock relief and torch lighting within the transferred pigment.
                lighting = 0.7 + sum(old[y][3*x:3*x+3])/(3*255)*0.45
                for c in range(3):
                    paint = min(255, sums[c]/alpha*lighting)
                    rows[y][3*x+c] = round(old[y][3*x+c]*(1-a) + paint*a)
    inside = outside = 0
    for y in range(height):
        for x in range(width):
            if rows[y][3*x:3*x+3] != old[y][3*x:3*x+3]:
                if left <= x < right and top <= y < bottom:
                    inside += 1
                else:
                    outside += 1
    assert inside > 0 and outside == 0
    finished = encode(width, height, rows)
    jpeg = codec.jpeg(codec.resize(width, height, rows, 512))
    assert len(jpeg) < 100000
    OUTPUT.write_bytes(finished)
    WALL.write_bytes(finished)
    with (ROOT / 'dist/line-4/36.jpg').open('xb') as handle:
        handle.write(jpeg)
    report = {'ancestor_sha256': original_hash, 'generated_source_sha256': source_hash,
              'wall_sha256': hashlib.sha256(finished).hexdigest(),
              'wall': {'width': width, 'height': height, 'format': 'PNG', 'mode': 'RGB', 'bytes': len(finished)},
              'thumbnail': {'width': 512, 'height': 512, 'format': 'JPEG', 'bytes': len(jpeg),
                            'sha256': hashlib.sha256(jpeg).hexdigest()},
              'addition_rectangle': list(PATCH), 'changed_pixels_inside': inside,
              'changed_pixels_outside': outside, 'named_wall_identical': WALL.read_bytes() == OUTPUT.read_bytes(),
              'unmet_visual_requirements': [
                  'Inherited small three-pronged trail marks cannot be certified as five-digit handprints; preserved unchanged.']}
    (ROOT / 'line-4/delivery-checks-36.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
