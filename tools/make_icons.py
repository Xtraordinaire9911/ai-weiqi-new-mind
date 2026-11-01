"""Draw the app icons (a small go board corner with two stones) with the standard library only.

Usage: python tools/make_icons.py [out_dir]     (default: icons/)
The artwork is our own: flat colours, a 5x5 grid and two circles, so there is nothing to license.
"""
import math
import struct
import sys
import zlib
from pathlib import Path

WOOD = (217, 168, 91)
LINE = (70, 48, 20)
BLACK = (24, 24, 24)
WHITE = (246, 246, 246)
SS = 3  # supersampling factor for smooth edges


def render(size, margin_ratio, round_corner):
    """Return RGBA bytes. margin_ratio keeps the artwork inside a safe zone (maskable icons)."""
    n = size * SS
    px = bytearray(n * n * 4)
    m = size * margin_ratio * SS
    inner = n - 2 * m
    step = inner / 4.0  # 5 lines -> 4 gaps
    lw = max(1.0, size * 0.012 * SS)
    # the two stones sit on grid points
    bx, by = m + step * 1.0, m + step * 2.0
    wx, wy = m + step * 2.0, m + step * 1.0
    r = step * 0.46
    rad = n * 0.18 if round_corner else 0
    for y in range(n):
        for x in range(n):
            # rounded outer shape
            if rad:
                dx = max(rad - x, x - (n - 1 - rad), 0)
                dy = max(rad - y, y - (n - 1 - rad), 0)
                if dx * dx + dy * dy > rad * rad:
                    continue
            col = WOOD
            gx = (x - m) % step if inner > 0 else 1
            gy = (y - m) % step
            on_x = m - lw <= x <= n - m + lw and (min(gx, step - gx) < lw / 2)
            on_y = m - lw <= y <= n - m + lw and (min(gy, step - gy) < lw / 2)
            if on_x and m - lw <= y <= n - m + lw or on_y and m - lw <= x <= n - m + lw:
                col = LINE
            d = math.hypot(x - bx, y - by)
            if d <= r:
                col = BLACK
            d = math.hypot(x - wx, y - wy)
            if d <= r:
                col = WHITE
                if d >= r - lw * 0.8:
                    col = (150, 150, 150)
            i = (y * n + x) * 4
            px[i:i + 4] = bytes(col) + b'\xff'
    # box filter down to size x size
    out = bytearray()
    for y in range(size):
        out.append(0)  # PNG filter type none
        for x in range(size):
            acc = [0, 0, 0, 0]
            for j in range(SS):
                row = ((y * SS + j) * n + x * SS) * 4
                for k in range(SS):
                    o = row + k * 4
                    a = px[o + 3]
                    acc[0] += px[o] * a; acc[1] += px[o + 1] * a; acc[2] += px[o + 2] * a; acc[3] += a
            if acc[3]:
                out += bytes((acc[0] // acc[3], acc[1] // acc[3], acc[2] // acc[3], acc[3] // (SS * SS)))
            else:
                out += b'\x00\x00\x00\x00'
    return bytes(out)


def png(size, raw):
    def chunk(tag, data):
        c = struct.pack('>I', len(data)) + tag + data
        return c + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent / 'icons'
    out.mkdir(parents=True, exist_ok=True)
    jobs = [('icon-192.png', 192, 0.14, True), ('icon-512.png', 512, 0.14, True),
            ('icon-maskable-512.png', 512, 0.22, False), ('apple-touch-icon.png', 180, 0.14, False)]
    for name, size, margin, rounded in jobs:
        (out / name).write_bytes(png(size, render(size, margin, rounded)))
        print('wrote', out / name)


if __name__ == '__main__':
    main(sys.argv)
