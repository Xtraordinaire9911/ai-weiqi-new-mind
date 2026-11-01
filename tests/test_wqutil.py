"""Atomic writes and tolerant json reads (incident: a kill during a write left partial json)."""
import json
import os
import threading

import pytest

import wqutil


def test_atomic_write_creates_and_replaces(tmp_path):
    p = tmp_path / "a.json"
    wqutil.atomic_write_json(p, {"x": 1})
    wqutil.atomic_write_json(p, {"x": 2, "t": "中文"}, ensure_ascii=False)
    assert json.loads(p.read_text(encoding="utf-8")) == {"x": 2, "t": "中文"}
    assert os.listdir(tmp_path) == ["a.json"], "no temp file may stay behind"


def test_text_write_keeps_lf_and_utf8(tmp_path):
    p = tmp_path / "a.sgf"
    wqutil.atomic_write_text(p, "(;C[黑\n白])")
    assert p.read_bytes() == "(;C[黑\n白])".encode("utf-8")  # no CRLF translation


def test_failed_replace_keeps_old_file(tmp_path, monkeypatch):
    p = tmp_path / "a.json"
    wqutil.atomic_write_json(p, {"v": "old"})

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        wqutil.atomic_write_json(p, {"v": "new"})
    monkeypatch.undo()
    assert json.loads(p.read_text()) == {"v": "old"}
    assert os.listdir(tmp_path) == ["a.json"]


def test_unserialisable_object_does_not_touch_old_file(tmp_path):
    p = tmp_path / "a.json"
    wqutil.atomic_write_json(p, {"v": "old"})
    with pytest.raises(TypeError):
        wqutil.atomic_write_json(p, {"v": {1, 2}})
    assert json.loads(p.read_text()) == {"v": "old"}
    assert os.listdir(tmp_path) == ["a.json"]


def test_permission_error_is_retried(tmp_path, monkeypatch):
    p = tmp_path / "a.json"
    real = os.replace
    calls = []

    def flaky(src, dst):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("file in use")  # what Windows does while build.ps1 reads the file
        return real(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    monkeypatch.setattr(wqutil.time, "sleep", lambda s: None)
    wqutil.atomic_write_json(p, [1, 2, 3])
    assert len(calls) == 3
    assert json.loads(p.read_text()) == [1, 2, 3]


def test_concurrent_writers_never_leave_a_partial_file(tmp_path):
    p = tmp_path / "a.json"

    def work(i):
        for _ in range(20):
            wqutil.atomic_write_json(p, {"writer": i, "pad": "x" * 5000})

    ts = [threading.Thread(target=work, args=(i,)) for i in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert json.loads(p.read_text())["pad"] == "x" * 5000
    assert os.listdir(tmp_path) == ["a.json"]


def test_read_json_accepts_bom(tmp_path):
    p = tmp_path / "idx.json"
    p.write_bytes(b"\xef\xbb\xbf" + json.dumps({"名": 1}, ensure_ascii=False).encode("utf-8"))
    assert wqutil.read_json(p) == {"名": 1}


def test_read_json_corrupt_gives_named_error_or_default(tmp_path):
    p = tmp_path / "b.json"
    p.write_text('[["0", "....', encoding="utf-8")  # looks like a write that was killed half way
    with pytest.raises(ValueError, match="b.json"):
        wqutil.read_json(p)
    assert wqutil.read_json(p, default=None) is None
    assert p.exists(), "plain read must not move the file"


def test_read_json_quarantine_moves_corrupt_file(tmp_path):
    p = tmp_path / "t.json"
    p.write_text("[{", encoding="utf-8")
    assert wqutil.read_json(p, default=None, quarantine=True) is None
    assert not p.exists() and (tmp_path / "t.json.corrupt").exists()


def test_read_json_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        wqutil.read_json(tmp_path / "nope.json")
    assert wqutil.read_json(tmp_path / "nope.json", default=[]) == []
