"""Tests for tools/make_site.py: stripping the teacher commentary and building the site folder.

Run in Docker (no venv): docker run --rm -v "$PWD":/app -w /app python:3.12-slim sh -c "pip install -q --root-user-action=ignore pytest && python -m pytest -q tests/test_make_site.py"
"""
import base64
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import make_site as ms  # noqa: E402

COMMENT = ('【老师讲解 @0|0:30】大家好 今天讲小飞挂 这是老师讲的一大段话用来保证删掉的字数比提示文字多\n'
           '【要点】黑棋要先手\n【AI局部评估】候选点 D4 最优\n'
           '【老师讲解 @1|2:05】再来看一个变化 \\] 带转义的括号和另外一大段话用来保证删掉的字数比提示文字多\n'
           '【避雷/注意点】不要在这里贪')


def sgf_with(c):
    return '(;GM[1]SZ[19]PC[BV1abc]C[' + c + ']AB[dd];B[pd]C[' + c + ']AP[x:1];W[dp])'


def test_strips_teacher_text_and_keeps_header_and_time_link():
    out = ms.strip_sgf(sgf_with(COMMENT))
    assert '大家好' not in out and '再来看一个变化' not in out
    assert '【老师讲解 @0|0:30】' + ms.OMITTED in out and '【老师讲解 @1|2:05】' + ms.OMITTED in out


def test_keeps_key_points_ai_and_other_sections():
    out = ms.strip_sgf(sgf_with(COMMENT))
    for keep in ['【要点】黑棋要先手', '【AI局部评估】候选点 D4 最优', '【避雷/注意点】不要在这里贪']:
        assert keep in out


def test_other_properties_are_untouched_and_sgf_stays_balanced():
    src = sgf_with(COMMENT)
    out = ms.strip_sgf(src)
    for keep in ['GM[1]', 'SZ[19]', 'PC[BV1abc]', 'AB[dd]', ';B[pd]', 'AP[x:1]', ';W[dp])']:
        assert keep in out
    # every bracket pair is still closed: count unescaped [ and ]
    assert len(re.findall(r'(?<!\\)\[', out)) == len(re.findall(r'(?<!\\)\]', out))


def test_a_comment_without_teacher_section_is_identical():
    c = '【要点】只有要点\n【AI局部评估】只有 AI'
    assert ms.strip_sgf(sgf_with(c)) == sgf_with(c)


def test_a_plain_comment_without_headers_is_kept():
    assert ms.strip_sgf('(;C[plain note])') == '(;C[plain note])'

def test_only_the_c_property_is_changed():
    # a property whose name merely ends with C must not be rewritten
    s = "(;XC[【老师讲解 @0|0:01】abc])"
    assert ms.strip_sgf(s) == s




def lib_text(sgfs):
    lib = [{'id': 'a/%d' % i, 'name': 'n%d' % i, 'videos': [], 'sgf': s} for i, s in enumerate(sgfs)]
    return 'window.LIB=' + json.dumps(lib, ensure_ascii=False) + ";window.LIBT='11-01 00:00';"


def test_strip_library_round_trip_and_tail_kept():
    text, removed = ms.strip_library(lib_text([sgf_with(COMMENT), '(;GM[1])']))
    head, lib, tail = ms.load_library(text)
    assert head == 'window.LIB=' and tail == ";window.LIBT='11-01 00:00';"
    assert removed > 0 and '大家好' not in text and lib[1]['sgf'] == '(;GM[1])'
    assert '【要点】黑棋要先手' in lib[0]['sgf']


def fake_root(tmp_path, with_icons=True):
    r = tmp_path / 'src'
    (r / 'data').mkdir(parents=True)
    (r / 'icons').mkdir()
    for f in ms.SHELL_FILES:
        (r / f).write_text('<html><script src="a.js"></script><script>var x=1;</script></html>' if f == 'index.html' else '// ' + f, encoding='utf-8')
    for f in ms.ICONS:
        (r / 'icons' / f).write_bytes(b'\x89PNG')
    (r / 'data' / 'library.js').write_text(lib_text([sgf_with(COMMENT)]), encoding='utf-8')
    return r


def test_build_makes_the_folder_with_headers_robots_and_hash(tmp_path):
    out = tmp_path / 'site'
    removed = ms.build(out, False, root=fake_root(tmp_path))
    assert removed == 0
    names = {p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
    for need in ['index.html', 'sw.js', 'manifest.webmanifest', 'data/library.js', 'icons/icon-192.png', '_headers', 'robots.txt']:
        assert need in names
    assert '大家好' in (out / 'data' / 'library.js').read_text(encoding='utf-8')
    h = (out / '_headers').read_text(encoding='utf-8')
    digest = base64.b64encode(hashlib.sha256(b'var x=1;').digest()).decode()
    assert "'sha256-" + digest + "'" in h, 'the inline script is allowed by hash'
    assert "'unsafe-inline'" in h.split('style-src')[1].split(';')[0] and "script-src 'self' 'sha256-" in h
    assert 'Content-Security-Policy:' in h and 'Cache-Control: no-cache' in h and 'frame-ancestors' in h


def test_build_with_strip_removes_the_text_from_the_output_only(tmp_path):
    src = fake_root(tmp_path)
    before = (src / 'data' / 'library.js').read_text(encoding='utf-8')
    out = tmp_path / 'site'
    removed = ms.build(out, True, root=src)
    assert removed > 0
    assert '大家好' not in (out / 'data' / 'library.js').read_text(encoding='utf-8')
    assert (src / 'data' / 'library.js').read_text(encoding='utf-8') == before, 'the source library is never changed'
    assert 'removed' in (out / 'README.txt').read_text(encoding='utf-8')


def test_build_replaces_an_old_output_folder(tmp_path):
    out = tmp_path / 'site'
    out.mkdir()
    (out / 'stale.txt').write_text('x')
    ms.build(out, False, root=fake_root(tmp_path))
    assert not (out / 'stale.txt').exists()


def test_library_only_option(tmp_path, monkeypatch):
    real = ROOT / 'data' / 'library.js'
    if not real.exists():
        pytest.skip('no data/library.js in this checkout')
    target = tmp_path / 'lib.js'
    assert ms.main(['--library-only', str(target), '--strip-commentary']) == 0
    text = target.read_text(encoding='utf-8')
    assert text.startswith('window.LIB=') and ms.OMITTED in text or '【老师讲解' not in text


def test_real_library_has_no_teacher_text_left_after_strip():
    real = ROOT / 'data' / 'library.js'
    if not real.exists():
        pytest.skip('no data/library.js in this checkout')
    text, removed = ms.strip_library(real.read_text(encoding='utf-8'))
    _, lib, _ = ms.load_library(text)
    for c in lib:
        for sec in re.findall(r'【老师讲解[^】]*】([^【]*)', c['sgf']):
            assert sec.strip().rstrip('\n').replace('\n', '') .startswith(ms.OMITTED) or sec.strip() == ''
