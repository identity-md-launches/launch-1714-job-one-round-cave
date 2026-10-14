#!/usr/bin/env python3
"""Retain the ancestor's pixels; transfer only the image tool's new pigment."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib
sys.path.insert(0, str(Path('shared/wall-thumbnail').resolve()))
import thumbnail

ANCESTOR = '7818ce2af82c85f7adbe1e36061c353a7f27084beed703ad9774ba42a90d170b'
BOX = (310, 1025, 470, 1115)


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def main():
    source, target = Path('artifacts/gathering/wall.png'), Path('artifacts/gathering/wall-v16.png')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == ANCESTOR
    generated_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    width, height, old = thumbnail.png_rgb(source)
    gw, gh, generated = thumbnail.png_rgb(target)
    assert (width, height) == (gw, gh) == (1254, 1254)
    rows = [bytearray(row) for row in old]
    counts = {'red_ochre': 0, 'chalk': 0, 'charcoal': 0}
    changed = 0
    for y in range(BOX[1], BOX[3]):
        for x in range(BOX[0], BOX[2]):
            at = 3*x
            r,g,b = generated[y][at:at+3]
            pigment = None
            if 1048 <= y <= 1082 and r > 65 and r > 1.7*g and r > 2*b and g < 100:
                pigment = 'red_ochre'
            if any((x-cx)**2 + (y-cy)**2 <= 13**2 for cx,cy in ((340,1046),(444,1057))):
                if r > 150 and g > 130 and b > 95 and r-g < 50:
                    pigment = 'chalk'
            if 1075 <= y <= 1108 and 367 <= x <= 411 and r < 65 and g < 55 and b < 45:
                pigment = 'charcoal'
            if pigment:
                previous = old[y][at:at+3]
                new = bytes(round(a*.18 + c*.82) for a,c in zip(previous,(r,g,b)))
                rows[y][at:at+3] = new
                changed += new != previous
                counts[pigment] += 1
    outside = sum(old[y][3*x:3*x+3] != rows[y][3*x:3*x+3]
                  for y in range(height) for x in range(width)
                  if not (BOX[0] <= x < BOX[2] and BOX[1] <= y < BOX[3]))
    assert changed > 0 and outside == 0 and all(counts.values())
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))
           + chunk(b'IDAT',zlib.compress(b''.join(b'\x00'+row for row in rows))) + chunk(b'IEND',b''))
    target.write_bytes(png); source.write_bytes(png)
    result = {'schema':'gathering-visual-preservation-v16','source_sha256':ANCESTOR,
              'image_tool_output_sha256':generated_hash,'output_sha256':hashlib.sha256(png).hexdigest(),
              'format':'PNG RGB 8-bit','width':width,'height':height,'addition_rectangle':list(BOX),
              'changed_pixels':changed,'changed_pixels_outside_addition':outside,'pigment_pixels':counts,
              'ancestral_pigment_intersects_addition':False,'left_hand_digits':5,'right_hand_digits':5,
              'new_hands':0,'unmet_visual_requirements_observed':[],
              'review_limits':'Digits and bare-patch choice reviewed visually; exact preservation outside the patch measured.'}
    Path('gathering/visual-checks-16.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
