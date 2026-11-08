"""wq.py fix-setup-turns: list and repair the set-up positions that were analysed for the wrong side (incident 12).

The fake engine answers for Black when a request does not name the player, so an analysis made with the old request code
can be reproduced. The trees and the fake engine are test fixtures, not real KataGo output.
"""
import json
import os

import pytest

import analyze2 as an
import fixturns
import treesync as ts
import wq
from setup_trees import forget_initial_player, run_analysis, tree
from wqutil import atomic_write_json, read_json


# ------------------------------------------------------------------ listing (no engine)

def test_listing_names_the_nodes_and_the_teacher_moves():
    N = tree()
    A = {"0": {"turn": "B", "cand": []}, "1": {"turn": "B", "cand": [{"m": "Q16", "v": 100, "s": 3.0}], "wr": 0.5},
         "1_0": {"turn": "B", "cand": []}, "9": {"turn": "W", "cand": [{"m": "D4", "v": 50, "s": 1.0}]}}
    rows = fixturns.wrong_nodes(N, A)
    assert [r["node"] for r in rows] == [1, 9]
    r1, r9 = rows
    assert (r1["old"], r1["new"], r1["keys"], r1["old_best"]) == ("B", "W", ["1", "1_0"], "Q16")
    assert r1["kids"].startswith("W ") and r1["mixed"] is False
    assert (r9["old"], r9["new"], r9["mixed"]) == ("W", "B", True), "the teacher plays both colours there: flagged"


def test_best_of_uses_the_merge_rule():
    c = [{"m": "A1", "v": 100, "s": 1.0}, {"m": "B1", "v": 3, "s": 9.0}, {"m": "C1", "v": 50, "s": 2.0}, {"m": "D1", "v": 100, "s": 4.0, "f": 1}]
    assert fixturns.best_of({"cand": c})["m"] == "D1", "a forced teacher move counts, a barely visited candidate does not"
    assert fixturns.best_of({"cand": []}) is None


# ------------------------------------------------------------------ the tool (wq.py fix-setup-turns)

@pytest.fixture
def work(eng, monkeypatch):
    """A work folder with one group analysed the old way (wrong turns at nodes 1 and 7), plus a good group."""
    N = tree()
    with monkeypatch.context() as old_code:
        forget_initial_player(old_code)
        rc, _ = run_analysis(eng, N)
    assert rc == 0
    rc, _ = run_analysis(eng, N, name="good-group")
    assert rc == 0
    A = read_json(os.path.join(eng, "g_good-group.a2.json"))
    assert an.wrong_turns(N, A) == []
    return str(eng)


def a2(work, name="toy-group"):
    return read_json(os.path.join(work, "g_%s.a2.json" % name))


def test_dry_run_lists_and_changes_nothing_and_needs_no_engine(work, monkeypatch, capsys):
    monkeypatch.setenv("WEIQI_KATAGO_CMD", json.dumps([os.path.join(work, "no-such-engine")]))
    before = open(os.path.join(work, "g_toy-group.a2.json"), "rb").read()
    for args in (["fix-setup-turns", "--work", work], ["fix-setup-turns", "--work", work, "--dry-run"]):
        assert wq.main(args) == 0
        out = capsys.readouterr().out
        assert "toy-group: 2 node(s) analysed for the wrong side" in out
        assert "node 1: recorded B, teacher plays W" in out and "should be W" in out
        assert "node 7: recorded B" in out
        assert "good-group: ok" in out
        assert "2 node(s) in 1 group(s)" in out and "add --apply" in out
    assert open(os.path.join(work, "g_toy-group.a2.json"), "rb").read() == before
    assert not os.path.exists(os.path.join(work, fixturns.BACKUP_DIR))


def test_apply_and_dry_run_exclude_each_other():
    with pytest.raises(SystemExit):
        wq.main(["fix-setup-turns", "--apply", "--dry-run"])


def test_apply_redoes_only_the_wrong_nodes_and_keeps_everything_else(work, capsys):
    N = tree()
    old = a2(work)
    meta = dict(old["_meta"])
    assert wq.main(["fix-setup-turns", "--work", work, "--apply"]) == 0
    out = capsys.readouterr().out
    new = a2(work)
    assert new["_meta"] == meta, "the tree fingerprint block is not touched"
    assert an.wrong_turns(N, new) == []
    assert new["1"]["turn"] == "W" and new["7"]["turn"] == "W" and new["4"]["turn"] == "B"
    for k in old:
        if k not in ("1", "7", "1_0", "7_0"):
            assert new[k] == old[k], "entry %s must stay as it was" % k
    assert list(new) == list(old), "same keys in the same order"
    assert any(m.get("f") for m in new["1"]["cand"]), "the teacher's moves were evaluated by force again"
    assert ts.check_analysis(N, new) == ("ok", "")
    assert "node 1: turn B -> W, best move" in out and "node 7: turn B -> W" in out
    assert "good-group" not in out.split("asking KataGo")[1], "the good group is not asked"
    # the original is kept, the temp files are gone
    bk = os.path.join(work, fixturns.BACKUP_DIR)
    assert read_json(os.path.join(bk, "g_toy-group.a2.json")) == old
    assert not [f for f in os.listdir(work) if ".tmp." in f]
    rep = read_json(os.path.join(bk, "fix_setup_turns_report.json"))
    group = rep["runs"][0]["groups"][0]
    assert group["group"] == "toy-group" and {n["node"] for n in group["nodes"]} == {1, 7}


def test_second_run_finds_nothing_to_do(work, capsys):
    assert wq.main(["fix-setup-turns", "--work", work, "--apply"]) == 0
    capsys.readouterr()
    assert wq.main(["fix-setup-turns", "--work", work, "--apply"]) == 0
    out = capsys.readouterr().out
    assert "0 node(s) in 0 group(s)" in out and "asking KataGo" not in out
    assert len(os.listdir(os.path.join(work, fixturns.BACKUP_DIR))) <= 3, "no second backup of an untouched file"


def test_backup_is_never_overwritten_and_an_identical_one_is_reused(tmp_path):
    src = tmp_path / "g_x.a2.json"
    bk = str(tmp_path / "bk")
    src.write_text('{"a": 1}', encoding="utf-8")
    first = fixturns.backup_copy(str(src), bk)
    assert fixturns.backup_copy(str(src), bk) == first, "same content: reused"
    src.write_text('{"a": 2}', encoding="utf-8")
    second = fixturns.backup_copy(str(src), bk)
    assert second != first and second.endswith(".2")
    assert open(first, encoding="utf-8").read() == '{"a": 1}', "the first backup stays the original"
    assert sorted(os.listdir(bk)) == ["g_x.a2.json", "g_x.a2.json.2"]


def test_only_asks_the_engine_about_the_wrong_nodes(work, monkeypatch):
    log = os.path.join(work, "reqs.log")
    monkeypatch.setenv("FAKE_REQUEST_LOG", log)
    assert wq.main(["fix-setup-turns", "--work", work, "--apply"]) == 0
    ids = [json.loads(x)["id"] for x in open(log, encoding="utf-8").read().splitlines()]
    bases = {i.lstrip("f").split("_")[0] for i in ids if i != "selftest"}
    assert "1" in bases and "7" in bases
    assert not (bases & {"4", "9", "14"}), "nodes that were fine are not asked again: %s" % sorted(ids)
    sent = {json.loads(x)["id"]: json.loads(x) for x in open(log, encoding="utf-8").read().splitlines()}
    assert sent["1"]["initialPlayer"] == "W" and sent["7"]["initialPlayer"] == "W"


def test_engine_crash_leaves_the_file_alone(work, monkeypatch, capsys):
    before = open(os.path.join(work, "g_toy-group.a2.json"), "rb").read()
    monkeypatch.setenv("FAKE_CRASH_AFTER", "2")
    assert wq.main(["fix-setup-turns", "--work", work, "--apply"]) == 4
    assert "ERROR" in capsys.readouterr().out
    assert open(os.path.join(work, "g_toy-group.a2.json"), "rb").read() == before
    monkeypatch.delenv("FAKE_CRASH_AFTER")
    assert wq.main(["fix-setup-turns", "--work", work, "--apply"]) == 0, "and it can simply be run again"
    assert an.wrong_turns(tree(), a2(work)) == []


def test_missing_engine_is_reported(work, monkeypatch, capsys):
    monkeypatch.setenv("WEIQI_KATAGO_CMD", json.dumps([os.path.join(work, "no-such-engine")]))
    assert wq.main(["fix-setup-turns", "--work", work, "--apply"]) == 5
    assert "cannot start KataGo" in capsys.readouterr().out
    assert a2(work)["1"]["turn"] == "B"


def test_group_with_another_tree_is_skipped_not_repaired(work, capsys):
    p = os.path.join(work, "g_toy-group.a2.json")
    A = read_json(p)
    A["_meta"]["tree_fp"] = "0123456789abcdef"
    atomic_write_json(p, A)
    assert wq.main(["fix-setup-turns", "--work", work, "--apply"]) == 1
    out = capsys.readouterr().out
    assert "SKIPPED toy-group: analysis is stale" in out and "asking KataGo" not in out
    assert read_json(p) == A


def test_unreadable_group_is_reported(work, capsys):
    os.remove(os.path.join(work, "g_toy-group.n.json"))
    assert wq.main(["fix-setup-turns", "--work", work]) == 1
    assert "SKIPPED toy-group: tree or analysis cannot be read" in capsys.readouterr().out


def test_only_limits_the_groups(work, capsys):
    assert wq.main(["fix-setup-turns", "--work", work, "--only", "good-group"]) == 0
    out = capsys.readouterr().out
    assert "good-group: ok" in out and "toy-group" not in out


def test_a_file_changed_while_the_engine_worked_is_not_overwritten(work, capsys):
    plans, _ = fixturns.plan_work(work)
    p = os.path.join(work, "g_toy-group.a2.json")
    live = read_json(p)
    live["1"]["score"] = 99.0       # somebody else rewrote the entry after we read it
    atomic_write_json(p, live)
    new = {"1": dict(live["1"], turn="W")}
    assert fixturns.write_group(plans[0], new, os.path.join(work, "bk"), print) is False
    assert "changed while we worked" in capsys.readouterr().out
    assert read_json(p) == live
    live["_meta"]["tree_fp"] = "other"
    atomic_write_json(p, live)
    assert fixturns.write_group(plans[0], {}, os.path.join(work, "bk"), print) is False


def test_an_engine_that_ignores_the_player_is_not_believed(work, monkeypatch, capsys):
    """An engine or bridge that drops initialPlayer answers for Black again. Those answers must not be written."""
    real = an.query

    def lossy(*a, **k):
        r = real(*a, **k)
        r.pop("initialPlayer", None)
        return r

    monkeypatch.setattr(an, "query", lossy)
    before = open(os.path.join(work, "g_toy-group.a2.json"), "rb").read()
    assert wq.main(["fix-setup-turns", "--work", work, "--apply"]) == 1
    assert "the engine answer is unusable" in capsys.readouterr().out
    assert open(os.path.join(work, "g_toy-group.a2.json"), "rb").read() == before


def test_check_command_reports_a_wrong_side(work, capsys):
    assert wq.main(["check", "toy-group", "--work", work]) == 1
    assert "side to move: WRONG at 2 entries" in capsys.readouterr().out
    assert wq.main(["check", "good-group", "--work", work]) == 0
    assert "side to move: ok" in capsys.readouterr().out
