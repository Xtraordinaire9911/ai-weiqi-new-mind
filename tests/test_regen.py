"""regen.py (incident 5: it replaced good SGFs with empty shells) and the plan checks."""
import json
import os

import pytest

import regen
import treesync as ts
from wqutil import atomic_write_json


def snapshot(root):
    """{relative path: bytes} of everything below root."""
    out = {}
    for d, _, files in os.walk(root):
        for f in files:
            p = os.path.join(d, f)
            out[os.path.relpath(p, root)] = open(p, "rb").read()
    return out


@pytest.fixture
def built(toy, monkeypatch):
    """Toy group built once with matching analysis, so a good SGF with AI data exists."""
    monkeypatch.delenv("NOAN", raising=False)
    A = toy.lib.toy_analysis(toy.N)
    A["_meta"] = ts.make_meta(toy.N)
    atomic_write_json(os.path.join(toy.W, "g_toy-group.a2.json"), A)
    toy.o.stageB("toy-group", [1])
    toy.good = open(toy.sgf_file, encoding="utf-8").read()
    assert "AN[" in toy.good
    return toy


def test_dry_run_writes_nothing_anywhere(built, capsys):
    before = {**snapshot(built.W), **{"sgf/" + k: v for k, v in snapshot(built.PROJ).items()}}
    assert regen.main(["--dry-run", "--only", "toy-group"]) == 0
    after = {**snapshot(built.W), **{"sgf/" + k: v for k, v in snapshot(built.PROJ).items()}}
    after = {k: v for k, v in after.items() if not k.startswith("logs")}   # the log file itself is allowed to grow
    before = {k: v for k, v in before.items() if not k.startswith("logs")}
    assert after == before
    assert "DRY RUN toy-group -> would write" in capsys.readouterr().out


def test_regen_without_analysis_does_not_replace_a_good_sgf_with_a_poorer_one(built, monkeypatch):
    os.remove(os.path.join(built.W, "g_toy-group.a2.json"))   # as if the analysis file were gone
    assert regen.main(["--only", "toy-group"]) == 0
    assert open(built.sgf_file, encoding="utf-8").read() == built.good
    assert os.path.exists(os.path.join(built.W, "rejected", "toy-group.sgf"))
    assert os.environ.get("NOAN") == "1", "regen never starts an analysis by itself"


def test_regen_dry_run_reports_a_refusal(built, capsys):
    os.remove(os.path.join(built.W, "g_toy-group.a2.json"))
    regen.main(["--dry-run", "--only", "toy-group"])
    out = capsys.readouterr().out
    assert "REFUSE" in out and "nodes with AI evaluation" in out


def test_group_without_cache_is_skipped_not_overwritten(built, capsys):
    import shutil
    shutil.rmtree(built.o.D(1))   # no b.json / t.json any more: the old code built an empty tree from this
    assert regen.main(["--only", "toy-group"]) == 0
    assert open(built.sgf_file, encoding="utf-8").read() == built.good
    assert "no cached board/transcript data" in capsys.readouterr().out


def test_regen_uses_a2_json_from_the_current_pipeline(built):
    """The old script only looked at <group>.a.json, a file nothing writes any more."""
    assert regen.main(["--only", "toy-group"]) == 0
    assert open(built.sgf_file, encoding="utf-8").read() == built.good, "same inputs, same SGF"


def test_regen_can_still_improve_an_sgf(built):
    p = os.path.join(built.W, "kp_toy-group.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"1": "新增要点"}, f, ensure_ascii=False)
    assert regen.main(["--only", "toy-group"]) == 0
    assert "新增要点" in open(built.sgf_file, encoding="utf-8").read()


# ------------------------------------------------------------------ plan validation

def test_plan_problems_are_named_before_anything_runs(toy):
    o = toy.o
    assert o.validate_plan() == []
    o.PLAN["merge"]["7"] = [["a/b", [1]], ["toy-group", [1]], ["toy-group", [9]], ["", [2]]]
    problems = "\n".join(o.validate_plan())
    for needle in ("'a/b' is not a usable file name", "'toy-group' appears twice", "video 9 is not in index.json",
                   "'' is not a usable file name"):
        assert needle in problems, needle
    with pytest.raises(RuntimeError, match="plan.json does not fit"):
        o.groups()


def test_index_problems_are_named(toy):
    o = toy.o
    o.IDX.append({"season": 7, "idx": 1, "bvid": "BVdup", "title": "same idx twice", "sec": 5})
    o.IDX.append({"season": 7, "idx": 3, "title": "no bvid"})
    o.vid[3] = o.IDX[-1]
    o.PLAN["merge"]["7"] = [["g", [1, 3]]]
    problems = "\n".join(o.validate_plan())
    assert "different idx values" in problems
    assert "video 3 has no bvid" in problems


def test_groups_left_out_by_max_idx_are_logged_not_silent(toy, monkeypatch, capsys):
    monkeypatch.setattr(toy.o, "MAXIDX", 1)
    names = [g[0] for g in toy.o.groups()]
    assert names == ["toy-group"]
    assert "toy-pair" in capsys.readouterr().out


def test_missing_season_in_plan(toy):
    toy.o.PLAN["merge"] = {}
    assert "no merge list for season 7" in toy.o.validate_plan()[0]
