"""SGF validation, the "never write a poorer file" rule, and what merge() produces."""
import glob
import os

import pytest

import sgfcheck as sc
from conftest import ROOT

GOOD = "(;GM[1]FF[4]CA[UTF-8]SZ[19]GN[t];B[pd];W[dp]PL[B]C[note (with) parens and \\] bracket]AN[dp:0.0:0.30:55:120:D4 Q16 D16])"


def test_valid_sgf_passes_and_escapes_are_respected():
    assert sc.validate(GOOD) == []
    nodes, _ = sc.parse(GOOD)
    assert nodes[2]["C"] == ["note (with) parens and ] bracket"], "escaped ] stays inside the value"


@pytest.mark.parametrize("bad,needle", [
    ("(;GM[1]SZ[19];B[pd]", "unbalanced"),
    ("(;GM[1]SZ[19];B[pd]))", "without a matching"),
    ("(;GM[1]SZ[19];C[never closed)", "unterminated"),
    ("(;GM[1]SZ[19];B[zz])", "not a point on the board"),
    ("(;GM[1]SZ[19];B[pd]B[dd])", "twice"),
    ("(;GM[1]SZ[19];W[dp]PL[X])", "PL[X]"),
    ("(;GM[1]SZ[13])", "SZ[13]"),
    ("(;AB[aa][tt])", "not a point on the board"),
    ("GM[1];B[pd]", "does not start"),
    ("", "no nodes"),
])
def test_broken_sgf_is_reported(bad, needle):
    problems = sc.validate(bad)
    assert any(needle in p for p in problems), problems


@pytest.mark.parametrize("an", [
    "dp:0.0:0.30:55:120",                    # variation missing
    "zz:0.0:0.30:55:120:D4",                 # point off the board
    "dp:0.0:0.30:155:120:D4",                # winrate above 100
    "dp:2.5:0.30:55:120:D4",                 # loss must be <= 0
    "dp:0.0:3.00:55:120:D4",                 # prior out of range
    "dp:0.0:0.30:55:120:D4 I5",              # no I column in GTP
    "dp:0.0:0.30:55:120:D4 pass",            # pass is not a board coordinate
    "dp:0.0:0.30:55:abc:D4",
])
def test_malformed_an_values_are_reported(an):
    assert sc.validate("(;GM[1]SZ[19];W[dp]AN[%s])" % an), an


def test_an_with_forced_candidate_prior_is_fine():
    assert sc.validate("(;GM[1]SZ[19];W[dp]AN[dp:-0.0:0.30:55:120:D4;pd:-1.5:-1.00:48:100:Q16 D16])") == []


def test_metrics_and_worse():
    m = sc.metrics(GOOD)
    assert m == {"nodes": 3, "an": 1, "kp": 0, "teach": 0}
    old = {"nodes": 100, "an": 10, "kp": 5, "teach": 50}
    assert sc.worse(dict(old), old) == []
    assert sc.worse({**old, "nodes": 1}, old) == ["nodes 100 -> 1"]
    assert "nodes with AI evaluation 10 -> 0" in sc.worse({**old, "an": 0}, old)[0]
    assert "key point notes" in sc.worse({**old, "kp": 4}, old)[0]
    assert sc.worse({**old, "teach": 45}, old) == [], "small fluctuation of teacher text is tolerated"
    assert "teacher text" in sc.worse({**old, "teach": 20}, old)[0]
    assert sc.worse({**old, "nodes": 500, "an": 99}, old) == [], "richer is fine"


def test_repo_sgfs_with_content_are_valid():
    """All real SGFs in the repo. Skeletons made by build.ps1 are skipped, see below."""
    files = glob.glob(os.path.join(ROOT, "data", "sgf", "**", "*.sgf"), recursive=True)
    assert files
    checked = 0
    for f in files:
        text = open(f, encoding="utf-8-sig").read()
        if "待填充" in text:
            # build.ps1 skeleton: its placeholder text contains an unescaped "C[]" inside C[...], so the
            # file is malformed SGF. tools/ is out of scope for this branch, noted in docs/PREMORTEM.md.
            continue
        assert sc.validate(text) == [], os.path.basename(f)
        checked += 1
    assert checked >= 1


# ------------------------------------------------------------------ merge output and write_sgf

def test_merge_output_is_valid_and_escapes_names(toy):
    o = toy.o
    A = toy.lib.toy_analysis(toy.N)
    sgf = o.merge(toy.N, A, [1], "name ] with \\ bracket", "", {})
    assert sc.validate(sgf) == []
    assert "GN[name \\] with \\\\ bracket]" in sgf


def test_merge_drops_candidates_that_are_not_board_coordinates(toy):
    A = toy.lib.toy_analysis(toy.N)
    A["1"]["cand"].insert(0, {"m": "pass", "v": 500, "s": 9.0, "wr": .5, "p": .1, "pv": ["pass"]})
    sgf = toy.o.merge(toy.N, A, [1], "g", "", {})
    assert sc.validate(sgf) == []
    assert "pass" not in sgf


def test_failed_merge_does_not_leak_into_next_kpin_dump(toy):
    o = toy.o
    o.DUMP.append({"id": 999, "path": "stale", "text": "from an earlier group", "nch": 0})
    o.merge(toy.N, {}, [1], "g", "", {})
    assert all(d["id"] != 999 for d in o.DUMP)


def rich_sgf(toy, with_ai=True):
    A = toy.lib.toy_analysis(toy.N) if with_ai else {}
    return toy.o.merge(toy.N, A, [1], "toy-group", "", {})


def test_write_sgf_refuses_to_lose_ai_data(toy):
    o = toy.o
    good, poor = rich_sgf(toy), rich_sgf(toy, with_ai=False)
    assert o.write_sgf(toy.sgf_file, good) == (True, [])
    written, why = o.write_sgf(toy.sgf_file, poor)
    assert not written and "nodes with AI evaluation" in why[0]
    assert open(toy.sgf_file, encoding="utf-8").read() == good, "old file untouched"
    assert o.write_sgf(toy.sgf_file, poor, force=True) == (True, [])
    assert open(toy.sgf_file, encoding="utf-8").read() == poor


def test_write_sgf_refuses_an_empty_shell(toy):
    o = toy.o
    good = rich_sgf(toy)
    o.write_sgf(toy.sgf_file, good)
    shell = o.merge(o.build_tree([]), {}, [], "toy-group", "", {})  # what a regen with no inputs produced: root node only
    written, why = o.write_sgf(toy.sgf_file, shell)
    assert not written and "nodes" in why[0]
    assert open(toy.sgf_file, encoding="utf-8").read() == good


def test_write_sgf_refuses_invalid_text_and_missing_folder(toy, tmp_path):
    o = toy.o
    assert o.write_sgf(toy.sgf_file, "(;GM[1]SZ[19];B[pd]")[0] is False
    assert not os.path.exists(toy.sgf_file)
    nowhere = str(tmp_path / "nope" / "x.sgf")
    written, why = o.write_sgf(nowhere, rich_sgf(toy))
    assert not written and "does not exist" in why[0]
    assert not os.path.exists(os.path.dirname(nowhere)), "a wrong path must not create folders"


def test_write_sgf_replaces_a_damaged_old_file(toy):
    o = toy.o
    with open(toy.sgf_file, "w", encoding="utf-8") as f:
        f.write("(;GM[1]SZ[19]C[killed half way ")
    assert o.write_sgf(toy.sgf_file, rich_sgf(toy))[0] is True


def test_stage_b_keeps_old_sgf_and_saves_the_candidate(toy, monkeypatch):
    o = toy.o
    import json
    A = toy.lib.toy_analysis(toy.N)
    from treesync import make_meta
    A["_meta"] = make_meta(toy.N)
    with open(os.path.join(toy.W, "g_toy-group.a2.json"), "w", encoding="utf-8") as f:
        json.dump(A, f)
    o.stageB("toy-group", [1])
    before = open(toy.sgf_file, encoding="utf-8").read()
    assert "AN[" in before
    os.remove(os.path.join(toy.W, "g_toy-group.a2.json"))
    monkeypatch.setenv("NOAN", "1")  # a rerun without the analysis would produce a poorer file
    o.stageB("toy-group", [1])
    assert open(toy.sgf_file, encoding="utf-8").read() == before
    assert os.path.exists(os.path.join(toy.W, "rejected", "toy-group.sgf"))
    rep = json.load(open(os.path.join(toy.W, "status_toy-group.json"), encoding="utf-8"))
    assert rep["sgf"]["written"] is False
    monkeypatch.setenv("WEIQI_FORCE", "1")
    o.stageB("toy-group", [1])
    assert "AN[" not in open(toy.sgf_file, encoding="utf-8").read()
