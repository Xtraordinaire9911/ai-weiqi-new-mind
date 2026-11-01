"""Tests for tools/strip_commentary.py: the stripped copy for the public repository.

Run in Docker (no venv): docker run --rm -v "$PWD":/app -w /app python:3.12-slim sh -c "pip install -q --root-user-action=ignore pytest && python -m pytest -q tests/test_strip_commentary.py"
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import make_site as ms  # noqa: E402
import strip_commentary as sc  # noqa: E402

COMMENT = ('【老师讲解 @0|0:30】大家好 今天讲小飞挂 这是老师讲的一大段话用来保证删掉的字数比提示文字多\n'
           '【要点】黑棋要先手\n【AI局部评估】候选点 D4 最优\n'
           '【老师讲解 @1|2:05】再来看一个变化 \\] 带转义的括号和另外一大段话用来保证删掉的字数比提示文字多\n'
           '【避雷/注意点】不要在这里贪')
SGF = '(;GM[1]SZ[19]PC[BV1abc]C[' + COMMENT + ']AB[dd];B[pd]C[' + COMMENT + '];W[dp])'


def make_root(tmp_path, sgf=SGF):
    root = tmp_path / 'in'
    f = root / 'data' / 'sgf' / 'src' / 'series' / 'one.sgf'
    f.parent.mkdir(parents=True)
    f.write_text(sgf, encoding='utf-8', newline='')
    col = [{'id': 'src/series/one', 'name': 'one', 'sgf': sgf}]
    (root / 'data' / 'library.js').write_text(
        'window.LIB=' + json.dumps(col, ensure_ascii=False, separators=(',', ':')) + ";window.LIBT='01-01 00:00';",
        encoding='utf-8', newline='')
    return root


def test_output_has_no_teacher_text_but_keeps_everything_else(tmp_path):
    root, out = make_root(tmp_path), tmp_path / 'out'
    assert sc.run(root, out, check=True, log=lambda m: None) == 0
    text = (out / 'data' / 'sgf' / 'src' / 'series' / 'one.sgf').read_text(encoding='utf-8')
    assert '大家好' not in text and '再来看一个变化' not in text
    for keep in ['【老师讲解 @0|0:30】', '【老师讲解 @1|2:05】', '【要点】黑棋要先手', '【AI局部评估】候选点 D4 最优',
                 '【避雷/注意点】不要在这里贪', 'PC[BV1abc]', 'AB[dd]']:
        assert keep in text
    lib = (out / 'data' / 'library.js').read_text(encoding='utf-8')
    assert lib.startswith('window.LIB=') and lib.endswith("window.LIBT='01-01 00:00';")
    assert '大家好' not in lib


def test_input_is_never_modified(tmp_path):
    root, out = make_root(tmp_path), tmp_path / 'out'
    before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    sc.run(root, out, log=lambda m: None)
    assert {p: p.read_bytes() for p in root.rglob('*') if p.is_file()} == before


def test_dry_run_writes_nothing(tmp_path):
    root, out = make_root(tmp_path), tmp_path / 'out'
    msgs = []
    assert sc.run(root, out, dry=True, log=msgs.append) == 0
    assert not out.exists() and 'dry run' in msgs[0]


@pytest.mark.parametrize('where', ['same', 'inside', 'around'])
def test_refuses_output_that_overlaps_the_input(tmp_path, where):
    root = make_root(tmp_path)
    out = {'same': root, 'inside': root / 'stripped', 'around': tmp_path}[where]
    assert sc.run(root, out, log=lambda m: None) == 2
    assert not (root / 'stripped').exists()


def test_missing_data_folder_is_an_error(tmp_path):
    (tmp_path / 'empty').mkdir()
    assert sc.run(tmp_path / 'empty', tmp_path / 'out', log=lambda m: None) == 2


def test_check_fails_when_library_and_sgf_disagree(tmp_path):
    msgs = []
    root = make_root(tmp_path)   # library.js holds SGF, the file on disk gets an extra newline
    (root / 'data' / 'sgf' / 'src' / 'series' / 'one.sgf').write_text(SGF + '\n', encoding='utf-8', newline='')
    assert sc.run(root, tmp_path / 'out', check=True, log=msgs.append) == 1
    assert any('differs' in m for m in msgs)


def test_plain_sgf_without_commentary_is_copied_byte_for_byte(tmp_path):
    plain = '(;GM[1]SZ[19]C[only a plain note];B[pd])\r\n'
    root, out = make_root(tmp_path, plain), tmp_path / 'out'
    sc.run(root, out, log=lambda m: None)
    assert (out / 'data' / 'sgf' / 'src' / 'series' / 'one.sgf').read_bytes() == plain.encode('utf-8')


def test_main_returns_2_on_bad_input(tmp_path):
    assert sc.main([str(tmp_path / 'nope'), str(tmp_path / 'out')]) == 2


def test_teacher_text_left_detects_leftovers():
    assert sc.teacher_text_left('C[【老师讲解 @0|0:30】还有字]')
    assert not sc.teacher_text_left('C[【老师讲解 @0|0:30】' + ms.OMITTED + ']')
