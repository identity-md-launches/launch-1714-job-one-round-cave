"""Assemble Pepe 36's generated edit over its verified ancestor and emit records.

Reads a base64 PNG from stdin; no intermediate image is written. Run from the
repository root with the generated image data, then retain only the two wall
PNGs and numbered JPEG as pictures.
"""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path.cwd()
ANCESTOR_SHA256 = '4e6d1cdd13d5a0109e3b76bdf26b2e075af323198885a0aeafa6db6dd34010b2'
BOX = (945, 870, 1224, 1055)
INPUT_LIMIT = 20_000_000


def decode_png(data):
    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'generated edit must be PNG'
    pos, compressed = 8, bytearray()
    while pos < len(data):
        length = int.from_bytes(data[pos:pos+4], 'big')
        kind = data[pos+4:pos+8]
        payload = data[pos+8:pos+8+length]
        assert len(payload) == length
        assert zlib.crc32(kind + payload) == int.from_bytes(data[pos+8+length:pos+12+length], 'big')
        if kind == b'IHDR':
            width, height, depth, color, comp, filt, interlace = struct.unpack('>IIBBBBB', payload)
            assert depth == 8 and color in (2, 6) and comp == filt == interlace == 0
        elif kind == b'IDAT':
            compressed.extend(payload)
        elif kind == b'IEND':
            break
        pos += length + 12
    channels = 3 if color == 2 else 4
    stride = width * channels
    raw = zlib.decompress(compressed)
    assert len(raw) == (stride + 1) * height
    previous, rows = bytearray(stride), []
    for y in range(height):
        offset = y * (stride + 1)
        mode, row = raw[offset], bytearray(raw[offset+1:offset+1+stride])
        assert mode in range(5)
        for x in range(stride):
            a = row[x-channels] if x >= channels else 0
            b = previous[x]
            c = previous[x-channels] if x >= channels else 0
            if mode == 0:
                predictor = 0
            elif mode == 1:
                predictor = a
            elif mode == 2:
                predictor = b
            elif mode == 3:
                predictor = (a+b)//2
            else:
                p = a+b-c
                distances = (abs(p-a), abs(p-b), abs(p-c))
                predictor = (a,b,c)[distances.index(min(distances))]
            row[x] = (row[x] + predictor) & 255
        if channels == 3:
            rows.append(bytes(row))
        else:
            rows.append([tuple(row[x:x+4]) for x in range(0, stride, 4)])
        previous = row
    return width, height, rows, channels


def rgb_rows(width, height, rows, channels, target_width, target_height, background):
    result = []
    for y in range(target_height):
        sy = y * height // target_height
        line = bytearray()
        for x in range(target_width):
            sx = x * width // target_width
            if channels == 3:
                pixel = rows[sy][sx*3:sx*3+3]
            else:
                red, green, blue, alpha = rows[sy][sx]
                base = background[y][x*3:x*3+3] if background else (0, 0, 0)
                pixel = bytes(round((base[c]*(255-alpha) + (red,green,blue)[c]*alpha)/255)
                              for c in range(3))
            line.extend(pixel)
        result.append(line)
    return result


def png_chunk(kind, payload):
    return (struct.pack('>I', len(payload)) + kind + payload +
            struct.pack('>I', zlib.crc32(kind + payload)))


def encode_png(width, height, rows):
    raw = b''.join(b'\0' + bytes(row) for row in rows)
    return (b'\x89PNG\r\n\x1a\n' +
            png_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
            png_chunk(b'IDAT', zlib.compress(raw, 9)) + png_chunk(b'IEND', b''))


def main():
    assert len(sys.argv) == 2 and sys.argv[1].isdigit(), 'pass the base64 character count'
    encoded = sys.stdin.buffer.read(int(sys.argv[1]))
    assert len(encoded) == int(sys.argv[1]) <= INPUT_LIMIT, 'incomplete or oversized image input'
    generated = base64.b64decode(encoded, validate=True)
    original_path = ROOT / 'artifacts/line-1/wall.png'
    original_bytes = original_path.read_bytes()
    ancestor_sha = hashlib.sha256(original_bytes).hexdigest()
    assert ancestor_sha == ANCESTOR_SHA256, 'ancestor wall changed before assembly'

    # The approved shared encoder parses the ancestor, while this in-memory
    # decoder accepts the image tool's generated RGB or RGBA PNG.
    helper_path = ROOT / 'shared/wall-thumbnail/thumbnail.py'
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location('thumbnail36', helper_path)
    thumbnail = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(thumbnail)
    width, height, old_bytes = thumbnail.png_rgb(original_path)
    assert (width, height) == (1254, 1254), 'preserve inherited wall dimensions'
    old = [bytearray(row) for row in old_bytes]
    gw, gh, generated_rows, channels = decode_png(generated)
    new = rgb_rows(gw, gh, generated_rows, channels, width, height, old)
    x0, y0, x1, y1 = BOX
    assert 0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height
    final_rows = [bytearray(row) for row in old]
    for y in range(y0, y1):
        final_rows[y][3*x0:3*x1] = new[y][3*x0:3*x1]
    changed_inside = sum(old[y][3*x:3*x+3] != final_rows[y][3*x:3*x+3]
                         for y in range(y0, y1) for x in range(x0, x1))
    changed_outside = sum(old[y][3*x:3*x+3] != final_rows[y][3*x:3*x+3]
                          for y in range(height) for x in range(width)
                          if not (x0 <= x < x1 and y0 <= y < y1))
    assert changed_inside > 1000 and changed_outside == 0
    final_png = encode_png(width, height, final_rows)
    final_sha = hashlib.sha256(final_png).hexdigest()
    wall_path = ROOT / 'artifacts/line-1/wall-v16.png'
    wall_path.write_bytes(final_png)
    original_path.write_bytes(final_png)

    jpeg = thumbnail.jpeg(thumbnail.resize(width, height, final_rows, 512))
    assert len(jpeg) < 100_000
    jpeg_path = ROOT / 'dist/line-1/36.jpg'
    json_path = ROOT / 'dist/line-1/36.json'
    assert not jpeg_path.exists() and not json_path.exists(), 'never replace a numbered ancestor record'
    jpeg_path.write_bytes(jpeg)
    record = {
        'name': 'Two Eyes, One Stone',
        'image': 'https://api.imd.fun/artifacts/' + final_sha,
        'attributes': [
            {'trait_type': 'Cave', 'value': 'Moss'},
            {'trait_type': 'Wall', 'value': 'Line 1'},
            {'trait_type': 'Number', 'value': 36},
            {'trait_type': 'Left behind', 'value': 'ZTO Witness'},
            {'trait_type': 'Meaning', 'value': 'Two Pepe witnesses compare one stone before trusting its swap bound.'},
            {'trait_type': 'One thing', 'value': 'Calculate ZTO/IMD swap bounds from real Uniswap v4 liquidity'},
        ]
    }
    json_path.write_text(json.dumps(record, separators=(',', ':')) + '\n')
    assert wall_path.read_bytes() == original_path.read_bytes() == final_png
    checks = {
        'ancestor_sha256': ancestor_sha,
        'wall_sha256': final_sha,
        'wall': {'width': width, 'height': height, 'format': 'PNG', 'mode': 'RGB', 'bytes': len(final_png)},
        'jpeg': {'width': 512, 'height': 512, 'format': 'JPEG', 'bytes': len(jpeg)},
        'record': 'dist/line-1/36.json',
        'addition_box': list(BOX),
        'changed_pixels_inside': changed_inside,
        'changed_pixels_outside': changed_outside,
        'hand_review': 'New motif consists only of two Pepe faces and one stone; no hands or handprints were added. Inherited hand counts follow the prior wall review.',
        'text_review': 'No letters or numbers added.',
        'unmet_visual_requirements': [],
        'visual_limitations': ['Generated patch is localized by its bounding rectangle; visual style and digit inspection are human review.']
    }
    checks_path = ROOT / 'line-1/visual-checks-36.json'
    checks_path.write_text(json.dumps(checks, indent=2) + '\n')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
