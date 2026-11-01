"""Board recognition self check (incident 11: a video with another layout silently produced garbage).

Frames are synthetic: wood, grid lines and round stones drawn with numpy, so no video and no ffmpeg are needed.
The thresholds were calibrated on the real lesson videos (grid score 39..65, board visible in 99.6..100% of frames).
"""
import json
import os

import numpy as np
import pytest

import board
from synth import make_frame

STONES = {69: "B", 106: "W", 52: "B", 87: "W"}


def good_frames(n=100, stones=STONES):
    f = make_frame(stones)
    return [f] * n


def test_read_board_returns_the_stones_where_they_are():
    s = board.read_board(make_frame(STONES))
    assert len(s) == 342
    assert s[69] == "B" and s[106] == "W" and s[52] == "B" and s[87] == "W"
    assert s.count(".") == 342 - 4


def test_board_visible_needs_the_wood_colour():
    assert board.board_visible(make_frame())
    assert not board.board_visible(make_frame(wood=(30, 120, 40)))   # a green title card


def test_grid_score_tells_the_right_layout_from_a_different_one():
    right, off = board.grid_score(make_frame(STONES))
    assert right >= board.MIN_GRID_SCORE
    for geo in (dict(X0=260.0), dict(Y0=52.0), dict(D=33.0), dict(D=34.4), dict(X0=200.0, Y0=20.0, D=40.0)):
        assert board.grid_score(make_frame(STONES, **geo))[0] < board.MIN_GRID_SCORE, geo
    assert board.grid_score(make_frame(grid=False))[0] < 5


def test_grid_check_tolerates_the_small_offsets_real_videos_have():
    # video 46 sits 1..3 px off the nominal position and its stones are read fine, so it must not be rejected
    score, off = board.grid_score(make_frame(STONES, X0=250.0, Y0=43.0))
    assert score >= board.MIN_GRID_SCORE


def run(tmp_path, frames, **kw):
    out = str(tmp_path / "b.json")
    kw.setdefault("size", (1134, 720))
    rc = board.run("video.mp4", out, "ffmpeg", frames=frames, **kw)
    return rc, out


def test_a_good_video_is_accepted(tmp_path):
    rc, out = run(tmp_path, good_frames(60))
    assert rc == 0
    data = json.load(open(out))
    assert len(data) == 60 and data[0][0] == 0 and data[1][0] == pytest.approx(1 / 6)
    assert data[0][1][69] == "B"
    meta = json.load(open(str(tmp_path / "b.meta.json")))
    assert meta["board_frames"] == 60 and meta["stones_max"] == 4 and meta["grid_scores"]


def test_frames_without_the_board_pass_through_as_null(tmp_path):
    frames = good_frames(60) + [make_frame(wood=(30, 120, 40))] * 30   # intro/outro card: 1/3 of the video
    rc, out = run(tmp_path, frames)
    assert rc == 0
    data = json.load(open(out))
    assert sum(1 for _, s in data if s is None) == 30


def reasons(tmp_path):
    return json.load(open(str(tmp_path / "b.rej.json"), encoding="utf-8"))["reasons"]


def test_another_layout_is_rejected_with_a_reason(tmp_path, capsys):
    rc, out = run(tmp_path, [make_frame(STONES, X0=260.0)] * 60)
    assert rc == 3 and not os.path.exists(out), "no b.json, so no tree is built from garbage"
    assert any("grid lines do not line up" in r for r in reasons(tmp_path))
    assert "REJECTED" in capsys.readouterr().err


def test_wrong_video_size_is_rejected(tmp_path):
    rc, _ = run(tmp_path, good_frames(30), size=(1280, 720))
    assert rc == 3 and "1280x720" in reasons(tmp_path)[0]


def test_video_without_a_board_is_rejected(tmp_path):
    rc, _ = run(tmp_path, [make_frame(wood=(30, 120, 40))] * 60)
    assert rc == 3 and "only 0% of the frames" in reasons(tmp_path)[0]


def test_mostly_non_board_video_is_rejected_but_half_is_not_enough(tmp_path):
    rc, _ = run(tmp_path, good_frames(20) + [make_frame(wood=(30, 120, 40))] * 80)
    assert rc == 3 and "20%" in reasons(tmp_path)[0]


def test_no_frames_and_ffmpeg_failure_are_rejected(tmp_path):
    rc, _ = run(tmp_path, [])
    assert rc == 3 and any("no frames" in r for r in reasons(tmp_path))

    class Broken(list):
        rc, err = 1, "moov atom not found"

    rc, _ = run(tmp_path, Broken(good_frames(30)))
    assert rc == 3 and any("exited with code 1: moov atom not found" in r for r in reasons(tmp_path))


def test_empty_board_everywhere_is_rejected(tmp_path):
    rc, _ = run(tmp_path, [make_frame()] * 60)
    assert rc == 3 and any("not a single stone" in r for r in reasons(tmp_path))


def test_absurd_number_of_stones_is_rejected(tmp_path):
    rc, _ = run(tmp_path, [make_frame({k: "B" for k in range(342)})] * 30)
    assert rc == 3 and any("stones per frame" in r for r in reasons(tmp_path))


def test_probe_size_reads_the_stream_line(monkeypatch):
    import subprocess
    err = (b"  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709, progressive), "
           b"1134x720 [SAR 2080:2079 DAR 52:33], 146 kb/s, 30 fps\n  Stream #0:1: Audio: aac, 44100 Hz\n")
    monkeypatch.setattr(board.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, b"", err))
    assert board.probe_size("ffmpeg", "x.mp4") == (1134, 720)
    monkeypatch.setattr(board.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1, b"", b"nothing useful"))
    assert board.probe_size("ffmpeg", "x.mp4") is None


def test_stage_a_does_not_repeat_a_rejected_video(toy, monkeypatch):
    o = toy.o
    monkeypatch.setattr(o, "FF", "/usr/bin/ffmpeg")
    os.makedirs(o.D(2), exist_ok=True)
    open(os.path.join(o.D(2), "v.mp4"), "wb").write(b"\0")
    json.dump({"reasons": ["only 0% of the frames show the board background"]}, open(os.path.join(o.D(2), "b.rej.json"), "w"))
    monkeypatch.setattr(o.subprocess, "run", lambda *a, **k: pytest.fail("no heavy work for a video that was rejected"))
    with pytest.raises(o.StageError, match="rejected earlier: only 0%") as e:
        o.stageA(2)
    assert e.value.stage == "board"
    assert o.process_video(2) is False
    assert "rejected earlier" in json.load(open(os.path.join(toy.W, "failed_videos.json"), encoding="utf-8"))["2"]["reason"]


def test_a_rejected_video_is_not_downloaded_again(toy, monkeypatch):
    o = toy.o
    monkeypatch.setattr(o, "FF", "/usr/bin/ffmpeg")
    os.makedirs(o.D(2), exist_ok=True)   # no v.mp4 here, only the verdict of an earlier run
    json.dump({"reasons": ["video is 1920x1080"]}, open(os.path.join(o.D(2), "b.rej.json"), "w"))
    monkeypatch.setattr(o.subprocess, "run", lambda *a, **k: pytest.fail("neither download nor decode again"))
    with pytest.raises(o.StageError, match="1920x1080"):
        o.stageA(2)
