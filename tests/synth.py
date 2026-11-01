"""Synthetic video frames for the board recognition tests: wood background, grid lines, round stones."""
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
