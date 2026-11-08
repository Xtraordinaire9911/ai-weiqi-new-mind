"""Incident 12: a position set up from stones was sent to KataGo without `initialPlayer`, so the engine guessed Black
and the node was analysed for the wrong side wherever the teacher continues with White.

Covers side_to_move, the request that query() builds and whole runs against the fake engine, which, like the real one,
answers for Black when it is not told. The fake engine and the toy trees are test fixtures, not real KataGo output.
"""
import json
import os

import analyze2 as an
import treesync as ts
from setup_trees import forget_initial_player, run_analysis, tree
from wqutil import atomic_write_json, read_json


# ------------------------------------------------------------------ side_to_move

def test_side_to_move_follows_the_last_move():
    N = tree()
    assert an.side_to_move(N, 2) == "B", "White just moved, so Black is next"
    assert an.side_to_move(N, 5) == "W", "Black just moved, so White is next"
    N[2]["ch"] = [3]          # even with children of the other colour, the last move decides
    assert an.side_to_move(N, 2) == "B"


def test_side_to_move_of_a_setup_position_is_the_colour_the_teacher_plays():
    N = tree()
    assert an.side_to_move(N, 1) == "W"
    assert an.side_to_move(N, 4) == "B"
    assert an.side_to_move(N, 7) == "W", "a single child is enough"
    assert an.side_to_move(N, 9) == "B", "the majority of the live children wins (2 Black, 1 White)"
    N[9]["ch"] = [10, 12]
    assert an.side_to_move(N, 9) == "B", "a tie goes to Black"
    N[11]["mv"][1] = "W"
    N[9]["ch"] = [10, 11, 12]
    assert an.side_to_move(N, 9) == "W", "1 Black, 2 White"


def test_side_to_move_defaults_to_black_without_a_hint():
    N = tree()
    assert an.side_to_move(N, 0) == "B", "the empty board: its children are setups without a move"
    assert an.side_to_move(N, 13) == "B", "its only child is dead: nothing says otherwise"
    N[17]["mv"][1], N[17]["dead"] = "W", False
    assert an.side_to_move(N, 13) == "W", "the same child alive: now it does"
    N[13]["ch"] = []
    assert an.side_to_move(N, 13) == "B"
    N[1]["ch"] = []
    assert an.side_to_move(N, 1) == "B", "a setup position with no continuation at all"


def test_dead_children_do_not_vote():
    N = tree()
    N[2]["dead"] = N[3]["dead"] = True
    N[1]["ch"] = [2, 3, 5]    # one live Black child among two dead White ones
    N[5]["par"] = 1
    N[5]["dead"] = False
    assert an.side_to_move(N, 1) == "B"


# ------------------------------------------------------------------ the request

def req(N, i, ctx=True):
    R = an.region(N)
    return an.query(N, R, an.allowed(R), i, ctx, str(i), 220)


def test_query_names_the_player_for_a_setup_node():
    N = tree()
    r1, r4 = req(N, 1), req(N, 4)
    assert r1["moves"] == [] and r1["initialPlayer"] == "W", "White children: the engine must not guess Black"
    assert r4["moves"] == [] and r4["initialPlayer"] == "B"
    assert req(N, 9)["initialPlayer"] == "B" and req(N, 7)["initialPlayer"] == "W"


def test_query_of_a_node_with_moves_has_no_initial_player():
    N = tree()
    for i in (2, 3, 5, 8):
        r = req(N, i)
        assert r["moves"] and "initialPlayer" not in r, "the side comes from the moves"
    assert req(N, 2)["moves"] == [["W", an.gtp(106 % an.C, 106 // an.C)]]


def test_control_query_with_all_moves_outside_the_region_still_gets_the_true_side():
    """ctx=False drops the moves outside the region. If none is left the engine would guess again."""
    N = tree()
    R = {"x0": 0, "x1": 5, "y0": 0, "y1": 5}   # the moves of node 2 are at column 16, row 5: outside
    r = an.query(N, R, an.allowed(R), 2, False, "2_0", 100)
    assert r["moves"] == [] and r["initialPlayer"] == "B", "node 2 follows a White move"
    assert "initialPlayer" not in an.query(N, R, an.allowed(R), 2, True, "2", 100), "with its moves the side is known"


def test_selftest_request_is_unchanged():
    r = an.selftest_query()
    assert r["initialPlayer"] == "W" and r["moves"] == [] and r["id"] == "selftest" and len(r["initialStones"]) == 9


# ------------------------------------------------------------------ whole runs against the fake engine


# ------------------------------------------------------------------ whole runs against the fake engine


def test_whole_run_analyses_a_setup_node_for_the_side_the_teacher_plays(eng):
    """Fails on the old code: the fake engine guesses Black for a request without initialPlayer, like KataGo does."""
    N = tree()
    rc, out = run_analysis(eng, N)
    assert rc == 0
    A = read_json(out)
    assert A["1"]["turn"] == "W", "teacher plays White at node 1"
    assert A["4"]["turn"] == "B" and A["7"]["turn"] == "W"
    assert an.wrong_turns(N, A) == []
    assert any(m.get("f") for m in A["1"]["cand"]), "the teacher's White moves were evaluated by force"
    assert ts.check_analysis(N, A) == ("ok", "")


def test_the_old_code_gets_it_wrong(eng, monkeypatch):
    """The same run without the fix: the symptom of the incident, and what wrong_turns reports."""
    forget_initial_player(monkeypatch)
    N = tree()
    rc, out = run_analysis(eng, N)
    A = read_json(out)
    assert rc == 0 and A["1"]["turn"] == "B" and A["7"]["turn"] == "B", "analysed for Black although White plays next"
    assert sorted(an.wrong_turns(N, A), key=lambda k: int(k.split("_")[0])) == ["1", "7"]


def test_only_nodes_without_moves_carry_initial_player_on_the_wire(eng):
    log = str(eng / "requests.log")
    rc, out = run_analysis(eng, tree(), FAKE_REQUEST_LOG=log)
    sent = [json.loads(x) for x in open(log, encoding="utf-8").read().splitlines()]
    assert rc == 0 and sent
    for r in sent:
        if r["id"] == "selftest":
            assert r["initialPlayer"] == "W"
        elif r["moves"]:
            assert "initialPlayer" not in r, r["id"]
        else:
            assert r["initialPlayer"] in ("B", "W"), r["id"]
    assert {r["id"]: r["initialPlayer"] for r in sent if r["id"] in ("1", "4", "7", "9")} == {"1": "W", "4": "B", "7": "W", "9": "B"}


def test_checkpoint_of_the_old_code_is_not_trusted(eng, monkeypatch):
    """A .part written before the fix holds node 1 for Black. The new run drops it and asks again, and keeps the good ones."""
    N = tree()
    rc, out = run_analysis(eng, N)
    good = read_json(out)
    os.remove(out)
    part = {k: v for k, v in good.items() if k in ("4", "9")}
    part["1"] = dict(good["1"], turn="B")
    atomic_write_json(out + ".part", {"tree_fp": ts.tree_fingerprint(N), "visits": [220, 100], "report_as": "BLACK", "done": part})
    log = str(eng / "q.log")
    rc, out = run_analysis(eng, N, FAKE_QUERY_LOG=log)
    asked = open(log, encoding="utf-8").read().split()
    assert rc == 0 and "1" in asked and "4" not in asked, "the bad entry is asked again, the good one is reused"
    assert read_json(out)["1"]["turn"] == "W"


def test_wrong_turns_only_looks_at_set_up_nodes_that_are_alive():
    N = tree()
    A = {"1": {"turn": "B", "cand": []}, "1_0": {"turn": "W", "cand": []}, "4": {"turn": "B", "cand": []},
         "2": {"turn": "W", "cand": []},          # a node with a move: not this class of error
         "17": {"turn": "W", "cand": []},         # dead node
         "9": {"err": "engine said no"}, "_meta": {}, "f2": {"turn": "W"}, "99": {"turn": "B"}}
    assert an.wrong_turns(N, A) == ["1"]
