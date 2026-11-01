#!/usr/bin/env python3
"""Write a copy of the generated data with the teacher's spoken commentary removed.

The full data (with the teacher text) lives in the private data repository. The public repository should only ship the
stripped copy. This tool makes that copy. It never edits its input: the input folder is read only and the output goes to a
different folder that you name.

Usage:
  python tools/strip_commentary.py INPUT_ROOT OUTPUT_ROOT [--dry-run] [--check]

  INPUT_ROOT   a folder that holds data/sgf/... and data/library.js (the working clone or the private data clone)
  OUTPUT_ROOT  where the stripped copy is written (data/sgf/..., data/library.js); must not be the same folder or inside the input
  --dry-run    count what would be removed, write nothing
  --check      after writing, re-read the output and fail if any teacher text is left, or if library.js and the SGF files disagree

What is removed: in every SGF comment (C property) the body of each section whose header starts with 【老师讲解. The header and
its time link (@video|mm:ss) stay, and a short note replaces the body, so the viewer still shows a teacher card that links to
the moment in the video. Key points, the AI evaluation, context notes, video links and all other properties are kept byte for
byte. The same logic as `tools/make_site.py --strip-commentary` is used (it is imported from there, not copied).

Exit code: 0 ok, 1 a check failed, 2 bad arguments or unreadable input.
Standard library only.
"""
import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_site as ms  # noqa: E402  (strip_sgf, strip_library, TEACHER, OMITTED)


def _inside(child, parent):
    child, parent = Path(os.path.realpath(child)), Path(os.path.realpath(parent))
    return child == parent or parent in child.parents


def read_text(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:   # newline='' keeps the line endings as they are
        return f.read()


def write_text(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def teacher_text_left(sgf):
    """True when some teacher section still has text after its header (anything but the omission note)."""
    for m in re.finditer(r'(?:(?<=\n)|(?<=\[))' + re.escape(ms.TEACHER) + r'[^】]*】([^\n]*)', sgf):
        if not m.group(1).startswith(ms.OMITTED):
            return True
    return False


def run(src, out, dry=False, check=False, log=print):
    src, out = Path(src), Path(out)
    if not (src / 'data').is_dir():
        log(f'error: {src / "data"} not found')
        return 2
    if _inside(out, src) or _inside(src, out):
        log('error: the output folder must be a different folder, not the input and not inside it (or around it)')
        return 2
    files = sorted((src / 'data' / 'sgf').rglob('*.sgf')) if (src / 'data' / 'sgf').is_dir() else []
    lib = src / 'data' / 'library.js'
    removed_total = files_changed = 0
    for f in files:
        before = read_text(f)
        after = ms.strip_sgf(before)
        removed_total += len(before) - len(after)
        files_changed += before != after
        if not dry:
            write_text(out / f.relative_to(src), after)
    lib_removed = 0
    if lib.is_file():
        text = read_text(lib)
        new, lib_removed = ms.strip_library(text)
        if not dry:
            write_text(out / 'data' / 'library.js', new)
    log(f'{len(files)} SGF files read, {files_changed} changed, {removed_total} characters removed; '
        f'library.js: {lib_removed} characters removed' + (' (dry run, nothing written)' if dry else ''))
    if check and not dry:
        bad = [str(p) for p in sorted((out / 'data' / 'sgf').rglob('*.sgf')) if teacher_text_left(read_text(p))]
        olib = out / 'data' / 'library.js'
        if olib.is_file():
            head, items, tail = ms.load_library(read_text(olib))
            by_id = {c.get('id'): c.get('sgf', '') for c in items}
            for c in items:
                if teacher_text_left(c.get('sgf', '')):
                    bad.append(f'library.js: {c.get("id")}')
            for f in sorted((out / 'data' / 'sgf').rglob('*.sgf')):
                rid = f.relative_to(out / 'data' / 'sgf').as_posix()[:-4]
                if rid in by_id and by_id[rid] != read_text(f):
                    bad.append(f'library.js differs from its SGF: {rid}')
        if bad:
            log('check failed:')
            for b in bad:
                log('  ' + b)
            return 1
        log('check ok: no teacher text left, library.js matches the SGF files')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('input_root')
    ap.add_argument('output_root')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args(argv)
    try:
        return run(a.input_root, a.output_root, a.dry_run, a.check)
    except (OSError, ValueError) as e:
        print('error:', e, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
