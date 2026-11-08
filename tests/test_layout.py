"""Per video board calibration (layout.py): measuring the grid and reading stones with it.

Where the board sits differs from video to video, so the geometry is measured on sample frames. Every frame here is
synthetic (tests/synth.py): wallpaper, banner, framed wooden board, grid lines at sub pixel positions, round stones.
No frame of any video is used or stored. The geometries are invented around the ranges seen on the real videos.
"""
import numpy as np
import pytest

import layout
from synth import LAYOUTS, make_lesson, truth

STONES = {0: 'B', 17: 'W', 69: 'B', 106: 'W', 52: 'B', 87: 'W', 324: 'B', 341: 'W', 200: 'W', 201: 'B', 250: 'B', 251: 'W', 252: 'B'}
NAMES = sorted(LAYOUTS)
BLACK, WHITE, SAT = 75, 185, 45   # the colour limits used by the recogniser


def reader(g, w=1154):
    return layout.GridReader(layout.Layout(g['x0'], g['y0'], g['dx'], g['dy'], w, 720), BLACK, WHITE, SAT)


def lesson(name, stones=STONES, **kw):
    g = dict(LAYOUTS[name])
    g.update(kw)
    return make_lesson(stones, **g)


def size_of(name):
    h, w = LAYOUTS[name]['size']
    return (w, h)


def close(r, name, tol=0.3):
    g = LAYOUTS[name]
    return (abs(r['x0'] - g['x0']) < tol and abs(r['y0'] - g['y0']) < tol and abs(r['dx'] - g['dx']) < 0.03 and abs(r['dy'] - g['dy']) < 0.03)


# ---------------------------------------------------------------- one frame

@pytest.mark.parametrize('name', NAMES)
def test_every_layout_is_measured_to_a_fraction_of_a_pixel(name):
    r = layout.fit_frame(lesson(name))
    assert r is not None and close(r, name), (name, r)
    assert r['lines'] == (19, 19)


@pytest.mark.parametrize('name', NAMES)
def test_an_empty_board_is_measured_too(name):
    r = layout.fit_frame(lesson(name, stones=None))
    assert r is not None and close(r, name)


def test_the_comb_is_not_taken_one_pitch_off():
    # a comb moved by one pitch fits 18 of 19 lines; the margin check has to move it back (also with letters in the margin)
    for name in ('wide', 'labelled'):
        f = lesson(name)
        g = LAYOUTS[name]
        lum = f.astype(np.float32).mean(2)
        for sx, sy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            got = layout._fix_shifts(lum, g['x0'] + sx * g['dx'], g['y0'] + sy * g['dy'], g['dx'], g['dy'])
            assert got is not None, (name, sx, sy)
            assert abs(got[0] - g['x0']) < 0.5 and abs(got[1] - g['y0']) < 0.5, (name, sx, sy, got)


def test_no_grid_in_noise_a_blank_card_or_a_small_board():
    rng = np.random.RandomState(3)
    assert layout.fit_frame(rng.randint(0, 256, (720, 1134, 3)).astype(np.uint8)) is None
    assert layout.fit_frame(np.full((720, 1134, 3), (30, 120, 40), np.uint8)) is None
    assert layout.fit_frame(make_lesson(STONES, size=(720, 1154), x0=300, y0=100, dx=20, dy=20)) is None, 'the board fills half the height only'
    assert layout.fit_frame(make_lesson(None, lines=13, dx=50, dy=50, x0=250, y0=60)) is None, 'a 13 line board'
    assert layout.fit_frame(np.zeros((300, 640, 3), np.uint8)) is None, 'too small'


# ---------------------------------------------------------------- one video

def test_calibrate_takes_the_vote_of_the_frames_that_show_a_board():
    card = np.full((720, 1154, 3), (30, 120, 40), np.uint8)
    frames = [card] + [lesson('wide', {k: 'B'}) for k in (3, 40, 90, 120, 160)] + [card]
    lay, info = layout.calibrate(frames)
    assert lay is not None and lay.kind == 'auto'
    assert info['fits'] == 5 and info['agree'] == 5 and info['agree_idx'] == [1, 2, 3, 4, 5]
    g = LAYOUTS['wide']
    assert abs(lay.x0 - g['x0']) < 0.3 and abs(lay.dy - g['dy']) < 0.03 and (lay.w, lay.h) == (1154, 720)


def test_calibrate_needs_a_few_frames_with_a_board():
    lay, info = layout.calibrate([lesson('wide')] * 2)
    assert lay is None and 'only 2 of 2' in info['why']
    lay, info = layout.calibrate([])
    assert lay is None and 'no frames' in info['why']


def test_calibrate_rejects_a_video_whose_board_moves():
    a, b = lesson('wide'), lesson('wide', x0=LAYOUTS['wide']['x0'] + 20)
    lay, info = layout.calibrate([a, b, a, b, a, b])
    assert lay is None and 'different places' in info['why']


# ---------------------------------------------------------------- reading stones

@pytest.mark.parametrize('name', NAMES)
def test_stones_are_read_at_the_right_points_in_every_layout(name):
    f = lesson(name)
    r = layout.fit_frame(f)
    rd = layout.GridReader(layout.Layout(r['x0'], r['y0'], r['dx'], r['dy'], f.shape[1], f.shape[0]), BLACK, WHITE, SAT)
    assert rd.read(f) == truth(STONES)
    assert rd.visible(f) and rd.grid(f)[0] > 20


@pytest.mark.parametrize('mark', ['dot', 'ring'])
def test_last_move_markers_do_not_hide_stones(mark):
    # a ring shaped marker (radius 8) sits right under a sampling ring of 9 px; the reader samples outside of it
    stones = {k: v for k, v in STONES.items()}
    f = lesson('wide', stones, marker=(69, mark))
    rd = reader(LAYOUTS['wide'])
    assert rd.read(f) == truth(stones)
    f = lesson('wide', stones, marker=(106, mark))   # a white stone with the dark marker
    assert rd.read(f) == truth(stones)


def test_subtitle_text_over_the_bottom_line_is_not_read_as_stones(monkeypatch):
    top_only = {k: v for k, v in STONES.items() if k < 324}
    f = lesson('wide', top_only, subtitle=True)
    rd = reader(LAYOUTS['wide'])
    assert rd.visible(f), 'the board is still there under a subtitle'
    assert rd.read(f) == truth(top_only)
    # the synthetic text must be nasty enough to fool the ring test alone, otherwise this test proves nothing
    monkeypatch.setattr(layout, 'FILL_MIN', 0.0)
    assert any(ch != '.' for ch in rd.read(f)[324:]), 'the synthetic subtitle no longer fools the ring test'


def test_a_mouse_cursor_on_a_stone_does_not_hide_it():
    # the last move marker in the middle plus a white arrow sized patch on the edge of the stone: still a stone
    g = LAYOUTS['wide']
    f = lesson('wide', STONES, marker=(69, 'dot'))
    cx, cy = int(round(g['x0'] + g['dx'] * (69 % 18))), int(round(g['y0'] + g['dy'] * (69 // 18)))
    f[cy - 14:cy + 2, cx - 12:cx + 1] = (255, 255, 255)
    assert reader(g).read(f) == truth(STONES)


def test_a_dialog_window_over_the_board_is_not_a_board_frame():
    # a white window covers 16 cells: its inside would be read as rows of white stones, so the frame must count as no board
    g = LAYOUTS['wide']
    f = lesson('wide', STONES)
    f[int(g['y0'] + 6.1 * g['dy']):int(g['y0'] + 10.2 * g['dy']), int(g['x0'] + 4.1 * g['dx']):int(g['x0'] + 8.2 * g['dx'])] = (245, 245, 245)
    rd = reader(g)
    assert not rd.visible(f) and rd.wood_share(f) < layout.WOOD_MIN_CELLS
    assert rd.visible(lesson('wide', STONES))


def test_a_screen_recording_is_not_a_board_frame():
    rd = reader(LAYOUTS['wide'])
    other = np.random.RandomState(5).randint(0, 256, (720, 1154, 3)).astype(np.uint8)
    assert not rd.visible(other)
    assert not rd.visible(np.full((720, 1154, 3), (232, 195, 138), np.uint8)), 'the wallpaper is not the board'
