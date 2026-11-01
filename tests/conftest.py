"""Shared pytest setup. The pipeline scripts are plain modules, so put pipeline/ on sys.path."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE = os.path.join(ROOT, "pipeline")
if PIPELINE not in sys.path:
    sys.path.insert(0, PIPELINE)


import importlib  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture
def toy(tmp_path, monkeypatch):
    """orch2 pointed at a throw-away work/project dir holding one toy video (idx 1) and one group.

    Returns a namespace-like object with .o (the orch2 module), .W, .PROJ, .N (the toy tree).
    """
    import json
    import types

    import toy as toylib

    proj, work = tmp_path / "proj", tmp_path / "work"
    src = proj / "data" / "sources" / "toy"
    src.mkdir(parents=True)
    idx = [{"season": 7, "idx": 1, "bvid": "BV1toy", "title": "toy video", "sec": 20},
           {"season": 7, "idx": 2, "bvid": "BV2toy", "title": "second toy video", "sec": 20}]
    (src / "index.json").write_text(json.dumps(idx), encoding="utf-8")
    plan = {"series": {"7": "定式大全"}, "merge": {"7": [["toy-group", [1]], ["toy-pair", [1, 2]]]}}
    (src / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
    out_dir = proj / "data" / "sgf" / "toy" / "定式大全"
    out_dir.mkdir(parents=True)
    vdir = work / "v" / "1"
    vdir.mkdir(parents=True)
    (vdir / "b.json").write_text(json.dumps(toylib.frames(toylib.toy_sequence())), encoding="utf-8")
    (vdir / "t.json").write_text(json.dumps(toylib.toy_transcript(), ensure_ascii=False), encoding="utf-8")
    for k, v in dict(WEIQI_PROJ=proj, WEIQI_WORK=work, WEIQI_SOURCE="toy", WEIQI_SEASON="7").items():
        monkeypatch.setenv(k, str(v))
    monkeypatch.delenv("NOAN", raising=False)
    monkeypatch.delenv("WEIQI_STRICT", raising=False)
    import orch2
    o = importlib.reload(orch2)
    ns = types.SimpleNamespace(o=o, W=str(work), PROJ=str(proj), tmp=tmp_path, lib=toylib)
    ns.N = o.build_tree([1])
    ns.sgf_file = o.sgf_path("toy-group")
    return ns
