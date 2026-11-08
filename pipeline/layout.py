"""Per video calibration of the board geometry: where are the grid lines in THIS video?

The lesson videos of one series are cut from the same template, but the frame width differs from video to video
(1028..1174 px wide, always 720 high) and the board moves and changes its pitch with it (35.0 to 36.2 px, left edge
at x=197..271, top line at y=30..45). One set of constants cannot fit them, so the geometry is measured:

1. Every grid line is a thin dark dip (about 2 px) in a brightness profile. The profile along x is the median over
   a band of rows (a stone covers a column over less than half of the rows, so the median still shows the line).
   The profile along y is the same over a band of columns inside the board.
2. A comb of 19 evenly spaced teeth is slid over the dips (pitch and offset), the best fit is refined to sub pixel
   accuracy by fitting a straight line through the centres of the dips (_axis), outliers dropped.
3. A comb shifted by one pitch also fits 18 of the 19 lines. The stretch of the grid lines just outside the first
   and the last line must be empty, otherwise the comb is moved by one pitch (_fix_shifts).
4. Several frames of the video vote (calibrate): the layout is the median of the frames that agree. A frame without
   a board (title card, a screen recording of another program) yields no fit and simply does not vote.

Everything is relative to the frame (the board must fill 80..97% of its height), so no pixel constants of one
video are baked in. Pure numpy, no other dependency. See board.py for how the result is used and checked.

Orientation: points are numbered as in the first layout, column 0 (A) at the left and row 0 (line 19) at the top,
index = row * 18 + col, and the whole 19x19 board is always in the frame. The three series show the board that way
(the videos with printed coordinates run A..T from left to right and 19..1 from top to bottom), so nothing is
mirrored or rotated here; the numbering follows the picture and needs no mapping. The 19th column is not read.

Reading (GridReader): a point is a stone when the median brightness of a ring around the crossing is black or white
(the colour limits of the first layout) and the annulus around the ring is almost completely that colour.
"""
import numpy as np

NLINES = 19                      # grid lines per axis
COLS, ROWS = 18, 19              # points that are read (the 19th column is not, see board.py)
SPAN_LO, SPAN_HI = 0.80, 0.97    # 18 pitches / frame height. Seen: 0.88..0.90 in all three series
BAND = (0.2, 0.8)                # rows used for the x profile, as a share of the frame height
CAP = 40.0                       # one dip counts at most this much (a few very dark lines must not decide)
SIGMA = 1.5                      # smoothing of the dips for the coarse comb search, in px
MIN_LINES = 15                   # a frame needs this many of the 19 lines on each axis to give a fit
MAX_RMS = 0.6                    # px, scatter of the line centres around the fitted straight grid
SQUARE_TOL = 0.03                # pitch in x and y may differ by this much (real videos: 0.3%)
MARGIN_LEVEL, MARGIN_PRESENT = 0.5, 0.7   # outside the grid a line counts as present when it is darker than its sides by half the
                                 # usual contrast over 70% of the stretch
AGREE_PX, AGREE_D = 1.0, 0.08    # frames agree when their offsets differ by less than this (px) and pitches by this
MIN_VOTES = 3                    # agreeing frames needed for a video
MIN_AGREE = 0.7                  # ... and this share of the frames that gave a fit at all
MIN_HEIGHT = 360                 # below this the 2 px lines are not resolvable
# Board wood as seen in every lesson video: R 220..240, G 173..183, B 84..106 on the cell centres. The wallpaper around
# the board is about 232,195,138, which these limits keep out (B differs by 40).
WOOD, WOOD_TOL = (230, 179, 95), (25, 20, 22)
WOOD_MIN_CELLS = 0.97            # share of cell centres that must be wood for the board to count as visible. Real frames: 0.98..1.0
                                 # (a burned in subtitle takes a few cells), a dialog window over the board: 0.90. Such a frame is
                                 # skipped (null in b.json) because the white window would be read as rows of white stones.
# Reading a stone (see GridReader.read). Radii are shares of the grid pitch, so they hold at any frame size.
RING = 0.34                      # sampling ring (12 px at a pitch of 35.4). The first layout used 9 px, which touches the
                                 # ring shaped last move marker (radius 8) of the winter camp videos and misses stones there
FILL_FROM, FILL_TO = 0.30, 0.40  # a stone must fill this annulus (10.6 to 14.2 px). The stone has a radius of about 17 px, and
                                 # the annulus stays clear of the last move marker and the move numbers in the middle
FILL_MIN = 0.70                  # share of the annulus that must have the stone colour. Real stones: 0.75..1.0 (a mouse cursor on
                                 # the stone takes some), text of a burned in subtitle over the bottom line: 0.65 at most
FILL_B_LUM = 100                 # annulus pixels count as black below this brightness (the shading of a stone is brighter than the ring test allows)
FILL_W_LUM, FILL_W_SAT = 150, 70   # ... and as white above this brightness and below this saturation (the wood has a saturation of about 130)


class Layout:
    """Board geometry in frame pixels: grid line (c, r) crosses at (x0 + dx*c, y0 + dy*r), c, r = 0..18."""
    __slots__ = ('x0', 'y0', 'dx', 'dy', 'w', 'h', 'kind', 'info')

    def __init__(self, x0, y0, dx, dy, w, h, kind='auto', info=None):
        self.x0, self.y0, self.dx, self.dy, self.w, self.h, self.kind, self.info = float(x0), float(y0), float(dx), float(dy), int(w), int(h), kind, info or {}

    def as_dict(self):
        d = {'kind': self.kind, 'x0': round(self.x0, 2), 'y0': round(self.y0, 2), 'dx': round(self.dx, 3), 'dy': round(self.dy, 3), 'w': self.w, 'h': self.h}
        d.update(self.info)
        return d

    def __repr__(self):
        return 'Layout(%s x0=%.2f y0=%.2f dx=%.3f dy=%.3f %dx%d)' % (self.kind, self.x0, self.y0, self.dx, self.dy, self.w, self.h)


# ------------------------------------------------------------------ one axis

def _dips(p, win=11):
    """Narrow dark dips of a 1-D brightness profile: running median minus the profile, below zero cut off.
    The running median removes everything wider than about win/2 px (stones, the board frame, the banner)."""
    k = win // 2
    pad = np.pad(p, k, mode='edge')
    base = np.median(np.lib.stride_tricks.sliding_window_view(pad, win), axis=1)
    return np.clip(base - p, 0.0, None)


def _smooth(a, sigma):
    r = int(3 * sigma) + 1
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    return np.convolve(a, k / k.sum(), mode='same')


def _coarse(dp, dmin, dmax):
    """Best comb of 19 teeth over the dips: (score, offset, pitch). Offsets in 0.5 px steps, pitches in 0.1 px steps."""
    n = dp.size
    g = _smooth(np.minimum(dp, CAP), SIGMA)
    g2 = np.interp(np.arange(0, n - 1 + 1e-9, 0.5), np.arange(n), g)   # same on a half pixel grid
    k = np.arange(NLINES)
    best = (-1.0, 0.0, 0.0)
    for d in np.arange(dmin, dmax + 1e-9, 0.1):
        m = int((n - 1 - (NLINES - 1) * d) / 0.5) + 1
        if m <= 0:
            continue
        idx = np.arange(m)[:, None] + np.rint(2 * d * k).astype(int)[None, :]
        s = g2[idx].sum(1)
        j = int(np.argmax(s))
        if s[j] > best[0]:
            best = (float(s[j]), j * 0.5, float(d))
    return best


def _centres(dp, c0, d, reach=2.0):
    """(tooth numbers, centres) of the dips found near the predicted lines, centre = weighted mean position."""
    n = dp.size
    ks, cs = [], []
    for k in range(NLINES):
        p = c0 + d * k
        a, b = int(round(p - reach)), int(round(p + reach)) + 1
        if a < 0 or b > n:
            continue
        seg = dp[a:b]
        if seg.max() < 15:
            continue
        w = np.clip(seg - 0.3 * seg.max(), 0, None)
        ks.append(k)
        cs.append(float((w * np.arange(a, b)).sum() / w.sum()))
    return np.array(ks, float), np.array(cs)


def _line_fit(ks, cs):
    """Straight line through (tooth, centre) with outliers dropped: (offset, pitch, inliers, rms) or None."""
    if len(ks) < MIN_LINES:
        return None
    keep = np.ones(len(ks), bool)
    for _ in range(4):
        A = np.vstack([np.ones(int(keep.sum())), ks[keep]]).T
        sol = np.linalg.lstsq(A, cs[keep], rcond=None)[0]
        res = cs - (sol[0] + sol[1] * ks)
        keep = np.abs(res) < 0.6
        if keep.sum() < MIN_LINES:
            return None
    return float(sol[0]), float(sol[1]), int(keep.sum()), float(np.sqrt(np.mean(res[keep] ** 2)))


def _axis(dp, dmin, dmax):
    """Offset and pitch of the 19 lines on one axis from its dips, or None. Returns (c0, d, inliers, rms)."""
    sc, c0, d = _coarse(dp, dmin, dmax)
    if sc <= 0:
        return None
    fit = _line_fit(*_centres(dp, c0, d))
    if fit is None:
        return None
    return fit   # the centres were measured around the coarse comb, so one pass is enough (checked on real frames)


# ------------------------------------------------------------------ one frame

def _beside(lum, vertical, pos, a, b):
    """For every line in `pos`: how much darker the line is than the pixels 3 px beside it, at each position along the
    stretch a..b. vertical=True: lines at columns pos, stretch of rows; False: lines at rows pos, stretch of columns.
    Returns a list with one array per line (lines too close to the frame edge are left out)."""
    h, w = lum.shape
    a, b = int(round(a)), int(round(b))
    a, b = max(a, 0), min(b, h if vertical else w)
    if b - a < 4:
        return []
    out = []
    for p in pos:
        p = int(round(p))
        if vertical:
            if p - 3 < 0 or p + 4 > w:
                continue
            seg = lum[a:b]
            out.append((seg[:, p - 3] + seg[:, p + 3]) / 2 - seg[:, p - 1:p + 2].min(1))
        else:
            if p - 3 < 0 or p + 4 > h:
                continue
            seg = lum[:, a:b]
            out.append((seg[p - 3] + seg[p + 3]) / 2 - seg[p - 1:p + 2].min(0))
    return out


def _clear_outside(lum, vertical, pos, c0, d):
    """For the lines `pos` that span c0 .. c0+18d along the other axis: (clear before the start, clear after the end).

    Clear = no line continues there. A line is present along a stretch when it is darker than its surroundings over
    most of the stretch (a real line: 94%, the letters of a coordinate label in the margin: about half). None = cannot tell."""
    inside = _beside(lum, vertical, pos, c0 + 0.3 * d, c0 + 17.7 * d)
    level = float(np.median([x.mean() for x in inside])) if inside else 0.0
    if level < 10:
        return None, None
    res = []
    for a, b in ((c0 - 0.85 * d, c0 - 0.2 * d), (c0 + 18.2 * d, c0 + 18.85 * d)):
        m = _beside(lum, vertical, pos, a, b)
        res.append(None if not m else float(np.median([(x > MARGIN_LEVEL * level).mean() for x in m])) < MARGIN_PRESENT)
    return res[0], res[1]


def _fix_shifts(lum, x0, y0, dx, dy):
    """Move the comb by whole pitches until the grid lines start and end where the comb says. Returns (x0, y0) or None.

    A comb moved by one pitch still fits 18 of 19 lines, so the fit alone cannot tell. The vertical lines exist only
    between the first and the last horizontal line and vice versa, so the stretch just outside must be empty."""
    h, w = lum.shape
    for _ in range(2):
        xs = x0 + dx * np.arange(NLINES)
        ys = y0 + dy * np.arange(NLINES)
        top, bot = _clear_outside(lum, True, xs, y0, dy)
        left, right = _clear_outside(lum, False, ys, x0, dx)
        moved = False
        for before, after, axis in ((top, bot, 'y'), (left, right, 'x')):
            if before is False and after is not False:
                if axis == 'y':
                    y0 -= dy
                else:
                    x0 -= dx
                moved = True
            elif after is False and before is not False:
                if axis == 'y':
                    y0 += dy
                else:
                    x0 += dx
                moved = True
            elif before is False and after is False:
                return None   # lines on both sides: this is not one 19 line grid
        if not moved:
            return (x0, y0)
        if x0 < 0 or y0 < 0 or x0 + 18 * dx > w - 1 or y0 + 18 * dy > h - 1:
            return None
    return None


def fit_frame(f):
    """Geometry of the board in one frame: a dict (x0, y0, dx, dy, lines, rms) or None when no 19x19 grid is found."""
    h, w = f.shape[:2]
    if h < MIN_HEIGHT:
        return None
    lum = f.astype(np.float32).mean(2)
    dmin, dmax = SPAN_LO * h / 18.0, SPAN_HI * h / 18.0
    px = _axis(_dips(np.median(lum[int(BAND[0] * h):int(BAND[1] * h)], axis=0)), dmin, dmax)
    if px is None:
        return None
    x0, dx, nx, rx = px
    a, b = int(round(max(x0 + 2 * dx, 0))), int(round(min(x0 + 16 * dx, w)))
    if b - a < 4 * dx:
        return None
    py = _axis(_dips(np.median(lum[:, a:b], axis=1)), dx * (1 - SQUARE_TOL), dx * (1 + SQUARE_TOL))
    if py is None:
        return None
    y0, dy, ny, ry = py
    if max(rx, ry) > MAX_RMS:
        return None
    fixed = _fix_shifts(lum, x0, y0, dx, dy)
    if fixed is None:
        return None
    x1, y1 = fixed
    if (x1, y1) != (x0, y0):   # re-measure the line centres with the corrected comb so the inlier counts mean something
        wx = _line_fit(*_centres(_dips(np.median(lum[int(BAND[0] * h):int(BAND[1] * h)], axis=0)), x1, dx))
        a, b = int(round(max(x1 + 2 * dx, 0))), int(round(min(x1 + 16 * dx, w)))
        wy = _line_fit(*_centres(_dips(np.median(lum[:, a:b], axis=1)), y1, dy))
        if wx is None or wy is None:
            return None
        x1, dx, nx, rx = wx
        y1, dy, ny, ry = wy
        if max(rx, ry) > MAX_RMS:
            return None
    if x1 < 0 or y1 < 0 or x1 + 18 * dx > w - 1 or y1 + 18 * dy > h - 1:
        return None
    return {'x0': x1, 'y0': y1, 'dx': dx, 'dy': dy, 'lines': (nx, ny), 'rms': max(rx, ry)}


# ------------------------------------------------------------------ one video

def calibrate(frames):
    """Layout of a video from a sample of its frames. Returns (Layout or None, info dict). info['why'] says why not.

    Frames that show no board give no fit and do not vote. The rest must agree on offset and pitch."""
    fits, shapes = [], set()
    n = 0
    for f in frames:
        shapes.add(f.shape[:2])
        r = fit_frame(f)
        if r:
            r['idx'] = n
            fits.append(r)
        n += 1
    info = {'samples': n, 'fits': len(fits)}
    if not n:
        info['why'] = 'no frames to calibrate on'
        return None, info
    if len(shapes) != 1:
        info['why'] = 'frames of different sizes in one video: %s' % sorted(shapes)
        return None, info
    h, w = shapes.pop()
    if len(fits) < MIN_VOTES:
        info['why'] = 'a 19x19 grid of lines was found in only %d of %d sample frames (need %d): no lesson board in this video, or a layout the detector cannot read' % (len(fits), n, MIN_VOTES)
        return None, info
    med = {k: float(np.median([r[k] for r in fits])) for k in ('x0', 'y0', 'dx', 'dy')}
    agree = [r for r in fits if abs(r['x0'] - med['x0']) < AGREE_PX and abs(r['y0'] - med['y0']) < AGREE_PX
             and abs(r['dx'] - med['dx']) < AGREE_D and abs(r['dy'] - med['dy']) < AGREE_D]
    info['agree'] = len(agree)
    info['agree_idx'] = [r['idx'] for r in agree]
    if len(agree) < MIN_VOTES or len(agree) < MIN_AGREE * len(fits):
        info['why'] = 'the grid sits at different places in different frames (%d of %d fits agree): the layout changes within the video' % (len(agree), len(fits))
        return None, info
    lay = Layout(*[float(np.median([r[k] for r in agree])) for k in ('x0', 'y0', 'dx', 'dy')], w=w, h=h, kind='auto')
    span = 18 * lay.dy / h
    if not SPAN_LO <= span <= SPAN_HI:   # cannot happen with the search range, kept as a guard against edits
        info['why'] = 'the board spans %.0f%% of the frame height (lesson boards: %d..%d%%)' % (100 * span, 100 * SPAN_LO, 100 * SPAN_HI)
        return None, info
    if abs(lay.dx - lay.dy) > SQUARE_TOL * lay.dy:
        info['why'] = 'the grid is not square (pitch %.2f px across, %.2f px down)' % (lay.dx, lay.dy)
        return None, info
    info['spread_px'] = round(max(max(r['x0'] for r in agree) - min(r['x0'] for r in agree), max(r['y0'] for r in agree) - min(r['y0'] for r in agree)), 2)
    return lay, info


# ------------------------------------------------------------------ reading a frame with a layout

class GridReader:
    """Reads stones and checks the board for one Layout. Same three jobs as the fixed layout functions in board.py:
    visible(f), read(f), grid(f)."""

    def __init__(self, lay, lum_black, lum_white, sat_white):
        self.lay = lay
        self.lb, self.lw, self.sw = lum_black, lum_white, sat_white
        self.px = np.rint(lay.x0 + lay.dx * np.arange(COLS)).astype(int)   # x of the columns A..S (the T line is not read)
        self.py = np.rint(lay.y0 + lay.dy * np.arange(ROWS)).astype(int)   # y of the rows 19..1
        pitch = (lay.dx + lay.dy) / 2
        ang = np.linspace(0, 2 * np.pi, 8, endpoint=False)
        self.ox, self.oy = np.rint(RING * pitch * np.cos(ang)).astype(int), np.rint(RING * pitch * np.sin(ang)).astype(int)
        r = int(np.ceil(FILL_TO * pitch))
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        rr = np.sqrt(yy * yy + xx * xx)
        inside = (rr >= FILL_FROM * pitch) & (rr <= FILL_TO * pitch)
        self.dy_, self.dx_ = yy[inside], xx[inside]
        # cell centres can never hold a stone (25 px from the nearest crossing, stones are 17 px in radius)
        self.cx = np.rint(lay.x0 + lay.dx * (np.arange(COLS) + .5)).astype(int)
        self.cy = np.rint(lay.y0 + lay.dy * (np.arange(ROWS - 1) + .5)).astype(int)

    def wood_share(self, f):
        """Share of the 18x18 cell centres that have the colour of the board."""
        v = f[self.cy[:, None], self.cx[None, :]].astype(int)
        ok = (np.abs(v[..., 0] - WOOD[0]) < WOOD_TOL[0]) & (np.abs(v[..., 1] - WOOD[1]) < WOOD_TOL[1]) & (np.abs(v[..., 2] - WOOD[2]) < WOOD_TOL[2])
        return float(ok.mean())

    def visible(self, f):
        return self.wood_share(f) >= WOOD_MIN_CELLS

    def fill(self, f, r, c, black):
        """Share of the annulus around point (row r, column c) that has the colour of a black (or white) stone."""
        h, w = f.shape[:2]
        ys = np.clip(self.py[r] + self.dy_, 0, h - 1)
        xs = np.clip(self.px[c] + self.dx_, 0, w - 1)
        v = f[ys, xs].astype(np.int32)
        lum = v.sum(1) / 3
        if black:
            return float((lum < FILL_B_LUM).mean())
        return float(((lum > FILL_W_LUM) & (v.max(1) - v.min(1) < FILL_W_SAT)).mean())

    def read(self, f):
        """One frame -> COLS*ROWS characters B, W or '.' (index row*18+col, row 0 = the top line).

        A point is a stone when the median brightness of the ring is black or white (the test of the first layout), and
        when the annulus around the ring is that colour almost everywhere. The second test is what the text of a burned
        in subtitle fails: its strokes can fool the ring, but they cannot fill an annulus."""
        ys = self.py[:, None, None] + self.oy[None, None, :]      # (19, 1, 8)
        xs = self.px[None, :, None] + self.ox[None, None, :]      # (1, 18, 8)
        v = f[ys, xs].astype(np.int32)                            # (19, 18, 8, 3)
        lum = np.median(v.sum(3) / 3, axis=2)
        sat = np.median(v.max(3) - v.min(3), axis=2)
        black = lum < self.lb
        white = (lum > self.lw) & (sat < self.sw)
        out = np.full(lum.shape, '.', dtype='<U1')
        for r, c in zip(*np.nonzero(black | white)):
            b = bool(black[r, c])
            if self.fill(f, r, c, b) >= FILL_MIN:
                out[r, c] = 'B' if b else 'W'
        return ''.join(out.ravel())

    def grid(self, f):
        """How much darker are the grid lines than the cells between them? Median over the lines of both axes, the
        weaker axis counts (same definition as board.grid_score, without the offset search: the layout is exact)."""
        lum = f.astype(np.float32).mean(2)
        lay = self.lay
        res = []
        for axis in (0, 1):
            sc = []
            n0, d = (lay.y0, lay.dy) if axis == 0 else (lay.x0, lay.dx)
            o0, od = (lay.x0, lay.dx) if axis == 0 else (lay.y0, lay.dy)
            for k in range(1, 18):
                p, pm = int(round(n0 + d * k)), int(round(n0 + d * (k + .5)))
                span = np.arange(int(o0 + 3), int(o0 + od * 18 - 3))
                if axis == 0:
                    sc.append(np.median(lum[pm - 1:pm + 2, span].min(0)) - np.median(lum[p - 1:p + 2, span].min(0)))
                else:
                    sc.append(np.median(lum[span, pm - 1:pm + 2].min(1)) - np.median(lum[span, p - 1:p + 2].min(1)))
            res.append(float(np.median(sc)))
        return min(res), (0, 0)
