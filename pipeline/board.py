"""Board recognition: video frames -> b.json = [[t_seconds, "<342 chars of . B W>" or null], ...] at 6 fps.

Usage: board.py video.mp4 out.json path/to/ffmpeg

Where the board sits differs from video to video (the frame is 1028..1174 px wide, the board moves with it), so
the geometry is measured per video before any stone is read (layout.py): a few sample frames are decoded, the 19
grid lines are located in each, and the frames vote. Videos of exactly 1134x720 whose frames fit the first layout
(board at X0/Y0 with pitch D, the constants below) are still read with those constants, so their results are
byte for byte what they always were.
For a video that is no lesson board the recogniser used to produce garbage without a word, and the tree builder
then built a tree from it. So the geometry and the run are checked (see calibrate_video and assess): a 19x19 grid
must be found, the board must have the wood colour, enough frames must show the board, the grid lines must sit
where the geometry says and stones must be seen, but not absurdly many.
A video that fails is rejected: no b.json, a b.rej.json with the reasons, exit code 3.
"""
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

import layout
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
SAMPLES = 40                                                              # frames spread over the video that calibrate its geometry
MIN_HEIGHT = layout.MIN_HEIGHT                                            # shorter frames cannot resolve the 2 px grid lines


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


class LegacyReader:
    """The first layout (1134x720, constants above) with the original functions, untouched: results stay byte for byte the same."""
    kind = 'legacy'
    visible = staticmethod(board_visible)
    read = staticmethod(read_board)
    grid = staticmethod(grid_score)

    def describe(self):
        return {'kind': 'legacy', 'x0': X0, 'y0': Y0, 'dx': D, 'dy': D, 'w': W, 'h': H}


class AutoReader(layout.GridReader):
    """A layout measured on this video (layout.py), read with the same colour thresholds as the first layout."""
    kind = 'auto'

    def __init__(self, lay):
        super().__init__(lay, LUM_BLACK, LUM_WHITE, SAT_WHITE)

    def describe(self):
        return self.lay.as_dict()


def analyse_frames(frames, reader=None):
    """Run the recogniser over an iterable of HxWx3 frames. Returns (out, stats).

    out = [[t, string or None], ...]; stats feed assess(). `reader` knows the geometry (LegacyReader when not given).
    """
    rd = reader or LegacyReader()
    out, grid, offsets, stones = [], [], [], []
    for i, f in enumerate(frames):
        if rd.visible(f):
            s = rd.read(f)
            out.append([i / FPS, s])
            stones.append(sum(1 for ch in s if ch != '.'))
            if len(stones) % GRID_EVERY == 1:
                sc, off = rd.grid(f)
                grid.append(sc)
                offsets.append(off)
        else:
            out.append([i / FPS, None])
    st = sorted(stones)
    return out, {'frames': len(out), 'board_frames': len(stones), 'grid_scores': [round(x, 1) for x in grid], 'grid_offsets': offsets,
                 'stones_median': st[len(st) // 2] if st else 0, 'stones_max': st[-1] if st else 0, 'layout': rd.describe()}


def assess(stats, size=None, ffmpeg_rc=0, ffmpeg_err=''):
    """Reasons to reject the recognition (empty list = accept)."""
    why = []
    if size and size[1] < MIN_HEIGHT:
        why.append('video is %dx%d: too small to resolve the grid lines (need a height of at least %d)' % (size[0], size[1], MIN_HEIGHT))
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
            why.append('grid lines do not line up with the board position found (score %.0f, need %.0f): the layout differs' % (g, MIN_GRID_SCORE))
    if stats['board_frames'] and stats['stones_max'] == 0:
        why.append('board frames found but not a single stone recognised (colour thresholds do not fit this video)')
    if stats['stones_median'] > MAX_MEDIAN_STONES:
        why.append('median %d stones per frame: the stone thresholds read the wood or the grid as stones' % stats['stones_median'])
    return why


def probe_info(ff, path):
    """((width, height), seconds) of the first video stream from `ffmpeg -i`; None for what cannot be read."""
    try:
        r = subprocess.run([ff, '-hide_banner', '-i', path], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    err = r.stderr.decode('utf-8', 'replace')
    m = re.search(r'Video:.*?\b(\d{2,5})x(\d{2,5})\b', err)
    d = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', err)
    return ((int(m.group(1)), int(m.group(2))) if m else None,
            int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else None)


def probe_size(ff, path):
    """(width, height) of the first video stream from `ffmpeg -i`, or None."""
    return probe_info(ff, path)[0]


class FfmpegFrames:
    """Iterate the decoded frames of a video at 6 fps; afterwards .rc and .err hold ffmpeg's exit code and stderr.

    legacy=True scales every frame to 1134x720 as the first recogniser always did (a no-op for a video of that size).
    legacy=False decodes at the size of the video, because the measured geometry (layout.py) is in real pixels."""

    def __init__(self, ff, path, size=None, duration=None, legacy=True):
        self.ff, self.path, self.size, self.duration, self.legacy, self.rc, self.err = ff, path, size, duration, legacy, 0, ''

    def _run(self, args, w, h, limit=None):
        cmd = [self.ff, '-v', 'error'] + args + ['-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
        with tempfile.TemporaryFile() as errf:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errf)
            try:
                n = 0
                while limit is None or n < limit:
                    b = p.stdout.read(w * h * 3)
                    if len(b) < w * h * 3:
                        break
                    n += 1
                    yield np.frombuffer(b, np.uint8).reshape(h, w, 3)
            finally:
                p.stdout.close()
                if limit is not None and p.poll() is None:
                    p.kill()   # enough frames: do not decode the rest of the video
                self.rc = p.wait()
                errf.seek(0)
                self.err = errf.read().decode('utf-8', 'replace')

    def __iter__(self):
        if self.legacy or not self.size:
            return self._run(['-i', self.path, '-vf', 'fps=%d,scale=%d:%d' % (FPS, W, H)], W, H)
        return self._run(['-i', self.path, '-vf', 'fps=%d' % FPS], self.size[0], self.size[1])

    def sample(self, n=SAMPLES):
        """n frames spread over the video, at the size of the video (calibration needs the real pixels)."""
        w, h = self.size
        dur = self.duration
        fps, start = (n / dur, dur / (2.0 * n)) if dur else (0.1, 0.0)   # unknown length: one frame every 10 s
        frames = list(self._run(['-ss', '%.3f' % start, '-i', self.path, '-vf', 'fps=%.6f' % fps, '-frames:v', str(n)], w, h, limit=n))
        self.rc, self.err = 0, ''   # a failing decode shows up again in the main pass, which is the one that is checked
        return frames


def take_sample(src, n=SAMPLES):
    """Frames to calibrate on: from the video, or evenly spaced out of a list (tests pass lists)."""
    if hasattr(src, 'sample'):
        return src.sample(n)
    seq = src if isinstance(src, (list, tuple)) else list(src)
    return list(seq[::max(1, len(seq) // n)][:n])


def calibrate_video(sample, size=None):
    """Which geometry reads this video? Returns (reader, info); reader is None when the video is rejected, info['why'] says why.

    1. 1134x720 frames that fit the first layout are read exactly as before (LegacyReader), whatever else would be found.
    2. Everything else is measured (layout.calibrate): a 19x19 grid must be found in most sample frames, and at the
       same place, and the board must have the wood colour of the lesson boards."""
    info = {'samples': len(sample)}
    shapes = {f.shape[:2] for f in sample}
    if len(shapes) > 1:
        info['why'] = 'frames of different sizes in one video: %s' % sorted(shapes)
        return None, info
    if size and shapes and shapes != {(size[1], size[0])}:
        got = list(shapes)[0]
        info['why'] = 'decoded frames are %dx%d but the video says %dx%d' % (got[1], got[0], size[0], size[1])
        return None, info
    if size and size[1] < MIN_HEIGHT:
        info['why'] = 'video is %dx%d: too small to resolve the grid lines (need a height of at least %d)' % (size[0], size[1], MIN_HEIGHT)
        return None, info
    if not sample:
        return LegacyReader(), info   # nothing to calibrate on: analyse_frames reports the missing frames
    if shapes == {(H, W)}:
        boards = [f for f in sample if board_visible(f)]
        if len(boards) >= layout.MIN_VOTES:
            sc = sorted(grid_score(f)[0] for f in boards)
            if sc[len(sc) // 2] >= MIN_GRID_SCORE:
                return LegacyReader(), info
    lay, linfo = layout.calibrate(sample)
    info.update(linfo)
    if lay is None:
        return None, info
    rd = AutoReader(lay)
    shares = sorted(rd.wood_share(sample[i]) for i in linfo['agree_idx'])
    info['wood'] = round(shares[len(shares) // 2], 3)
    if info['wood'] < layout.WOOD_MIN_CELLS:
        info['why'] = 'a 19x19 grid was found but the board is not the wood colour of the lesson boards (%d%% of the cell centres, need %d%%)' % (100 * info['wood'], 100 * layout.WOOD_MIN_CELLS)
        return None, info
    lay.info = {k: info[k] for k in ('samples', 'fits', 'agree', 'spread_px', 'wood') if k in info}   # goes into b.meta.json
    return rd, info


def run(video, out_path, ff, frames=None, size=None):
    """Calibrate, recognise, check, then write b.json (+ b.meta.json) or b.rej.json. Returns the exit code (0 ok, 3 rejected)."""
    base = os.path.splitext(out_path)[0]

    def reject(why, stats):
        atomic_write_json(base + '.rej.json', {'reasons': why, 'stats': stats}, ensure_ascii=False, indent=1)
        print('REJECTED %s: %s' % (video, '; '.join(why)), file=sys.stderr)
        return 3

    src = frames
    if src is not None and not isinstance(src, (list, tuple)):
        src = list(src)   # an iterator would be used up by the calibration sample before the real pass sees it
    if src is None:
        psize, dur = probe_info(ff, video)
        size = size or psize
        if size is None:
            return reject(['could not read the video size: ffmpeg found no video stream in the file'], {})
        src = FfmpegFrames(ff, video, size, dur)
    reader, info = calibrate_video(take_sample(src), size)
    if reader is None:
        return reject([info['why']], {'layout': info})
    if isinstance(src, FfmpegFrames):
        src.legacy = reader.kind == 'legacy'
    out, stats = analyse_frames(src, reader)
    why = assess(stats, size, getattr(src, 'rc', 0), getattr(src, 'err', ''))
    if why:
        return reject(why, stats)
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
