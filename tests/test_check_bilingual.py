"""Tests for tools/check_bilingual.py, with small toy documents for every rule.

Run them in Docker, no venv, nothing is installed on the host:

    docker run --rm -v "$PWD":/app -w /app python:3.12-slim sh -c "pip install -q --root-user-action=ignore pytest && python -m pytest -q tests/test_check_bilingual.py"

In Git Bash on Windows put MSYS_NO_PATHCONV=1 in front of docker so that /app is not rewritten.
"""
import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import check_bilingual as cb  # noqa: E402

EN = "This is a plain English sentence about the project."
EN2 = "Another English sentence explains the second point here."
ZH = "这是一句关于这个项目的普通中文句子。"
ZH2 = "另一句中文解释了这里的第二个要点。"


def check(text, yaml=False):
    return cb.check_text(text, "doc.md", yaml=yaml).problems


def found(text, yaml=False):
    """(line, kind, rule) of every problem."""
    return [(p.line, p.kind, p.rule) for p in check(text, yaml)]


def doc(*blocks):
    return "\n\n".join(blocks) + "\n"


# ---------------------------------------------------------------------------
# (a) paragraphs: the English paragraph directly followed by the Chinese one
# ---------------------------------------------------------------------------

def test_chinese_first_pair_is_clean():
    assert found(doc(ZH, EN)) == []


def test_english_first_pair_is_flagged_with_its_line():
    assert found(doc(EN, ZH)) == [(1, "order", "paragraph")]


def test_each_wrong_pair_is_flagged():
    text = doc(EN, ZH, EN2, ZH2)
    assert found(text) == [(1, "order", "paragraph"), (5, "order", "paragraph")]


def test_second_pair_wrong_only():
    text = doc(ZH, EN, EN2, ZH2)
    assert found(text) == [(5, "order", "paragraph")]


def test_multi_line_paragraph_reports_the_first_line_and_the_range():
    text = "First English line of a wrapped paragraph\nand the second English line of it.\n\n" + ZH + "\n"
    probs = check(text)
    assert [(p.line, p.kind) for p in probs] == [(1, "order")]
    assert "lines 1-2" in probs[0].reason


def test_heading_between_the_paragraphs_breaks_the_pair():
    text = "# 标题 / Title\n\n" + EN + "\n\n## 另一个标题 / Another\n\n" + ZH + "\n"
    assert [p.kind for p in check(text)] == ["missing"]


def test_code_block_between_the_paragraphs_is_transparent():
    text = EN + "\n\n```\nsome code\n```\n\n" + ZH + "\n"
    assert found(text) == [(1, "order", "paragraph")]


def test_english_first_in_a_block_quote():
    text = "> " + EN + "\n>\n> " + ZH + "\n"
    assert found(text) == [(1, "order", "paragraph")]


def test_chinese_first_in_a_block_quote_is_clean():
    text = "> " + ZH + "\n>\n> " + EN + "\n"
    assert found(text) == []


def test_pair_inside_a_list_item_continuation():
    text = "1. " + EN + "\n\n   " + ZH + "\n"
    assert found(text) == [(1, "order", "paragraph")]


def test_correct_pair_inside_a_list_item():
    text = "1. " + ZH + "\n\n   " + EN + "\n"
    assert found(text) == []


def test_lone_english_line_followed_by_correct_pairs():
    # a tagline without translation, then proper pairs: only the tagline is reported
    text = doc(EN, ZH, EN2)
    assert found(text) == [(1, "missing", "paragraph")]


def test_hard_break_pair_in_one_paragraph():
    text = EN + "<br>" + ZH + "\n"
    assert [p.kind for p in check(text)] == ["order"]


def test_hard_break_chinese_first_is_clean():
    text = ZH + "\\\n" + EN + "\n"
    assert found(text) == []


def test_trailing_spaces_inside_one_language_do_not_split():
    text = "First half of an English sentence that goes on  \nand then ends here for good.\n\n" + ZH + "\n"
    probs = check(text)
    assert len(probs) == 1 and probs[0].kind == "order"


def test_grouped_blocks_are_reported_as_order():
    # all Chinese bullets first, then all English bullets
    text = "* " + ZH + "\n* " + ZH2 + "\n\n* " + EN + "\n* " + EN2 + "\n"
    kinds = [(p.kind, p.rule) for p in check(text)]
    assert kinds and all(k == ("order", "grouped") for k in kinds)


# ---------------------------------------------------------------------------
# (b) missing translations
# ---------------------------------------------------------------------------

def test_english_only_paragraph_in_a_bilingual_document():
    text = doc(ZH, EN, EN2)
    assert found(text) == [(5, "missing", "paragraph")]


def test_chinese_only_paragraph_is_not_reported():
    assert found(doc(ZH, EN, ZH2)) == []


def test_document_without_any_chinese_is_folded_into_one_line():
    text = doc(EN, EN2, "A third English paragraph without any translation.")
    probs = check(text)
    assert len(probs) == 1
    assert (probs[0].kind, probs[0].rule, probs[0].count) == ("missing", "document", 3)


def test_short_english_lines_are_ignored():
    assert found(doc(ZH, EN, "Closes #4", "See below")) == []


def test_english_next_to_a_mixed_paragraph_is_not_reported():
    mixed = "我们在 README 里用 Docker 和 pytest 跑 the full test suite on every change 然后看结果"
    assert cb.classify(mixed) == cb.MIXED
    assert found(doc(ZH, EN, mixed, EN2)) == []


def test_lone_english_list_item():
    text = "- " + ZH + "\n- " + EN + "\n- " + EN2 + "\n"
    assert found(text) == [(3, "missing", "list")]


# ---------------------------------------------------------------------------
# (c) headings
# ---------------------------------------------------------------------------

def test_english_first_heading():
    probs = check("## What changed / 改动内容\n")
    assert [(p.kind, p.rule) for p in probs] == [("order", "heading")]
    assert "## 改动内容 / What changed" in probs[0].suggestion


def test_chinese_first_heading_is_clean():
    assert found("## 改动内容 / What changed\n") == []


def test_english_only_heading_in_a_bilingual_document():
    text = "## 概述 / Summary\n\n" + ZH + "\n\n" + EN + "\n\n## Risks\n"
    assert (7, "missing", "heading") in found(text)


def test_setext_heading_english_first():
    assert found("What changed / 改动内容\n=======================\n") == [(1, "order", "heading")]


def test_heading_with_numbering_and_emphasis():
    assert found("## 2. **Why** / 为什么\n") == [(1, "order", "heading")]
    assert found("## 2. **为什么** / **Why**\n") == []


def test_identifier_and_acronym_headings_are_not_translated():
    assert found("# ai-weiqi-new-mind\n\n" + ZH + "\n\n" + EN + "\n") == []
    assert found("## FAQ\n\n" + ZH + "\n\n" + EN + "\n") == []


def test_heading_inside_code_block_is_ignored():
    assert found("```\n## What changed / 改动内容\n```\n") == []


# ---------------------------------------------------------------------------
# (d) table cells and titles
# ---------------------------------------------------------------------------

TABLE_HEAD = "| A | B |\n|---|---|\n"


def test_english_first_cell():
    text = "| 项目 / Item | 状态 / State |\n|---|---|\n| Viewer / 查看器 | 完成 / Done |\n"
    assert found(text) == [(3, "order", "cell")]


def test_chinese_first_cells_are_clean():
    text = "| 项目 / Item | 状态 / State |\n|---|---|\n| 查看器 / Viewer | 完成 / Done |\n"
    assert found(text) == []


def test_english_only_cell_in_a_bilingual_table():
    text = "| 项目 / Item | 说明 / Note |\n|---|---|\n| 查看器 / Viewer | A single file that opens offline |\n"
    assert found(text) == [(3, "missing", "cell")]


def test_cell_with_chinese_first_but_mostly_a_name():
    text = ("| 部分 / Part | 许可 / License |\n|---|---|\n"
            "| 代码 / Code | PolyForm Noncommercial License 1.0.0，见 [LICENSE](LICENSE) "
            "/ PolyForm Noncommercial License 1.0.0, see [LICENSE](LICENSE) |\n")
    assert found(text) == []


def test_table_of_pure_code_is_ignored():
    text = "| Path | Command |\n|---|---|\n| `a/b.py` | `python a/b.py --flag` |\n| `c` | `d / e` |\n"
    assert [p.rule for p in check(text) if p.line > 2] == []


def test_names_links_and_acronyms_in_cells_are_not_translations():
    text = ("| 平台 / Platform | 文档 / Docs |\n|---|---|\n"
            "| Hugging Face Jobs | [Jobs docs](https://huggingface.co/docs/jobs) |\n"
            "| Vast.ai | GPU |\n")
    assert found(text) == []


def test_pipe_inside_inline_code_does_not_split_the_cell():
    text = "| 项目 / Item | 说明 / Note |\n|---|---|\n| 管道 / Pipe | `a | b` 示例 / example |\n"
    assert found(text) == []


def test_split_row_keeps_pipes_inside_code_and_escaped_pipes():
    assert cb.split_row("| a | `b | c` | d |") == ["a", "`b | c`", "d"]
    assert cb.split_row(r"a | b\|c | d") == ["a", "b|c", "d"]
    assert cb.split_row("| only |") == ["only"]


def test_cell_with_br_separator():
    text = "| 项目 / Item | 说明 / Note |\n|---|---|\n| 查看器 / Viewer | Opens offline in a browser<br>离线用浏览器打开 |\n"
    assert found(text) == [(3, "order", "cell")]


def test_english_cell_next_to_a_chinese_cell_is_not_reported():
    text = "| Item | 项目 |\n|---|---|\n| Viewer | 查看器 |\n"
    assert found(text) == []


def test_title_english_first():
    probs = cb.check_title("Add a bilingual check / 添加双语检查").problems
    assert [(p.kind, p.rule) for p in probs] == [("order", "title")]


def test_title_chinese_first_is_clean():
    assert cb.check_title("添加双语检查 / Add a bilingual check").problems == []


def test_title_english_only():
    probs = cb.check_title("Add a bilingual check").problems
    assert [(p.kind, p.rule) for p in probs] == [("missing", "title")]


def test_title_with_code_and_slash_in_the_english_part():
    assert cb.check_title("修复 `a / b` 的解析 / Fix parsing of `a / b`").problems == []


# ---------------------------------------------------------------------------
# (e) list items
# ---------------------------------------------------------------------------

def test_english_item_before_its_chinese_item():
    text = "- " + EN + "\n- " + ZH + "\n- " + EN2 + "\n- " + ZH2 + "\n"
    assert found(text) == [(1, "order", "list"), (3, "order", "list")]


def test_chinese_item_before_its_english_item_is_clean():
    text = "- " + ZH + "\n- " + EN + "\n- " + ZH2 + "\n- " + EN2 + "\n"
    assert found(text) == []


def test_numbered_items_in_the_wrong_order():
    text = "1. " + EN + "\n2. " + ZH + "\n"
    assert found(text) == [(1, "order", "list")]


def test_checklist_item_with_english_first_slash():
    text = "- [ ] Run the check script before you push / 推送之前先运行检查脚本\n"
    assert found(text) == [(1, "order", "inline")]


def test_checklist_item_chinese_first_is_clean():
    text = "- [ ] 推送之前先运行检查脚本 / Run the check script before you push\n"
    assert found(text) == []


def test_loose_list_with_pairs_inside_each_item():
    text = ("- " + ZH + "\n\n  " + EN + "\n\n- " + ZH2 + "\n\n  " + EN2 + "\n")
    assert found(text) == []


# ---------------------------------------------------------------------------
# inline "A / B" lines
# ---------------------------------------------------------------------------

def test_inline_english_first_pair_in_a_paragraph():
    text = "Conventional Commits 1.0.0 / 约定式提交规范: https://www.conventionalcommits.org/\n"
    assert found(text) == [(1, "order", "inline")]


def test_stray_slash_between_two_names_in_a_chinese_sentence():
    text = doc("免费额度用完了，等一会儿再试，或者改用 Kaggle / LRZ。", "The free quota is used up, wait a while or switch to Kaggle / LRZ.")
    assert found(text) == []


def test_unit_slash_is_not_a_separator():
    text = "| 项目 / Item | 速度 / Speed |\n|---|---|\n| 速度 / Speed | 约 20 visits/秒 / about 20 visits per second |\n"
    assert found(text) == []


# ---------------------------------------------------------------------------
# false positives
# ---------------------------------------------------------------------------

def test_fenced_code_is_ignored():
    text = doc(ZH, EN, "```\nThis is only some English code sample here\n这是代码里的中文注释\n```")
    assert found(text) == []


def test_tilde_fence_and_longer_fence():
    tilde = "~~~\nEnglish lines inside the fence stay unchecked here\n~~~"
    longer = "````\n```\ninner\n```\nEnglish text still inside the outer fence\n````"
    assert found(doc(ZH, EN, tilde, longer)) == []


def test_indented_code_is_ignored():
    text = doc(ZH, EN, "    An English sentence that is indented like code here")
    assert found(text) == []


def test_inline_code_does_not_count_as_text():
    text = doc(ZH, EN, "`python tools/check_bilingual.py --fix-suggest docs/WORKFLOW.md`")
    assert found(text) == []


def test_html_comments_are_ignored_even_over_several_lines():
    text = ("<!--\nTitle: type(scope): short imperative subject, for example the first line\n"
            "标题:简短的祈使句主题\n-->\n\n## 改了什么 / What changed\n\n" + ZH + "\n\n" + EN + "\n")
    assert found(text) == []


def test_comment_markers_inside_a_code_block_do_not_hide_text():
    text = "```\n<!-- not a comment\n```\n\n" + EN + "\n\n" + ZH + "\n"
    assert found(text) == [(5, "order", "paragraph")]


def test_urls_next_to_chinese_text_stay_chinese():
    text = doc("版权所有 (c) 2026 Somebody（https://github.com/somebody）。下文未明确授予的权利一律保留。",
               "Copyright (c) 2026 Somebody (https://github.com/somebody). All rights not granted below are reserved.")
    assert found(text) == []


def test_url_glued_to_chinese_text_does_not_swallow_it():
    zh = "Somebody Else Person owns this（https://github.com/somebody）这个项目的全部权利一律保留。"
    assert cb.classify(zh) == cb.ZH
    assert found(doc(zh, "All rights to this project are reserved by Somebody Else Person here.")) == []


def test_inline_code_with_english_words_is_not_text():
    assert found(doc(ZH, EN, "`please run the whole check script now`")) == []
    assert cb.classify("`please run the whole check script now`") == cb.NONE


def test_link_targets_and_images_are_not_text():
    text = doc(ZH, EN, "![a long alternative text for the screenshot](docs/some/very/long/path/to/image.png)")
    assert found(text) == []


def test_paragraph_that_is_only_links_and_code():
    text = doc(ZH, EN, "[CHANGELOG.md](CHANGELOG.md) and `README.md` and https://example.com/a/b/c/d")
    assert found(text) == []


def test_chinese_paragraph_quoting_english_words_is_chinese():
    para = "我们使用 KataGo 和 yt-dlp 来分析 Bilibili 上的视频，并把结果写进 SGF 文件。"
    assert cb.classify(para) == cb.ZH
    assert found(doc(para, "We use KataGo and yt-dlp to analyse the videos on Bilibili.")) == []


def test_english_paragraph_quoting_chinese_names_is_english():
    para = ("Only 小目-小飞挂-二间高夹 has the new evaluation. The other three have none for now: "
            "the old results were withdrawn because of a score perspective error.")
    assert cb.classify(para) == cb.EN
    zh = "只有 小目-小飞挂-二间高夹 带有新版评估；其余三个暂时没有，旧结果因分数视角错误已撤下。"
    assert found(doc(para, zh)) == [(1, "order", "paragraph")]
    assert found(doc(zh, para)) == []


def test_classify_thresholds():
    assert cb.classify(ZH) == cb.ZH
    assert cb.classify(EN) == cb.EN
    assert cb.classify("12345 ... ---") == cb.NONE
    assert cb.classify("Fixes #4") == cb.NONE
    assert cb.classify("") == cb.NONE


def test_front_matter_crlf_and_bom():
    text = "---\ntitle: x\n---\n\n" + EN + "\n\n" + ZH + "\n"
    assert found(text) == [(5, "order", "paragraph")]
    assert found(text.replace("\n", "\r\n")) == [(5, "order", "paragraph")]
    assert found(chr(0xFEFF) + text) == [(5, "order", "paragraph")]


def test_directive_switches_a_region_off():
    text = ("<!-- bilingual-check: off -->\n" + EN + "\n\n" + ZH + "\n<!-- bilingual-check: on -->\n\n"
            + EN2 + "\n\n" + ZH2 + "\n")
    assert found(text) == [(7, "order", "paragraph")]


def test_skip_file_directive():
    text = "<!-- bilingual-check: skip-file -->\n\n" + EN + "\n\n" + ZH + "\n"
    rep = cb.check_text(text, "doc.md")
    assert rep.problems == [] and rep.skipped


def test_empty_document():
    assert found("") == []
    assert found("\n\n") == []


# ---------------------------------------------------------------------------
# YAML issue forms
# ---------------------------------------------------------------------------

FORM = """name: Bug report / 缺陷报告
description: 查看器或工具的行为不符合预期 / The viewer or a tool does not behave as expected
title: "bug: "
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        Please do not paste tokens or keys into the form.

        请不要在表单里贴令牌或密钥。
  - type: textarea
    id: what
    attributes:
      label: 发生了什么 / What happened
"""


def test_yaml_form_reports_english_first_scalars_and_block_text():
    probs = check(FORM, yaml=True)
    assert [(p.line, p.kind, p.rule) for p in probs] == [
        (1, "order", "yaml"), (9, "order", "paragraph")]


def test_yaml_form_chinese_first_is_clean():
    fixed = (FORM.replace("Bug report / 缺陷报告", "缺陷报告 / Bug report")
             .replace("Please do not paste tokens or keys into the form.\n\n        请不要在表单里贴令牌或密钥。",
                      "请不要在表单里贴令牌或密钥。\n\n        Please do not paste tokens or keys into the form."))
    assert found(fixed, yaml=True) == []


# ---------------------------------------------------------------------------
# output, suggestions and the command line
# ---------------------------------------------------------------------------

def write(tmp_path, name, text):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.encode("utf-8"))
    return p


def test_exit_code_and_line_format(tmp_path, capsys):
    bad = write(tmp_path, "bad.md", doc(EN, ZH))
    code = cb.run([str(bad)])
    out = capsys.readouterr().out.splitlines()
    assert code == 1
    assert out[0].startswith(str(bad) + ":1: order/paragraph: ")
    assert out[-1] == "Checked 1 input: 1 problems (1 order, 0 missing translation)."


def test_clean_file_exits_zero(tmp_path, capsys):
    good = write(tmp_path, "good.md", doc("## 概述 / Summary", ZH, EN))
    assert cb.run([str(good)]) == 0
    assert capsys.readouterr().out.strip() == "Checked 1 input: no problems."


def test_missing_file_exits_two(tmp_path, capsys):
    assert cb.run([str(tmp_path / "nope.md")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_fix_suggest_prints_the_swap_and_edits_nothing(tmp_path, capsys):
    bad = write(tmp_path, "bad.md", "## What changed / 改动内容\n\n" + EN + "\n\n" + ZH + "\n")
    before = bad.read_bytes()
    mtime = os.stat(bad).st_mtime_ns
    code = cb.run(["--fix-suggest", str(bad)])
    out = capsys.readouterr().out
    assert code == 1
    assert "suggest: replace with: ## 改动内容 / What changed" in out
    assert "suggest: swap line 3 with line 5" in out
    assert bad.read_bytes() == before
    assert os.stat(bad).st_mtime_ns == mtime


def test_without_fix_suggest_no_suggestion_lines(tmp_path, capsys):
    bad = write(tmp_path, "bad.md", doc(EN, ZH))
    cb.run([str(bad)])
    assert "suggest:" not in capsys.readouterr().out


def test_exempt_files_are_skipped(tmp_path, capsys):
    lic = write(tmp_path, "LICENSE", doc(EN, EN2))
    msg = write(tmp_path, ".gitmessage", doc(EN, EN2))
    other = write(tmp_path, "terms.txt", doc(EN, EN2))
    assert cb.run([str(lic), str(msg)]) == 0
    assert cb.run([str(other)]) == 1
    capsys.readouterr()
    assert cb.run(["--exempt", "terms.*", str(other)]) == 0
    capsys.readouterr()
    rules = write(tmp_path, "exempt.txt", "# comment\nterms.*\n")
    assert cb.run(["--exempt-file", str(rules), str(other)]) == 0


def test_default_document_set(tmp_path, capsys):
    write(tmp_path, "README.md", doc(EN, ZH))
    write(tmp_path, "docs/WORKFLOW.md", doc(ZH, EN))
    write(tmp_path, "docs/deep/ignored.md", doc(EN, ZH))
    write(tmp_path, "notes.md", doc(EN, ZH))
    write(tmp_path, "remote/README.md", doc(EN, ZH))
    write(tmp_path, ".github/pull_request_template.md", doc(EN, ZH))
    write(tmp_path, ".github/ISSUE_TEMPLATE/bug.yml", "name: Bug report / 缺陷报告\n")
    write(tmp_path, "LICENSE", doc(EN, EN2))
    code = cb.run(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert code == 1
    flagged = {line.split(":")[0] for line in out.splitlines() if ": order/" in line}
    assert flagged == {"README.md", "remote/README.md", ".github/pull_request_template.md",
                       ".github/ISSUE_TEMPLATE/bug.yml"}


def test_include_adds_a_pattern_to_the_default_set(tmp_path, capsys):
    write(tmp_path, "notes.md", doc(EN, ZH))
    assert cb.run(["--root", str(tmp_path)]) == 0
    capsys.readouterr()
    assert cb.run(["--root", str(tmp_path), "--include", "notes.md"]) == 1


def test_title_option(capsys):
    assert cb.run(["--title", "Add x / 添加 x"]) == 1
    assert "order/title" in capsys.readouterr().out
    assert cb.run(["--title", "添加 x / Add x"]) == 0


def test_stdin_body(capsys):
    assert cb.run(["-"], stdin=doc(EN, ZH)) == 1
    assert capsys.readouterr().out.startswith("<stdin>:1: order/paragraph")


def test_pr_json_single_object_and_list(tmp_path, capsys):
    one = {"number": 6, "title": "Make it bilingual / 改成双语",
           "body": "## Summary / 概述\n\n" + doc(EN, ZH)}
    many = [one, {"number": 7, "title": "修复 / Fix", "body": doc(ZH, EN)}]
    f1 = write(tmp_path, "one.json", json.dumps(one, ensure_ascii=False))
    f2 = write(tmp_path, "many.json", json.dumps(many, ensure_ascii=False))
    assert cb.run(["--pr-json", str(f1)]) == 1
    out = capsys.readouterr().out
    assert "PR #6 title:1: order/title" in out
    assert "PR #6 body:1: order/heading" in out
    assert "PR #6 body:3: order/paragraph" in out
    assert cb.run(["--pr-json", str(f2)]) == 1
    out = capsys.readouterr().out
    assert "PR #7" not in out


@pytest.mark.skipif(os.name == "nt", reason="needs a shell script as fake gh")
def test_pr_option_calls_gh(tmp_path, capsys, monkeypatch):
    gh = tmp_path / "bin" / "gh"
    gh.parent.mkdir()
    payload = json.dumps({"number": 12, "title": "Fix it / 修复", "body": doc(EN, ZH)}, ensure_ascii=False)
    gh.write_text("#!/bin/sh\necho \"$@\" > \"%s\"\ncat <<'EOF'\n%s\nEOF\n" % (tmp_path / "args.txt", payload))
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(gh.parent) + os.pathsep + os.environ["PATH"])
    assert cb.run(["--pr", "12", "--repo", "owner/name"]) == 1
    out = capsys.readouterr().out
    assert "PR #12 title:1: order/title" in out
    assert "PR #12 body:1: order/paragraph" in out
    args = (tmp_path / "args.txt").read_text().split()
    assert args[:3] == ["pr", "view", "12"] and "--json" in args and "owner/name" in args


@pytest.mark.skipif(os.name == "nt", reason="needs a shell script as fake gh")
def test_pr_option_reports_a_failing_gh(tmp_path, capsys, monkeypatch):
    gh = tmp_path / "bin" / "gh"
    gh.parent.mkdir()
    gh.write_text("#!/bin/sh\necho 'no such pull request' >&2\nexit 1\n")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(gh.parent) + os.pathsep + os.environ["PATH"])
    assert cb.run(["--pr", "99"]) == 2
    assert "no such pull request" in capsys.readouterr().err


def test_summary_counts_both_kinds(tmp_path, capsys):
    bad = write(tmp_path, "bad.md", doc(ZH, EN, EN2) + "\n" + doc(EN, ZH))
    assert cb.run([str(bad)]) == 1
    assert capsys.readouterr().out.splitlines()[-1] == "Checked 1 input: 2 problems (1 order, 1 missing translation)."


def test_glob_matching_rules():
    assert cb.matches_any("docs/LICENSE-ADVICE.md", ["LICENSE-*"]) is True
    assert cb.matches_any("LICENSE", ["LICENSE"]) is True
    assert cb.matches_any("a/b/.gitmessage", [".gitmessage"]) is True
    assert cb.matches_any("docs/a.md", ["docs/*.md"]) is True
    assert cb.matches_any("docs/x/a.md", ["docs/*.md"]) is False
    assert cb.matches_any("docs/x/a.md", ["docs/**"]) is True
