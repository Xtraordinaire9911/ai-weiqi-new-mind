"""How board.py uses the per video calibration (layout.py): choosing the reader, accepting and rejecting whole videos.

Frames are synthetic (tests/synth.py), the ffmpeg parts are tested against a fake process, so neither a video nor
ffmpeg is needed. The first layout (1134x720, fixed constants) must keep giving exactly what it always gave.
"""
import json
import os
import subprocess

import numpy as np
import pytest

import board
import layout
from synth import LAYOUTS, make_frame, make_lesson, truth

STONES = {0: 'B', 17: 'W', 69: 'B', 106: 'W', 52: 'B', 87: 'W', 324: 'B', 341: 'W', 200: 'W', 201: 'B', 250: 'B', 251: 'W', 252: 'B'}


def lesson(name, stones=STONES, **kw):
    g = dict(LAYOUTS[name])
    g.update(kw)
    return make_lesson(stones, **g)


def size_of(name):
    h, w = LAYOUTS[name]['size']
    return (w, h)


def run(tmp_path, frames, size):
    out = str(tmp_path / 'b.json')
    return board.run('video.mp4', out, 'ffmpeg', frames=frames, size=size), out


def reasons(tmp_path):
    return json.load(open(str(tmp_path / 'b.rej.json'), encoding='utf-8'))['reasons']


@pytest.mark.parametrize('name', ['wide', 'narrow', 'labelled'])
def test_a_video_with_a_new_layout_is_accepted_and_read(tmp_path, name):
    frames = [lesson(name)] * 14
    rc, out = run(tmp_path, frames, size_of(name))
    assert rc == 0
    data = json.load(open(out))
    assert len(data) == 14 and all(s == truth(STONES) for _, s in data)
    meta = json.load(open(str(tmp_path / 'b.meta.json')))
    assert meta['layout']['kind'] == 'auto' and abs(meta['layout']['x0'] - LAYOUTS[name]['x0']) < 0.3
    assert meta['board_frames'] == 14 and meta['grid_scores'][0] > board.MIN_GRID_SCORE


def test_frames_that_are_not_the_board_become_null_in_a_new_layout(tmp_path):
    rng = np.random.RandomState(7)
    other = rng.randint(0, 256, (720, 1154, 3)).astype(np.uint8)
    frames = [lesson('wide')] * 12 + [other] * 3
    rc, out = run(tmp_path, frames, size_of('wide'))
    assert rc == 0
    data = json.load(open(out))
    assert [s is None for _, s in data] == [False] * 12 + [True] * 3


def test_a_burned_in_subtitle_does_not_put_stones_into_b_json(tmp_path):
    top_only = {k: v for k, v in STONES.items() if k < 324}
    rc, out = run(tmp_path, [lesson('narrow', top_only, subtitle=True)] * 12, size_of('narrow'))
    assert rc == 0
    assert all(s == truth(top_only) for _, s in json.load(open(out)))


def test_a_shifted_board_of_the_first_size_is_found_by_calibration(tmp_path):
    # this used to be the "another layout is rejected" case: the board is 12 px off the constants of the first layout
    frames = [make_frame(STONES, X0=260.0)] * 14
    rc, out = run(tmp_path, frames, (1134, 720))
    assert rc == 0
    meta = json.load(open(str(tmp_path / 'b.meta.json')))
    assert meta['layout']['kind'] == 'auto' and abs(meta['layout']['x0'] - 259.5) < 1.0
    assert json.load(open(out))[0][1] == truth(STONES)


def test_the_first_layout_keeps_its_constants_and_its_exact_reader(tmp_path):
    frames = [make_frame(STONES)] * 14
    rc, out = run(tmp_path, frames, (1134, 720))
    assert rc == 0
    assert json.load(open(str(tmp_path / 'b.meta.json')))['layout'] == {'kind': 'legacy', 'x0': 248.0, 'y0': 40.0, 'dx': 35.4, 'dy': 35.4, 'w': 1134, 'h': 720}
    assert json.load(open(out)) == [[i / 6, board.read_board(frames[0])] for i in range(14)]


def test_the_constants_of_the_first_layout_never_change():
    # regression anchor: a change here renumbers or shifts every point in every cached b.json of series 1
    assert (board.W, board.H, board.X0, board.Y0, board.D, board.COLS, board.ROWS) == (1134, 720, 248.0, 40.0, 35.4, 18, 19)
    assert (layout.COLS, layout.ROWS) == (board.COLS, board.ROWS), 'both readers must number the points the same way (row * 18 + col)'
    assert (board.LUM_BLACK, board.LUM_WHITE, board.SAT_WHITE, board.FPS) == (75, 185, 45, 6)
    assert board.OX.tolist() == [9, 6, 0, -6, -9, -6, 0, 6] and board.OY.tolist() == [0, 6, 9, 6, 0, -6, -9, -6]
    assert len(board.PTS) == 342 and board.PTS[0] == (248, 40) and board.PTS[17] == (850, 40) and board.PTS[-1] == (850, 677)
    assert board.PTS[18] == (248, 75) and board.PTS[19] == (283, 75)


def test_noise_is_rejected_with_the_reason(tmp_path, capsys):
    rng = np.random.RandomState(11)
    frames = [rng.randint(0, 256, (720, 1154, 3)).astype(np.uint8) for _ in range(10)]
    rc, out = run(tmp_path, frames, (1154, 720))
    assert rc == 3 and not os.path.exists(out)
    assert any('19x19 grid of lines was found in only 0 of 10' in r for r in reasons(tmp_path))
    assert 'REJECTED' in capsys.readouterr().err


def test_a_board_with_fewer_lines_is_rejected(tmp_path):
    frames = [make_lesson(None, lines=13, dx=50, dy=50, x0=250, y0=60)] * 10
    rc, _ = run(tmp_path, frames, (1154, 720))
    assert rc == 3 and any('19x19 grid' in r for r in reasons(tmp_path))


def test_a_pale_board_is_rejected_because_the_stone_colours_would_not_fit(tmp_path):
    frames = [lesson('wide', wood=(250, 240, 200))] * 10
    rc, _ = run(tmp_path, frames, size_of('wide'))
    assert rc == 3 and any('not the wood colour' in r for r in reasons(tmp_path))


def test_a_video_that_is_too_small_is_rejected(tmp_path):
    rc, _ = run(tmp_path, [np.zeros((300, 640, 3), np.uint8)] * 5, (640, 300))
    assert rc == 3 and 'too small' in reasons(tmp_path)[0]


def test_frames_that_do_not_match_the_video_size_are_rejected(tmp_path):
    rc, _ = run(tmp_path, [make_frame(STONES)] * 5, (1280, 720))
    assert rc == 3 and 'decoded frames are 1134x720 but the video says 1280x720' in reasons(tmp_path)[0]


def test_a_board_that_moves_inside_the_video_is_rejected(tmp_path):
    a, b = lesson('wide'), lesson('wide', x0=LAYOUTS['wide']['x0'] + 20)
    rc, _ = run(tmp_path, [a, b] * 6, size_of('wide'))
    assert rc == 3 and any('different places' in r for r in reasons(tmp_path))


# ---------------------------------------------------------------- ffmpeg plumbing without ffmpeg

class FakePopen:
    """Stands in for subprocess.Popen: hands out `n` frames of `shape` as raw bytes and remembers the command line."""
    cmds = []

    def __init__(self, cmd, stdout=None, stderr=None):
        import io
        FakePopen.cmds.append(cmd)
        self.stdout = io.BytesIO(FakePopen.payload)

    def poll(self):
        return None

    def kill(self):
        pass

    def wait(self):
        return 0


def test_ffmpeg_command_lines_for_the_old_and_the_new_decoding(monkeypatch):
    h, w = 6, 10
    FakePopen.cmds = []
    FakePopen.payload = bytes(range(250)) * 1 + bytes(10 * 6 * 3 * 2)   # more than the three frames asked for below
    monkeypatch.setattr(board.subprocess, 'Popen', FakePopen)
    src = board.FfmpegFrames('ff', 'v.mp4', size=(w, h), duration=60.0)
    got = src.sample(3)
    assert len(got) == 3 and got[0].shape == (h, w, 3)
    cmd = FakePopen.cmds[-1]
    assert cmd[cmd.index('-vf') + 1] == 'fps=0.050000' and cmd[cmd.index('-frames:v') + 1] == '3' and cmd[cmd.index('-ss') + 1] == '10.000'
    src.legacy = True
    FakePopen.payload = bytes(1134 * 720 * 3)
    assert len(list(src)) == 1
    assert FakePopen.cmds[-1][FakePopen.cmds[-1].index('-vf') + 1] == 'fps=6,scale=1134:720', 'the first layout is decoded exactly as before'
    src.legacy = False
    FakePopen.payload = bytes(w * h * 3 * 2)
    assert len(list(src)) == 2
    assert FakePopen.cmds[-1][FakePopen.cmds[-1].index('-vf') + 1] == 'fps=6', 'a measured layout is decoded at the real size, without scaling'


def test_probe_info_reads_size_and_length(monkeypatch):
    err = (b"  Duration: 00:05:52.11, start: 0.000000, bitrate: 400 kb/s\n"
           b"  Stream #0:0[0x1](und): Video: h264 (High), yuv420p(tv, bt709), 1032x720 [SAR 1:1 DAR 43:30], 30 fps\n")
    monkeypatch.setattr(board.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 1, b'', err))
    assert board.probe_info('ffmpeg', 'x.mp4') == ((1032, 720), pytest.approx(352.11))
    monkeypatch.setattr(board.subprocess, 'run', lambda *a, **k: subprocess.CompletedProcess(a, 1, b'', b'nothing'))
    assert board.probe_info('ffmpeg', 'x.mp4') == (None, None)


def test_a_file_without_a_video_stream_is_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(board, 'probe_info', lambda ff, p: (None, None))
    rc = board.run('x.mp4', str(tmp_path / 'b.json'), 'ffmpeg')
    assert rc == 3 and 'could not read the video size' in reasons(tmp_path)[0]


def test_frames_may_come_from_a_generator(tmp_path):
    # the calibration sample must not use up an iterator that the real pass still needs
    rc, out = run(tmp_path, (lesson('narrow') for _ in range(12)), size_of('narrow'))
    assert rc == 0 and len(json.load(open(out))) == 12
