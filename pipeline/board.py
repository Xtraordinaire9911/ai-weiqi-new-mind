"""Board recognition: video frames -> b.json = [[t_seconds, "<342 chars of . B W>" or null], ...] at 6 fps.

Usage: board.py video.mp4 out.json path/to/ffmpeg

The recogniser only works for the layout of the lesson videos (1134x720, board at X0/Y0 with pitch D).
For any other layout it used to produce garbage without a word, and the tree builder then built a tree from it.
So before writing anything the run is checked (see assess): video size, how many frames show the board at
all, whether the grid lines sit where the geometry says, whether stones were seen and not absurdly many.
A video that fails is rejected: no b.json, a b.rej.json with the reasons, exit code 3.
"""
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

from wqutil import atomic_write_json, setup_stdio

# ---- geometry and colour thresholds, tuned on 1134x720 frames of the lesson videos
W, H = 1134, 720
X0, Y0, D = 248.0, 40.0, 35.4
COLS, ROWS = 18, 19   # points that are read. The board has 19 columns; the last one is not read, so stones on that line are invisible.
                      # Changing this would renumber every point (row*18+col) in every cache file, so it is documented, not changed.
LUM_BLACK, LUM_WHITE, SAT_WHITE = 75, 185, 45
FPS = 6
ANG = np.linspace(0, 2 * np.pi, 8, endpoint=False)
OX, OY = (9 * np.cos(ANG)).round().astype(int), (9 * np.sin(ANG)).round().astype(int)
PTS = [(int(round(X0 + D * c)), int(round(Y0 + D * r))) for r in range(ROWS) for c in range(COLS)]

# ---- self check limits (real videos: board visible in 99.6..100% of frames, grid score 46..91, median 6..23 stones; other layouts score 0..2)
MIN_BOARD_RATIO = float(os.environ.get('WEIQI_MIN_BOARD_RATIO', '0.5'))   # share of frames that show the board background
MIN_GRID_SCORE = float(os.environ.get('WEIQI_MIN_GRID_SCORE', '20'))      # grid lines must be this much darker than the cells between them
MAX_MEDIAN_STONES = 150                                                  # a lesson board never has this many stones
GRID_REACH = 4                                                            # +-pixels the grid may sit off the expected position (real videos: up to 3)
GRID_EVERY = 30                                                           # check the grid on every 30th board frame (5 s)


def board_visible(f):
    """Is the board background where we expect it? (A single wood coloured pixel, as before.)"""
    return abs(int(f[200, 300, 0]) - 225) < 40 and abs(int(f[200, 300, 2]) - 85) < 60


def read_board(f):
    """One frame -> string of COLS*ROWS characters: B, W or '.'"""
    s = []
    for x, y in PTS:
        v = f[y + OY, x + OX].astype(int)
        lum = np.median(v.sum(1) / 3)
        sat = np.median(v.max(1) - v.min(1))
        s.append('B' if lum < LUM_BLACK else ('W' if lum > LUM_WHITE and sat < SAT_WHITE else '.'))
    return ''.join(s)


def grid_score(f, x0=X0, y0=Y0, d=D, reach=GRID_REACH):
    """How well do the grid lines sit where the geometry says? Returns (score, (dx, dy)).

    For each axis the offset within +-reach pixels that fits best is taken (the real videos differ by 1..3 px, which the
    stone reader tolerates), and the score is the median over that axis' lines of (cell between the lines - the line), in
    luminance. The result is the weaker axis, so both directions must line up. Real frames: 20..90. A different layout
    (other offset, other pitch, other board position) gives about 0..5.
    """
    lum = f.astype(np.float32).mean(2)
    best = []
    for axis in (0, 1):   # 0: horizontal lines (offset in y), 1: vertical lines (offset in x)
        top = None
        for off in range(-reach, reach + 1):
            sc = []
            for k in range(1, 18):
                p, pm = int(round((y0 if axis == 0 else x0) + off + d * k)), int(round((y0 if axis == 0 else x0) + off + d * (k + .5)))
                if axis == 0:
                    xs = np.arange(int(x0 + 3), min(W - 2, int(x0 + d * 18 - 3)))
                    if pm + 2 >= H:
                        break
                    sc.append(np.median(lum[pm - 1:pm + 2, xs].min(0)) - np.median(lum[p - 1:p + 2, xs].min(0)))
                else:
                    ys = np.arange(int(y0 + 3), min(H - 2, int(y0 + d * 18 - 3)))
                    if pm + 2 >= W:
                        break
                    sc.append(np.median(lum[ys, pm - 1:pm + 2].min(1)) - np.median(lum[ys, p - 1:p + 2].min(1)))
            v = float(np.median(sc)) if sc else 0.0
            if top is None or v > top[0]:
                top = (v, off)
        best.append(top)
    return min(best[0][0], best[1][0]), (best[1][1], best[0][1])


def analyse_frames(frames):
    """Run the recogniser over an iterable of HxWx3 frames. Returns (out, stats).

    out = [[t, string or None], ...]; stats feed assess().
    """
    out, grid, offsets, stones = [], [], [], []
    for i, f in enumerate(frames):
        if board_visible(f):
            s = read_board(f)
            out.append([i / FPS, s])
            stones.append(sum(1 for ch in s if ch != '.'))
            if len(stones) % GRID_EVERY == 1:
                sc, off = grid_score(f)
                grid.append(sc)
                offsets.append(off)
        else:
            out.append([i / FPS, None])
    st = sorted(stones)
    return out, {'frames': len(out), 'board_frames': len(stones), 'grid_scores': [round(x, 1) for x in grid], 'grid_offsets': offsets,
                 'stones_median': st[len(st) // 2] if st else 0, 'stones_max': st[-1] if st else 0}


def assess(stats, size=None, ffmpeg_rc=0, ffmpeg_err=''):
    """Reasons to reject the recognition (empty list = accept)."""
    why = []
    if size and (size[0], size[1]) != (W, H):
        why.append('video is %dx%d, the recogniser is built for %dx%d' % (size[0], size[1], W, H))
    if ffmpeg_rc:
        why.append('ffmpeg exited with code %d: %s' % (ffmpeg_rc, ffmpeg_err.strip()[-200:]))
    if stats['frames'] == 0:
        why.append('no frames could be decoded (corrupt or unreadable file)')
        return why
    ratio = stats['board_frames'] / stats['frames']
    if ratio < MIN_BOARD_RATIO:
        why.append('only %d%% of the frames show the board background (need %d%%): different layout or not a lesson video?' % (100 * ratio, 100 * MIN_BOARD_RATIO))
    elif stats['grid_scores']:
        g = sorted(stats['grid_scores'])[len(stats['grid_scores']) // 2]
        if g < MIN_GRID_SCORE:
            why.append('grid lines do not line up with the expected board position (score %.0f, need %.0f): the layout differs' % (g, MIN_GRID_SCORE))
    if stats['board_frames'] and stats['stones_max'] == 0:
        why.append('board frames found but not a single stone recognised (colour thresholds do not fit this video)')
    if stats['stones_median'] > MAX_MEDIAN_STONES:
        why.append('median %d stones per frame: the stone thresholds read the wood or the grid as stones' % stats['stones_median'])
    return why


def probe_size(ff, path):
    """(width, height) of the first video stream from `ffmpeg -i`, or None."""
    try:
        r = subprocess.run([ff, '-hide_banner', '-i', path], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r'Video:.*?\b(\d{2,5})x(\d{2,5})\b', r.stderr.decode('utf-8', 'replace'))
    return (int(m.group(1)), int(m.group(2))) if m else None


class FfmpegFrames:
    """Iterate the decoded frames of a video; afterwards .rc and .err hold ffmpeg's exit code and stderr."""

    def __init__(self, ff, path):
        self.ff, self.path, self.rc, self.err = ff, path, 0, ''

    def __iter__(self):
        cmd = [self.ff, '-v', 'error', '-i', self.path, '-vf', 'fps=%d,scale=%d:%d' % (FPS, W, H), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        with tempfile.TemporaryFile() as errf:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errf)
            while True:
                b = p.stdout.read(W * H * 3)
                if len(b) < W * H * 3:
                    break
                yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
            self.rc = p.wait()
            errf.seek(0)
            self.err = errf.read().decode('utf-8', 'replace')


def run(video, out_path, ff, frames=None, size=None):
    """Recognise, check, then write b.json (+ b.meta.json) or b.rej.json. Returns the exit code (0 ok, 3 rejected)."""
    src = frames if frames is not None else FfmpegFrames(ff, video)
    out, stats = analyse_frames(src)
    if size is None and frames is None:
        size = probe_size(ff, video)
    why = assess(stats, size, getattr(src, 'rc', 0), getattr(src, 'err', ''))
    base = os.path.splitext(out_path)[0]
    if why:
        atomic_write_json(base + '.rej.json', {'reasons': why, 'stats': stats}, ensure_ascii=False, indent=1)
        print('REJECTED %s: %s' % (video, '; '.join(why)), file=sys.stderr)
        return 3
    atomic_write_json(out_path, out)
    atomic_write_json(base + '.meta.json', stats, indent=1)   # kept next to b.json so a weak video can be spotted later
    print(len(out), stats['board_frames'])
    return 0


def main(argv=None):
    setup_stdio()
    a = argv if argv is not None else sys.argv
    if len(a) < 4:
        print(__doc__, file=sys.stderr)
        return 1
    return run(a[1], a[2], a[3])


if __name__ == '__main__':
    sys.exit(main())
