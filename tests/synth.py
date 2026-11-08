"""Synthetic video frames for the board recognition tests: wood background, grid lines, round stones.

Everything is drawn with numpy, no video frame is used anywhere (copyright)."""
import numpy as np

COLS = 18


def make_frame(stones=None, X0=248.0, Y0=40.0, D=35.4, wood=(228, 180, 98), grid=True, size=(720, 1134)):
    """A 720x1134 RGB frame like the lesson videos show. stones: {point index (row*18+col): 'B'|'W'}."""
    H, W = size
    f = np.empty((H, W, 3), np.uint8)
    f[:] = wood
    if grid:
        line = (150, 110, 60)
        for r in range(19):
            y = int(round(Y0 + D * r))
            f[y - 1:y + 1, int(X0):int(X0 + D * 18) + 1] = line
        for c in range(19):
            x = int(round(X0 + D * c))
            f[int(Y0):int(Y0 + D * 18) + 1, x - 1:x + 1] = line
    yy, xx = np.ogrid[-16:17, -16:17]
    disc = (yy * yy + xx * xx) <= 16 * 16
    for k, col in (stones or {}).items():
        r, c = divmod(k, COLS)
        cx, cy = int(round(X0 + D * c)), int(round(Y0 + D * r))
        f[cy - 16:cy + 17, cx - 16:cx + 17][disc] = (20, 20, 20) if col == "B" else (245, 245, 245)
    return f


# Geometries that look like the real layouts: size (h, w), x0, y0, dx, dy. The numbers are invented around the ranges
# measured on the lesson videos (frame width 1028..1174, pitch 34.9..36.2, board left edge 197..271, top line 30..45),
# they are not copied from any one video.
LAYOUTS = {
    'wide': dict(size=(720, 1154), x0=252.5, y0=36.9, dx=36.05, dy=36.1),
    'narrow': dict(size=(720, 1030), x0=198.0, y0=41.2, dx=35.26, dy=35.36),
    'offset': dict(size=(720, 1110), x0=238.6, y0=44.3, dx=35.3, dy=35.28),
    'labelled': dict(size=(720, 1174), x0=271.1, y0=44.8, dx=34.95, dy=34.92, coords=True),
    'low': dict(size=(720, 1134), x0=249.8, y0=30.2, dx=35.4, dy=35.5),
}


def _paint_line(f, vertical, c, a, b, colour, width=1.6):
    """A line of the given width centred at c (pixel index units, sub pixel exact) from a to b; edge pixels are blended."""
    for i in range(int(np.floor(c - width)) - 1, int(np.ceil(c + width)) + 2):
        cover = max(0.0, min(c + width / 2, i + .5) - max(c - width / 2, i - .5))
        if cover <= 0:
            continue
        seg = f[a:b, i] if vertical else f[i, a:b]
        seg[:] = (seg.astype(np.float32) * (1 - cover) + np.array(colour, np.float32) * cover).round().astype(np.uint8)


def make_lesson(stones=None, size=(720, 1154), x0=252.5, y0=36.9, dx=36.05, dy=None, coords=False, marker=None,
                subtitle=False, wood=(228, 180, 98), lines=19, banner=True):
    """A frame laid out like a lesson video: light wallpaper, a striped banner on the left, a framed wooden board with
    `lines` x `lines` grid lines at sub pixel positions, star points, round stones and optionally a last move marker
    (marker=(point index, 'dot' or 'ring')), coordinate letters in the margin (coords) and a burned in subtitle (white
    strokes with a black outline across the bottom line of the board). stones: {point index (row*18+col): 'B'|'W'}."""
    dy = dy or dx
    H, W = size
    f = np.empty((H, W, 3), np.uint8)
    f[:] = (232, 195, 138)   # wallpaper, as light as the real one
    if banner:   # vertical stripes with a period close to the grid pitch, to tempt a line detector
        f[60:H - 60, 50:150] = (250, 250, 250)
        for x in range(54, 150, 9):
            f[60:H - 60, x:x + 2] = (40, 30, 20)
    n = lines - 1
    mx, my = int(0.9 * dx), int(0.9 * dy)
    bx0, bx1, by0, by1 = int(x0) - mx, int(x0 + n * dx) + mx, int(y0) - my, int(y0 + n * dy) + my
    f[max(by0 - 8, 0):by1 + 8, bx0 - 8:bx1 + 8] = (150, 100, 50)      # the dark frame around the board
    f[max(by0, 0):by1, bx0:bx1] = wood
    ink = (150, 110, 60)
    for k in range(lines):
        _paint_line(f, True, x0 + dx * k, int(round(y0)), int(round(y0 + n * dy)) + 1, ink)
        _paint_line(f, False, y0 + dy * k, int(round(x0)), int(round(x0 + n * dx)) + 1, ink)
    if lines == 19:
        for r in (3, 9, 15):
            for c in (3, 9, 15):
                cx, cy = int(round(x0 + dx * c)), int(round(y0 + dy * r))
                f[cy - 3:cy + 4, cx - 3:cx + 4] = (60, 40, 20)
    if coords:   # dark glyph sized blocks right where the margin check looks for grid lines
        for c in range(19):
            cx = int(round(x0 + dx * c))
            f[int(y0 - 0.55 * dy) - 5:int(y0 - 0.55 * dy) + 5, cx - 3:cx + 3] = (30, 30, 30)
            f[int(y0 + n * dy + 0.55 * dy) - 5:int(y0 + n * dy + 0.55 * dy) + 5, cx - 3:cx + 3] = (30, 30, 30)
        for r in range(19):
            cy = int(round(y0 + dy * r))
            f[cy - 4:cy + 4, int(x0 - 0.55 * dx) - 5:int(x0 - 0.55 * dx) + 5] = (30, 30, 30)
            f[cy - 4:cy + 4, int(x0 + n * dx + 0.55 * dx) - 5:int(x0 + n * dx + 0.55 * dx) + 5] = (30, 30, 30)
    radius = 0.48 * (dx + dy) / 2
    for k, col in (stones or {}).items():
        r, c = divmod(k, COLS)
        cx, cy = x0 + dx * c, y0 + dy * r
        a, b, c0, d0 = int(cy - radius) - 2, int(cy + radius) + 3, int(cx - radius) - 2, int(cx + radius) + 3
        yy, xx = np.mgrid[a:b, c0:d0]
        d2 = (yy - cy) ** 2 + (xx - cx) ** 2
        body, ink2 = ((22, 22, 22), (240, 240, 240)) if col == 'B' else ((244, 244, 250), (25, 25, 25))
        f[a:b, c0:d0][d2 <= radius ** 2] = body
        if marker and marker[0] == k:
            if marker[1] == 'dot':
                f[a:b, c0:d0][d2 <= 4.5 ** 2] = ink2
            else:
                f[a:b, c0:d0][(d2 <= 9 ** 2) & (d2 >= 7 ** 2)] = ink2
    if subtitle:   # strokes of a text line: white bars with a black outline of 1 px in a band over the last grid line
        rng = np.random.RandomState(1)
        top = int(y0 + n * dy) - 12
        for x in range(90, W - 90, 11):
            h = int(rng.randint(10, 30))
            a = top + int(rng.randint(0, 8))
            f[a - 1:a + h + 1, x - 1:x + 5] = (0, 0, 0)
            f[a:a + h, x:x + 4] = (255, 255, 255)
        for x in range(90, W - 90, 37):
            a = top + 14
            f[a - 1:a + 6, x - 1:x + 24] = (0, 0, 0)
            f[a:a + 4, x:x + 22] = (255, 255, 255)
    return f


def truth(stones):
    """The 342 character string a perfect reader gives for these stones."""
    s = ['.'] * (19 * COLS)
    for k, v in stones.items():
        s[k] = v
    return ''.join(s)
