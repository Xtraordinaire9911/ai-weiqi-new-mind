"""Derived files (analysis, key point notes) must be tied to the tree they were made from.

Incident: a2.json and kp_*.json are keyed by node id; when the tree changed (another video
finished downloading) they were silently merged into the wrong nodes.
"""
import copy
import json
import os
import subprocess

import treesync as ts
from wqutil import atomic_write_json, read_json


def other_tree(toy):
    """The toy group after a second video arrived: same first video, extra content in front."""
    N2 = copy.deepcopy(toy.N)
    N2.insert(1, {"id": 1, "par": 0, "mv": [10, "W"], "v": [[0, 1, 0]], "ch": [], "dead": False, "setup": False, "n": 1, "pos": "W10"})
    for i, n in enumerate(N2):
        n["id"] = i
    return N2


# ------------------------------------------------------------------ tree and fingerprint

def test_toy_tree_has_the_expected_branch(toy):
    N = toy.N
    live = [n for n in N if not n["dead"]]
    assert len(live) == 7
    branch = [n for n in live if len([c for c in n["ch"] if not N[c]["dead"]]) == 2]
    assert [n["id"] for n in branch] == [1, 2]


def test_fingerprint_is_stable_and_sees_structure_changes(toy):
    fp = ts.tree_fingerprint(toy.N)
    assert fp == ts.tree_fingerprint(toy.o.build_tree([1])), "same input, same fingerprint"
    N2 = copy.deepcopy(toy.N)
    for n in N2:
        for span in n["v"]:
            span[0] += 0.5  # timing shift only: analysis stays valid, no GPU re-run
    assert ts.tree_fingerprint(N2) == fp
    assert ts.tree_fingerprint(other_tree(toy)) != fp
    N3 = copy.deepcopy(toy.N)
    N3[3]["dead"] = True
    assert ts.tree_fingerprint(N3) != fp


# ------------------------------------------------------------------ analysis

def stamped(toy, **meta):
    A = toy.lib.toy_analysis(toy.N)
    A["_meta"] = ts.make_meta(toy.N, **meta)
    return A


def test_analysis_with_matching_fingerprint_is_ok(toy):
    assert ts.check_analysis(toy.N, stamped(toy)) == ("ok", "")


def test_analysis_for_another_tree_is_stale(toy):
    st, msg = ts.check_analysis(other_tree(toy), stamped(toy))
    assert st == "stale" and "tree changed" in msg


def test_incomplete_and_missing_analysis_are_not_usable(toy):
    assert ts.check_analysis(toy.N, stamped(toy, complete=False))[0] == "incomplete"
    assert ts.check_analysis(toy.N, None)[0] == "missing"
    assert ts.check_analysis(toy.N, {"_meta": ts.make_meta(toy.N)})[0] == "missing"


def test_meta_must_say_side_to_move(toy):
    A = stamped(toy)
    A["_meta"]["persp"] = "black"
    assert ts.check_analysis(toy.N, A)[0] == "bad_persp"


def _many_white_nodes(n=8):
    """n White-to-move nodes whose first candidate is the best (correct) or the worst (Black persp)."""
    def entry(first_is_best):
        sc = [3.0, 1.0, -1.0, -3.0]
        if not first_is_best:
            sc = sc[::-1]
        return {"turn": "W", "cand": [{"m": "D%d" % (i + 4), "v": 50, "s": s, "wr": .5, "p": .1, "pv": ["D4"]} for i, s in enumerate(sc)]}
    return {str(i): entry(True) for i in range(n)}, {str(i): entry(False) for i in range(n)}


def test_perspective_suspect_separates_stm_from_black_perspective():
    good, inverted = _many_white_nodes()
    assert ts.perspective_suspect(good)[0] is False
    assert ts.perspective_suspect(inverted)[0] is True
    assert ts.perspective_suspect({"0": good["0"]})[0] is False, "too few nodes to judge"


def test_black_perspective_scores_are_rejected_even_with_a_fingerprint(toy):
    N = toy.N
    A = toy.lib.toy_analysis(N, persp_ok=False)
    _, bad = _many_white_nodes(6)  # enough White nodes for the detector to judge
    A.update({"%d" % (100 + int(i)): v for i, v in bad.items()})
    A["_meta"] = ts.make_meta(N)
    assert ts.check_analysis(N, A)[0] == "bad_persp"


def test_legacy_analysis_is_accepted_only_if_it_fits_the_tree(toy):
    A = toy.lib.toy_analysis(toy.N)  # no _meta: what a2.json looked like before this change
    assert ts.check_analysis(toy.N, A)[0] == "legacy"
    # the same file against a tree where ids moved: node 1's candidates now sit on stones / wrong side to move
    st, msg = ts.check_analysis(other_tree(toy), A)
    assert st == "stale", msg


def test_candidate_on_a_stone_is_detected(toy):
    A = toy.lib.toy_analysis(toy.N)
    A["1"]["cand"][0]["m"] = toy.lib.gtp(toy.lib.B1)  # B1 is already on the board at node 1
    ok, why = ts.consistent_with_tree(toy.N, A)
    assert not ok and "stone" in why


# ------------------------------------------------------------------ key point notes

def test_kp_ok_remapped_stale_and_legacy(toy):
    N = toy.N
    notes = {"1": "first move", "2": "answer", "5": "branch"}
    kp = dict(notes, _meta=ts.kp_ident(N))
    out, st, msg, stamp = ts.check_kp(N, kp)
    assert (st, out, stamp) == ("ok", notes, None)

    N2 = other_tree(toy)  # ids shifted by one: the old file must not be applied by id
    out, st, msg, _ = ts.check_kp(N2, kp)
    assert st == "remapped"
    assert out == {"2": "first move", "3": "answer", "6": "branch"}, "notes follow their position, not their id"

    unrelated = {"7": "x", "_meta": {"tree_fp": "zzz", "keys": {"7": "nomatch"}}}
    assert ts.check_kp(N, unrelated)[1] == "stale"

    legacy = dict(notes)  # old file, no fingerprint: applied but flagged
    out, st, msg, _ = ts.check_kp(N, legacy)
    assert st == "legacy" and out == notes and "unverified" in msg
    assert ts.check_kp(N, legacy, strict=True)[1] == "stale"
    assert ts.check_kp(N, {"900": "t", "901": "t"})[1] == "stale", "ids that do not exist: not applied"
    assert ts.check_kp(N, {})[1] == "missing"


def test_kp_without_meta_uses_the_identity_of_the_dump_it_was_written_from(toy):
    ident = ts.kp_ident(toy.N)
    out, st, msg, stamp = ts.check_kp(other_tree(toy), {"2": "a note"}, ident=ident)
    assert st == "remapped" and out == {"3": "a note"} and stamp == ident


# ------------------------------------------------------------------ stageB wiring

def write_a2(toy, A):
    atomic_write_json(os.path.join(toy.W, "g_toy-group.a2.json"), A)


def read_status(toy):
    return read_json(os.path.join(toy.W, "status_toy-group.json"))


def test_stage_b_merges_matching_analysis(toy):
    write_a2(toy, stamped(toy))
    toy.o.stageB("toy-group", [1])
    sgf = open(toy.sgf_file, encoding="utf-8").read()
    assert "AN[" in sgf and "PL[W]" in sgf
    assert read_status(toy)["analysis"]["status"] == "ok"


def test_stage_b_never_merges_analysis_of_another_tree(toy, monkeypatch):
    monkeypatch.setenv("NOAN", "1")  # no re-analysis here, only the decision not to merge
    A = stamped(toy)
    A["_meta"]["tree_fp"] = "deadbeefdeadbeef"
    write_a2(toy, A)
    toy.o.stageB("toy-group", [1])
    sgf = open(toy.sgf_file, encoding="utf-8").read()
    assert "AN[" not in sgf and "AI局部评估" not in sgf
    assert read_status(toy)["analysis"]["status"] == "stale"


def test_stage_b_reanalyses_when_the_tree_changed(toy, monkeypatch):
    A = stamped(toy)
    A["_meta"]["tree_fp"] = "deadbeefdeadbeef"
    write_a2(toy, A)
    calls = []

    def fake_analyze(cmd, **kw):
        calls.append(cmd)
        n_json, out = cmd[2], cmd[3]
        N = read_json(n_json)
        fresh = toy.lib.toy_analysis(N)
        fresh["_meta"] = ts.make_meta(N)
        atomic_write_json(out, fresh)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(toy.o.subprocess, "run", fake_analyze)
    toy.o.stageB("toy-group", [1])
    assert len(calls) == 1 and calls[0][1].endswith("analyze2.py")
    assert os.path.exists(os.path.join(toy.W, "g_toy-group.a2.json.stale")), "old file is kept, not merged"
    assert "AN[" in open(toy.sgf_file, encoding="utf-8").read()
    assert read_status(toy)["analysis"]["status"] == "ok"


def test_stage_b_stamps_and_remaps_kp_notes(toy):
    o, W = toy.o, toy.W
    o.stageB("toy-group", [1])  # first run: writes the kpin dump and its sidecar
    kp = os.path.join(W, "kp_toy-group.json")
    with open(kp, "w", encoding="utf-8") as f:  # the helper writes notes for what it saw, without any meta
        json.dump({"2": "白棋压的考量"}, f, ensure_ascii=False)
    o.stageB("toy-group", [1])
    stamped_kp = read_json(kp)
    assert stamped_kp["_meta"]["tree_fp"] == ts.tree_fingerprint(toy.N), "unstamped notes get the identity of the dump"
    assert "白棋压的考量" in open(toy.sgf_file, encoding="utf-8").read()
