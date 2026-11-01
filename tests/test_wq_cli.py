"""wq.py helper commands."""
import os

import treesync as ts
import wq
from wqutil import atomic_write_json, read_json


def prepare(toy):
    """A built group with a legacy (unstamped) a2.json and kp file, as the real files looked before this change."""
    o = toy.o
    A = toy.lib.toy_analysis(toy.N)  # no _meta
    atomic_write_json(os.path.join(toy.W, "g_toy-group.a2.json"), A)
    o.stageB("toy-group", [1])
    with open(os.path.join(toy.W, "kp_toy-group.json"), "w", encoding="utf-8") as f:
        f.write('{"2": "白棋压的考量"}')
    os.utime(os.path.join(toy.W, "kp_toy-group.json"), (1, 1))  # older than the kpin dump: stays legacy


def test_status_lists_groups_failures_and_progress(toy, capsys):
    prepare(toy)
    toy.o.FAILED.record(2, bvid="BV2toy", stage="download", reason="HTTP 567 (throttled)")
    atomic_write_json(os.path.join(toy.W, "g_toy-group.a2.json.progress.json"),
                      {"phase": "phase 1/2 main search", "done": 3, "total": 9, "nodes_done": 1, "nodes_total": 2, "eta_s": 40, "updated": "now"})
    assert wq.main(["status", "--work", toy.W]) == 0
    out = capsys.readouterr().out
    assert "toy-group" in out and "analysis legacy" in out and "written" in out
    assert "FAILED video 2 (BV2toy) stage download after 1 tries: HTTP 567 (throttled)" in out
    assert "3/9 queries" in out and "eta 40 s" in out


def test_check_and_stamp_a_legacy_group(toy, capsys):
    prepare(toy)
    assert wq.main(["check", "toy-group", "--work", toy.W]) == 0
    out = capsys.readouterr().out
    assert "analysis: legacy" in out and "key points: legacy" in out
    assert wq.main(["stamp", "toy-group", "--work", toy.W]) == 0
    assert read_json(os.path.join(toy.W, "g_toy-group.a2.json"))["_meta"]["tree_fp"] == ts.tree_fingerprint(toy.N)
    assert read_json(os.path.join(toy.W, "kp_toy-group.json"))["_meta"]["tree_fp"] == ts.tree_fingerprint(toy.N)
    capsys.readouterr()
    assert wq.main(["check", "toy-group", "--work", toy.W]) == 0
    assert "analysis: ok" in capsys.readouterr().out


def test_stamp_refuses_a_file_that_does_not_fit(toy, capsys):
    prepare(toy)
    p = os.path.join(toy.W, "g_toy-group.a2.json")
    A = read_json(p)
    A["1"]["cand"][0]["m"] = toy.lib.gtp(toy.lib.B1)  # candidate on a stone
    atomic_write_json(p, A)
    wq.main(["stamp", "toy-group", "--work", toy.W])
    assert "a2.json not stamped" in capsys.readouterr().out
    assert "_meta" not in read_json(p)


def test_validate_command(tmp_path, capsys):
    good, bad = tmp_path / "g.sgf", tmp_path / "b.sgf"
    good.write_text("(;GM[1]SZ[19];B[pd];W[dp]PL[B])", encoding="utf-8")
    bad.write_text("(;GM[1]SZ[19];B[zz]", encoding="utf-8")
    assert wq.main(["validate", str(good)]) == 0
    assert wq.main(["validate", str(tmp_path / "*.sgf")]) == 1
    out = capsys.readouterr().out
    assert "g.sgf: OK" in out and "b.sgf: INVALID" in out
    assert wq.main(["validate", str(tmp_path / "missing.sgf")]) == 1


def test_fix_check_command():
    assert wq.main(["fix-check"]) == 0
