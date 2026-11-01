"""Path handling: no hard coded backslash joins, env overrides, importing orch2 never needs the real machine."""
import ast
import glob
import importlib
import json
import os

import pytest

from conftest import PIPELINE


def _write_sources(root, groups):
    d = root / "data" / "sources" / "toy"
    d.mkdir(parents=True)
    idx = [{"season": 7, "idx": i, "bvid": "BV%d" % i, "title": "t%d" % i, "sec": 100} for i in range(1, 6)]
    # PowerShell writes a BOM, the reader has to cope with it
    (d / "index.json").write_bytes(b"\xef\xbb\xbf" + json.dumps(idx).encode("utf-8"))
    plan = {"series": {"7": "定式大全"}, "merge": {"7": groups}}
    (d / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def orch(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    work = tmp_path / "work"
    _write_sources(proj, [["g-one", [1, 2]], ["g-two", [3]], ["g-late", [4, 60]]])
    monkeypatch.setenv("WEIQI_PROJ", str(proj))
    monkeypatch.setenv("WEIQI_WORK", str(work))
    monkeypatch.setenv("WEIQI_SOURCE", "toy")
    monkeypatch.setenv("WEIQI_SEASON", "7")
    import orch2
    return importlib.reload(orch2)


def test_import_without_ffmpeg_or_sources_does_not_crash(tmp_path, monkeypatch):
    # The old module did glob(...)[0] and json.load(...) at import time.
    monkeypatch.setenv("WEIQI_PROJ", str(tmp_path / "nothing"))
    monkeypatch.setenv("FFMPEG", str(tmp_path / "no-ffmpeg"))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    import orch2
    o = importlib.reload(orch2)
    assert o.SRC_ERR
    with pytest.raises(RuntimeError, match="index.json"):
        o.groups()


def test_groups_and_paths_follow_env(orch, tmp_path):
    names = [g[0] for g in orch.groups()]
    assert names == ["g-one", "g-two"], "group with video 60 (> WEIQI_MAX_IDX) must be skipped"
    assert orch.D(3) == os.path.join(str(tmp_path / "work"), "v", "3")
    assert orch.sgf_path("g-one") == os.path.join(str(tmp_path / "proj"), "data", "sgf", "toy", "定式大全", "g-one.sgf")


def test_no_backslash_string_concatenation_in_sources():
    """Incident: a regen path built with backslashes got mangled. Join paths with os.path.join."""
    bad = []
    for f in glob.glob(os.path.join(PIPELINE, "*.py")):
        with open(f, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for n in ast.walk(tree):
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
                for side in (n.left, n.right):
                    if isinstance(side, ast.Constant) and isinstance(side.value, str) and side.value.startswith("\\"):
                        bad.append("%s:%d" % (os.path.basename(f), n.lineno))
    assert not bad, "path built with a '\\...' literal: %s" % bad
