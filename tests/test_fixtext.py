"""Typo dictionary (incident 10): longest first, idempotent, protected words, rule log."""
import json
import os
from collections import Counter

import pytest

import fixtext
import mkfix
from conftest import PIPELINE

REAL_DICT = os.path.join(PIPELINE, "fixdict.json")


def fixer(**rules):
    return fixtext.Fixer(rules)


def test_longest_rule_wins_whatever_the_order():
    a = fixtext.Fixer({"ab": "X", "abc": "Y"})
    b = fixtext.Fixer({"abc": "Y", "ab": "X"})
    assert a.apply("abc ab") == b.apply("abc ab") == "Y X"


def test_short_rule_does_not_eat_a_protected_longer_word():
    fx = fixtext.Fixer(fixtext.load_rules())
    assert fx.apply("拖延时间") == "拖延时间", "拖 -> 托 must not reach 拖延"
    assert fx.apply("白拖角") == "白托角"
    assert fx.apply("黑棋力量很大") == "黑棋力量很大", "黑棋力 -> 黑棋立 must not reach 黑棋力量 (real corruption of an earlier version)"
    assert fx.apply("白棋力量") == "白棋力量"
    fx2 = fixtext.Fixer({**fixtext.load_rules(), "白棋力": "白棋立"})
    assert fx2.apply("白棋力下") == "白棋立下"


def test_cascading_rules_settle_to_the_intended_text():
    fx = fixtext.Fixer({"三天低": "三间低", "低家": "低夹"})
    assert fx.apply("三天低家") == "三间低夹", "the dictionary relies on rules feeding each other"


def test_apply_twice_equals_apply_once():
    rules = fixtext.load_rules(REAL_DICT)
    fx = fixtext.Fixer(rules)
    texts = ["黑旗压 白鸡断 拖延一手", "那白棋有隐争 隐真 隐征", "三天低家 二天高家 搬一下", "即使将来被黑鸡力量也会好一点点", "小木 新位 煎三三 争子 拖先"]
    texts += [k for k in rules] + [v for v in rules.values()] + ["前" + k + "后" for k in list(rules)[:80]]
    for t in texts:
        once = fx.apply(t)
        assert fx.apply(once) == once, (t, once, fx.apply(once))


def test_chain_in_the_real_dictionary_gives_a_stable_result():
    fx = fixtext.Fixer(fixtext.load_rules(REAL_DICT))
    # 隐争 -> 隐征 -> 引征: the old one pass loop stopped at 隐征 and a second application changed it again
    assert fx.apply("那白棋有隐争") == fx.apply(fx.apply("那白棋有隐争")) == "那白棋有引征"


def test_real_dictionary_has_no_hard_problems():
    assert fixtext.check_rules(fixtext.load_rules(REAL_DICT)) == []


def test_cycle_is_reported_and_apply_still_terminates():
    rules = {"a": "b", "b": "a"}
    assert any("cycle" in p for p in fixtext.check_rules(rules))
    fired = Counter()
    fixtext.Fixer(rules).apply("a", fired)
    assert fired["<did not settle>"] == 1
    assert fixtext.check_rules({"": "x"}) == ["empty key"]


def test_which_rules_fired_is_logged():
    fired = Counter()
    fx = fixtext.Fixer(fixtext.load_rules())
    out = fx.apply("黑旗白旗黑旗 拖延", fired)
    assert out == "黑棋白棋黑棋 拖延"
    assert fired == {"黑旗->黑棋": 2, "白旗->白棋": 1}, "identity (protected) matches are not counted as fixes"
    assert "黑旗->黑棋 x2" in fixtext.top(fired)


def test_replacement_characters_are_dropped_and_counted():
    fired = Counter()
    assert fixtext.Fixer({}).apply("脱�先", fired) == "脱先"
    assert fired["<U+FFFD removed>"] == 1


def test_missing_file_means_built_in_rules_only_but_a_damaged_one_is_loud(tmp_path):
    assert fixtext.load_rules(str(tmp_path / "nope.json"))["黑旗"] == "黑棋"
    bad = tmp_path / "fixdict.json"
    bad.write_text('[["a", "b"', encoding="utf-8")
    with pytest.raises(ValueError, match="fixdict.json"):
        fixtext.load_rules(str(bad))


def test_fixer_is_reloaded_when_the_dictionary_file_changes(tmp_path):
    p = tmp_path / "fixdict.json"
    p.write_text(json.dumps([["苹", "果"]], ensure_ascii=False), encoding="utf-8")
    assert fixtext.fixer_for(str(p)).apply("苹") == "果"
    os.utime(p, (1, 1))   # a different mtime
    p.write_text(json.dumps([["苹", "梨"]], ensure_ascii=False), encoding="utf-8")
    os.utime(p, (2, 2))
    assert fixtext.fixer_for(str(p)).apply("苹") == "梨"


# ------------------------------------------------------------------ the maintenance tool

def test_mkfix_normalize_sorts_longest_first_resolves_chains_and_keeps_a_backup(tmp_path, capsys):
    p = tmp_path / "d.json"
    p.write_text(json.dumps([["隐争", "隐征"], ["隐征", "引征"], ["低家", "低夹"], ["三天低", "三间低"], ["隐争", "隐征"]], ensure_ascii=False), encoding="utf-8")
    assert mkfix.main(["normalize", str(p)]) == 0
    pairs = json.loads(p.read_text(encoding="utf-8"))
    assert pairs == [["三天低", "三间低"], ["低家", "低夹"], ["隐争", "引征"], ["隐征", "引征"]]
    assert [len(a) for a, _ in pairs] == sorted((len(a) for a, _ in pairs), reverse=True)
    assert (tmp_path / "d.json.bak").exists()
    again = p.read_text(encoding="utf-8")
    assert mkfix.main(["normalize", str(p)]) == 0 and p.read_text(encoding="utf-8") == again, "normalizing twice changes nothing"


def test_mkfix_refuses_to_write_a_dictionary_with_a_cycle(tmp_path):
    p = tmp_path / "d.json"
    p.write_text(json.dumps([["苹", "果"]], ensure_ascii=False), encoding="utf-8")
    before = p.read_text(encoding="utf-8")
    assert mkfix.main(["add", "x=y", "y=x", "--dict", str(p)]) == 1
    assert p.read_text(encoding="utf-8") == before


def test_mkfix_add_check_and_apply(tmp_path, capsys):
    p = tmp_path / "d.json"
    p.write_text("[]", encoding="utf-8")
    assert mkfix.main(["add", "苹=果", "--dict", str(p)]) == 0
    assert json.loads(p.read_text(encoding="utf-8")) == [["苹", "果"]]
    assert mkfix.main(["check", str(p)]) == 0
    txt = tmp_path / "t.txt"
    txt.write_text("苹和黑旗", encoding="utf-8")
    assert mkfix.main(["apply", str(txt), "--dict", str(p)]) == 0
    cap = capsys.readouterr()
    assert "果和黑棋" in cap.out and "苹->果 x1" in cap.err and txt.read_text(encoding="utf-8") == "苹和黑旗", "apply never edits the file"
    assert mkfix.main(["add", "oops", "--dict", str(p)]) == 2


# ------------------------------------------------------------------ in the pipeline

def test_orch2_fix_uses_the_work_dir_dictionary_and_logs_firing(toy):
    o = toy.o
    with open(os.path.join(toy.W, "fixdict.json"), "w", encoding="utf-8") as f:
        json.dump([["天低家", "间低夹"]], f, ensure_ascii=False)
    assert o.fix("二天低家 黑旗 拖延") == "二间低夹 黑棋 拖延"
    assert o.FIRED["黑旗->黑棋"] == 1
    o.stageB("toy-group", [1])
    log = json.load(open(os.path.join(toy.W, "fixlog_toy-group.json"), encoding="utf-8"))
    assert log["黑旗->黑棋"] == 1, "the toy transcript contains 黑旗"
    assert not o.FIRED
