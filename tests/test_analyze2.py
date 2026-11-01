"""analyze2 without KataGo: score perspective, resume after a crash, stalls, progress log.

A fake engine (fake_katago.py) answers the json protocol, so no GPU or model is needed.
"""
import json
import os
import sys

import pytest

import analyze2 as an
import treesync as ts
from wqutil import atomic_write_json, read_json

FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fake_katago.py")


def moveinfo(move, black_lead, order, wr=0.5):
    return {"move": move, "visits": 100, "scoreLead": black_lead, "winrate": wr, "prior": 0.1, "order": order, "pv": [move]}


# ------------------------------------------------------------------ perspective (incident 1)

def test_white_to_move_with_black_perspective_scores_is_flipped():
    """White is to move, KataGo reports from Black's side. The best move for White has the most negative Black lead."""
    d = {"rootInfo": {"currentPlayer": "W", "scoreLead": -5.0, "winrate": 0.2},
         "moveInfos": [moveinfo("D4", -5.0, 0, 0.2), moveinfo("Q16", -1.0, 1, 0.45)]}
    r = an.convert(d, "BLACK")
    assert r["turn"] == "W" and r["score"] == 5.0 and r["wr"] == 0.8
    best = max(r["cand"], key=lambda m: m["s"])
    assert best["m"] == "D4", "the old code compared Black scores as if they were side to move and picked Q16"
    assert [m["s"] for m in r["cand"]] == [5.0, 1.0]


def test_black_to_move_and_other_report_modes():
    d = {"rootInfo": {"currentPlayer": "B", "scoreLead": 2.0, "winrate": 0.6}, "moveInfos": [moveinfo("D4", 2.0, 0, 0.6)]}
    assert an.convert(d, "BLACK")["score"] == 2.0
    d["rootInfo"]["currentPlayer"] = "W"
    assert an.convert(d, "SIDETOMOVE")["score"] == 2.0, "already side to move: never flipped twice"
    assert an.convert(d, "WHITE")["score"] == 2.0
    d["rootInfo"]["currentPlayer"] = "B"
    assert an.convert(d, "WHITE")["score"] == -2.0
    with pytest.raises(ValueError):
        an.convert(d, "SOMETHING")


def test_cfg_file_is_parsed(tmp_path):
    p = tmp_path / "analysis.cfg"
    p.write_text("# comment\nreportAnalysisWinratesAs = BLACK\nnumSearchThreads=16\n", encoding="utf-8")
    assert an.cfg_report_as(str(p)) == "BLACK"
    assert an.cfg_report_as(str(tmp_path / "missing.cfg")) is None


# ------------------------------------------------------------------ whole runs against the fake engine

@pytest.fixture
def env(toy, tmp_path, monkeypatch):
    monkeypatch.setenv("WEIQI_KATAGO_CMD", json.dumps([sys.executable, FAKE]))
    monkeypatch.setenv("WEIQI_KATAGO_DIR", str(tmp_path / "no-engine-dir"))
    monkeypatch.setenv("WEIQI_WINDOW", "2")
    for k in ("FAKE_REPORT_AS", "FAKE_CRASH_AFTER", "FAKE_STALL_AFTER", "FAKE_QUERY_LOG", "WEIQI_REPORT_AS", "LIMIT"):
        monkeypatch.delenv(k, raising=False)
    nj = str(tmp_path / "g.n.json")
    atomic_write_json(nj, toy.N)

    def run(out=None, **extra):
        for k, v in extra.items():
            monkeypatch.setenv(k, str(v))
        out = out or str(tmp_path / "g.a2.json")
        return an.main(["analyze2.py", nj, out, "220", "100"]), out

    return type("E", (), {"run": staticmethod(run), "toy": toy, "tmp": tmp_path, "nj": nj})


def test_run_writes_side_to_move_analysis_with_meta(env):
    rc, out = env.run()
    assert rc == 0
    A = read_json(out)
    meta = A["_meta"]
    assert meta["persp"] == "stm" and meta["report_as"] == "BLACK" and meta["report_as_source"] == "selftest"
    assert meta["tree_fp"] == ts.tree_fingerprint(env.toy.N) and meta["complete"] is True
    for k in ("1", "2"):
        assert A[k]["turn"] in "BW"
        scores = [m["s"] for m in A[k]["cand"] if not m.get("f")]
        assert scores == sorted(scores, reverse=True), "first candidate is the best for the side to move"
    assert any(m.get("f") for m in A["1"]["cand"]), "the teacher's moves were evaluated separately"
    assert ts.check_analysis(env.toy.N, A) == ("ok", "")
    assert not os.path.exists(out + ".part"), "checkpoint is removed after success"


def test_engine_that_reports_side_to_move_gives_the_same_result(env):
    rc1, out1 = env.run()
    rc2, out2 = env.run(out=str(env.tmp / "g2.a2.json"), FAKE_REPORT_AS="SIDETOMOVE")
    assert rc1 == rc2 == 0
    A1, A2 = read_json(out1), read_json(out2)
    assert A2["_meta"]["report_as"] == "SIDETOMOVE"
    for k in ("1", "2"):
        assert A1[k] == A2[k], "the live check sees through a changed engine config, no double flipping"


def test_crash_then_resume_asks_only_for_what_is_missing(env):
    log = str(env.tmp / "q.log")
    out = str(env.tmp / "g.a2.json")
    rc, _ = env.run(out=out, FAKE_CRASH_AFTER=3, FAKE_QUERY_LOG=log)
    assert rc == 4 and not os.path.exists(out), "no final file after a crash"
    part = read_json(out + ".part")
    saved = set(part["done"])
    assert saved, "answers received before the crash are kept"
    os.remove(log)
    rc, _ = env.run(out=out, FAKE_CRASH_AFTER=0, FAKE_QUERY_LOG=log)
    assert rc == 0
    asked = open(log, encoding="utf-8").read().split()
    assert not (saved & set(asked)), "nothing that was already answered is asked again"
    ref_rc, ref = env.run(out=str(env.tmp / "ref.a2.json"))
    A, B = read_json(out), read_json(ref)
    A.pop("_meta"), B.pop("_meta")
    assert A == B, "resumed run equals an uninterrupted run"


def test_checkpoint_of_another_tree_is_ignored(env):
    out = str(env.tmp / "g.a2.json")
    atomic_write_json(out + ".part", {"tree_fp": "other", "visits": [220, 100], "report_as": "BLACK", "done": {"1": {"turn": "B", "cand": []}}})
    rc, _ = env.run(out=out)
    assert rc == 0
    assert read_json(out)["1"]["cand"], "the bogus entry did not leak in"


def test_stalled_engine_ends_with_a_message_instead_of_hanging(env, capsys):
    rc, out = env.run(FAKE_STALL_AFTER=1, WEIQI_STALL_S=1)
    assert rc == 4 and not os.path.exists(out)
    assert "no answer from KataGo" in capsys.readouterr().err


def test_missing_engine_and_empty_tree(env, monkeypatch, capsys):
    monkeypatch.setenv("WEIQI_KATAGO_CMD", json.dumps([str(env.tmp / "does-not-exist")]))
    rc, _ = env.run()
    assert rc == 5 and "cannot start KataGo" in capsys.readouterr().err
    empty = str(env.tmp / "empty.n.json")
    atomic_write_json(empty, env.toy.o.build_tree([]))
    assert an.main(["analyze2.py", empty, str(env.tmp / "e.a2.json")]) == 2
    assert "no moves" in capsys.readouterr().err


def test_progress_log_has_counts_and_eta(env):
    rc, out = env.run()
    text = open(out + ".progress.log", encoding="utf-8").read()
    assert "phase 1/2" in text and "phase 2/2" in text and "eta" in text and "queries" in text and "nodes" in text
    prog = read_json(out + ".progress.json")
    assert prog["done"] == prog["total"] and prog["nodes_total"] >= 1


def test_limit_marks_the_result_incomplete(env):
    rc, out = env.run(LIMIT=1)
    assert rc == 0
    A = read_json(out)
    assert A["_meta"]["complete"] is False
    assert ts.check_analysis(env.toy.N, A)[0] == "incomplete"


def test_black_perspective_numbers_from_a_misreporting_engine_are_caught(env):
    """Told the engine reports side to move while it really reports Black: White nodes come out upside down."""
    rc, out = env.run(WEIQI_REPORT_AS="SIDETOMOVE")  # wrong on purpose, the fake engine reports BLACK
    w = read_json(out)["1"]  # node 1 follows a Black move, White to move
    assert w["turn"] == "W" and w["cand"][0]["s"] < w["cand"][1]["s"], "symptom: the first candidate is not the best"
    many = {str(100 + i): w for i in range(8)}  # a real group has dozens of such nodes
    assert ts.perspective_suspect(many)[0] is True


def test_orch2_keeps_the_analysis_output_and_survives_a_failed_run(toy, monkeypatch):
    """Incident: analysis stderr was captured to nowhere and the exit code was never looked at."""
    import subprocess

    def failing(cmd, **kw):
        kw["stdout"].write("KataGo exploded\n".encode("utf-8"))
        return subprocess.CompletedProcess(cmd, 3)

    monkeypatch.setattr(toy.o.subprocess, "run", failing)
    toy.o.stageB("toy-group", [1])
    log = open(os.path.join(toy.W, "logs", "analyze_toy-group.log"), encoding="utf-8").read()
    assert "KataGo exploded" in log
    assert "exit code 3" in open(os.path.join(toy.W, "logs", "orch2.log"), encoding="utf-8").read()
    assert os.path.exists(toy.sgf_file), "the SGF is still produced, without AI data"
