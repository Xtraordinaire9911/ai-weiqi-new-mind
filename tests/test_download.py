"""Download retry, the failure manifest and the pool: a failing video must not block anyone (incident 6)."""
import json
import os
import subprocess
import threading

import pytest

import wqutil
from wqutil import read_json


# ------------------------------------------------------------------ retry_with_backoff

def test_retry_waits_longer_each_time_and_stops_at_the_limit():
    waits, calls = [], []

    def attempt():
        calls.append(1)
        return False, "HTTP 567"

    ok, info = wqutil.retry_with_backoff(attempt, tries=4, base=60, factor=3, jitter=0, sleep=waits.append)
    assert (ok, info) == (False, "HTTP 567")
    assert len(calls) == 4 and waits == [60, 180, 540], "no wait after the last try"


def test_retry_stops_at_first_success_and_caps_the_wait():
    n = []

    def attempt():
        n.append(1)
        return len(n) == 3, "x"

    waits = []
    assert wqutil.retry_with_backoff(attempt, tries=10, base=100, factor=10, cap=250, jitter=0, sleep=waits.append)[0] is True
    assert waits == [100, 250]


# ------------------------------------------------------------------ manifest

def test_manifest_records_clears_and_survives_threads(tmp_path):
    m = wqutil.Manifest(lambda: str(tmp_path / "sub" / "failed.json"))
    m.record(3, reason="HTTP 567", stage="download")
    m.record(3, reason="HTTP 567 again", stage="download")
    assert m.all()["3"]["attempts"] == 2 and m.all()["3"]["reason"] == "HTTP 567 again"
    ts = [threading.Thread(target=m.record, args=(100 + i,), kwargs={"reason": "r"}) for i in range(10)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(m.all()) == 11
    m.clear(3)
    assert "3" not in m.all()
    json.loads((tmp_path / "sub" / "failed.json").read_text(encoding="utf-8"))  # always a complete file


# ------------------------------------------------------------------ download() inside orch2

def fake_ytdlp(toy, outcomes, record=None):
    """subprocess.run replacement: yt-dlp calls pop an outcome ('567' fails, 'ok' writes a file); other commands succeed."""
    def run(cmd, **kw):
        if "yt_dlp" in cmd:
            bvid = cmd[-1].rsplit("/", 1)[-1]
            if record is not None:
                record.append(bvid)
            out = outcomes[bvid].pop(0) if outcomes[bvid] else "567"
            if out == "ok":
                with open(cmd[cmd.index("-o") + 1], "wb") as f:
                    f.write(b"\0" * 1_100_000)
                return subprocess.CompletedProcess(cmd, 0, b"", b"")
            return subprocess.CompletedProcess(cmd, 1, b"", b"ERROR: unable to download: HTTP Error 567: \n")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")
    return run


@pytest.fixture
def dl(toy, monkeypatch):
    o = toy.o
    monkeypatch.setattr(o, "FF", "/usr/bin/ffmpeg")
    monkeypatch.setattr(o, "SLEEP", lambda s: None)
    monkeypatch.setattr(o, "probe_duration", lambda p: 20.0)
    for i in (1, 2):
        os.makedirs(o.D(i), exist_ok=True)
    for f in ("b.json", "t.json"):   # these exist for video 1 in the fixture; this test wants a real download
        p = os.path.join(o.D(1), f)
        if os.path.exists(p):
            os.rename(p, p + ".keep")
    return toy


def test_throttled_video_succeeds_on_a_later_try(dl, monkeypatch):
    o = dl.o
    seen = []
    monkeypatch.setattr(o.subprocess, "run", fake_ytdlp(dl, {"BV1toy": ["567", "567", "ok"]}, seen))
    o.download(1)
    assert seen == ["BV1toy"] * 3 and os.path.getsize(os.path.join(o.D(1), "v.mp4")) > 1e6


def test_a_video_that_never_downloads_gives_up_with_the_reason(dl, monkeypatch):
    o = dl.o
    monkeypatch.setattr(o.subprocess, "run", fake_ytdlp(dl, {"BV1toy": []}))
    with pytest.raises(o.StageError, match="HTTP 567 .throttled.") as e:
        o.download(1)
    assert e.value.stage == "download"


def test_waiting_between_tries_does_not_hold_the_download_slot(dl, monkeypatch):
    """Video 1 is throttled and sleeps between tries; video 2 must be able to download meanwhile."""
    o = dl.o
    slot_free_while_sleeping = []
    v2_done = threading.Event()

    def sleep(s):
        got = o.DL.acquire(timeout=2)   # free during the wait (video 2 may use it for a moment, the sleeper does not)
        slot_free_while_sleeping.append(got)
        if got:
            o.DL.release()
        v2_done.wait(5)

    monkeypatch.setattr(o, "SLEEP", sleep)
    monkeypatch.setattr(o.subprocess, "run", fake_ytdlp(dl, {"BV1toy": [], "BV2toy": ["ok"]}))
    t1 = threading.Thread(target=lambda: pytest.raises(o.StageError, o.download, 1))
    t1.start()
    o.download(2)
    v2_done.set()
    t1.join(10)
    assert not t1.is_alive()
    assert slot_free_while_sleeping and all(slot_free_while_sleeping)
    assert os.path.exists(os.path.join(o.D(2), "v.mp4"))


def test_truncated_download_is_quarantined_and_retried(dl, monkeypatch):
    o = dl.o
    lengths = iter([5.0, 20.0])
    monkeypatch.setattr(o, "probe_duration", lambda p: next(lengths))
    monkeypatch.setattr(o.subprocess, "run", fake_ytdlp(dl, {"BV1toy": ["ok", "ok"]}))
    o.download(1)
    assert os.path.exists(os.path.join(o.D(1), "v.mp4.short")), "the short file was moved aside, not kept as the video"
    assert os.path.exists(os.path.join(o.D(1), "v.mp4"))


# ------------------------------------------------------------------ process_video and the manifest

def test_process_video_records_the_failure_and_never_raises(dl, monkeypatch):
    o = dl.o
    monkeypatch.setattr(o.subprocess, "run", fake_ytdlp(dl, {"BV1toy": []}))
    assert o.process_video(1) is False
    rec = read_json(os.path.join(dl.W, "failed_videos.json"))["1"]
    assert rec["stage"] == "download" and "567" in rec["reason"] and rec["bvid"] == "BV1toy"
    monkeypatch.setattr(o, "stageA", lambda i: (_ for _ in ()).throw(KeyError("surprise")))
    assert o.process_video(2) is False, "unexpected errors are handled the same way"
    assert read_json(os.path.join(dl.W, "failed_videos.json"))["2"]["stage"] == "error"


def test_success_clears_an_old_failure(dl, monkeypatch):
    o = dl.o
    o.FAILED.record(1, reason="old", stage="download")
    monkeypatch.setattr(o, "stageA", lambda i: None)
    assert o.process_video(1) is True
    assert "1" not in o.FAILED.all()


def test_stage_script_failure_and_timeout_are_reported(dl, monkeypatch):
    o = dl.o
    mk = lambda **kw: (lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, b"", b"Traceback: boom"))
    monkeypatch.setattr(o.subprocess, "run", mk())
    with pytest.raises(o.StageError, match="exit code 1: Traceback: boom"):
        o.child("transcribe", ["x"])

    def hang(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)

    monkeypatch.setattr(o.subprocess, "run", hang)
    with pytest.raises(o.StageError, match="timed out"):
        o.child("board", ["x"])


def test_corrupt_json_from_a_killed_run_is_redone(dl, monkeypatch):
    o = dl.o
    os.makedirs(o.D(2), exist_ok=True)
    mp4 = os.path.join(o.D(2), "v.mp4")
    open(mp4, "wb").write(b"\0")
    open(os.path.join(o.D(2), "t.json"), "w").write('[{"s": 0.0, "e"')       # killed mid write
    open(os.path.join(o.D(2), "b.json"), "w").write("[[0.0, ")
    ran = []

    def fake(cmd, **kw):
        ran.append(os.path.basename(cmd[1]))
        with open(cmd[3], "w", encoding="utf-8") as f:
            f.write("[]")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(o.subprocess, "run", fake)
    o.stageA(2)
    assert ran == ["board.py", "tr.py"]
    assert os.path.exists(os.path.join(o.D(2), "t.json.corrupt"))


def test_no_download_when_only_the_video_file_is_gone(dl, monkeypatch):
    o = dl.o
    for f in ("b.json", "t.json"):
        os.rename(os.path.join(o.D(1), f + ".keep"), os.path.join(o.D(1), f))
    monkeypatch.setattr(o.subprocess, "run", lambda *a, **k: pytest.fail("nothing should run"))
    o.stageA(1)


# ------------------------------------------------------------------ the whole pool

def test_pipeline_builds_partial_group_then_rebuilds_after_the_retry(toy, monkeypatch):
    """Video 2 fails the first time (throttled). Its group is built from video 1, then rebuilt once video 2 works."""
    o = toy.o
    monkeypatch.setattr(o, "SLEEP", lambda s: None)
    tries = {1: [True], 2: [False, True]}
    monkeypatch.setattr(o, "process_video", lambda i: tries[i].pop(0) if tries[i] else True)
    built = []
    monkeypatch.setattr(o, "stageB", lambda name, idxs, visits=150, force=False, planned=None: built.append((name, tuple(idxs), tuple(planned or ()))))
    o.run_pipeline(workers=2)
    assert ("toy-pair", (1,), (1, 2)) in built and ("toy-pair", (1, 2), (1, 2)) in built
    assert built.index(("toy-pair", (1,), (1, 2))) < built.index(("toy-pair", (1, 2), (1, 2)))
    assert [b for b in built if b[0] == "toy-group"] == [("toy-group", (1,), (1,))], "an unaffected group is built once"


def test_a_crashing_worker_does_not_hang_the_pipeline(toy, monkeypatch):
    o = toy.o
    monkeypatch.setattr(o, "SLEEP", lambda s: None)
    monkeypatch.setattr(o, "RETRY_ROUNDS", 0)

    def boom(i):
        raise SystemExit(5)   # not an Exception: the old code never set ready[i] and stageB waited for ever

    monkeypatch.setattr(o, "process_video", boom)
    monkeypatch.setattr(o, "stageB", lambda *a, **k: pytest.fail("no group can be built"))
    done = threading.Event()
    threading.Thread(target=lambda: (o.run_pipeline(workers=2), done.set()), daemon=True).start()
    assert done.wait(20), "pipeline hung"
