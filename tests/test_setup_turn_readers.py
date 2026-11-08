"""What reads the recorded turn of an analysis: merge writes PL from it, stageB warns about a wrong one, and the control
run is only compared with the main run when both are for the same side (incident 12)."""
import json
import os

import pytest

import sgfcheck
from setup_trees import forget_initial_player, run_analysis
from wqutil import read_json


@pytest.fixture
def setup_group(toy, eng):
    """The toy group, rebuilt so that it starts from a set-up position (one Black stone) and the teacher answers with White."""
    lib = toy.lib
    s0 = {lib.B1: "B"}
    seq = [s0, {**s0, lib.W2: "W"}, s0, {**s0, lib.W3: "W"}]
    with open(os.path.join(toy.W, "v", "1", "b.json"), "w", encoding="utf-8") as f:
        json.dump(lib.frames(seq), f)
    toy.N = toy.o.build_tree([1])
    assert toy.N[1]["setup"] and [toy.N[c]["mv"][1] for c in toy.N[1]["ch"]] == ["W", "W"]
    return toy


def sgf_setup_node(toy):
    text = open(toy.sgf_file, encoding="utf-8").read()
    nodes, problems = sgfcheck.parse(text)
    assert not problems
    return next(n for n in nodes if "AB" in n or "AW" in n)


def test_pl_in_the_sgf_is_the_side_that_was_analysed(setup_group):
    toy = setup_group
    rc, out = run_analysis(toy.tmp, toy.N)
    os.replace(out, os.path.join(toy.W, "g_toy-group.a2.json"))
    toy.o.stageB("toy-group", [1])
    assert sgf_setup_node(toy)["PL"] == ["W"], "White plays next, and the analysis was made for White"


def test_old_analysis_is_flagged_at_merge_time(setup_group, monkeypatch):
    toy = setup_group
    forget_initial_player(monkeypatch)
    rc, out = run_analysis(toy.tmp, toy.N)
    os.replace(out, os.path.join(toy.W, "g_toy-group.a2.json"))
    toy.o.stageB("toy-group", [1])
    assert sgf_setup_node(toy)["PL"] == ["B"], "this is what the wrong analysis would have shown"
    log = open(os.path.join(toy.W, "logs", "orch2.log"), encoding="utf-8").read()
    assert "wrong side to move" in log and "wq.py fix-setup-turns" in log
    assert read_json(os.path.join(toy.W, "status_toy-group.json"))["analysis"]["wrong_turns"] == ["1"]


def test_control_run_for_the_other_side_is_not_compared_with_the_main_run(toy):
    """The control run drops moves outside the region, so it can end up for the other side. Its best move is then no
    evidence about the surrounding stones and must not be turned into a sentence."""
    A = toy.lib.toy_analysis(toy.N)
    A["1_0"] = {"turn": A["1"]["turn"], "score": 1.0, "wr": 0.5, "cand": [dict(A["1"]["cand"][1], v=100)]}
    sgf = toy.o.merge(toy.N, A, [1], "toy-group")
    assert "周边子力影响" in sgf
    A["1_0"]["turn"] = "W" if A["1"]["turn"] == "B" else "B"
    assert "周边子力影响" not in toy.o.merge(toy.N, A, [1], "toy-group")
