"""Build a deployable static folder (default: site/) from the viewer files. It only copies and rewrites files, it never uploads anything.

Usage:
  python tools/make_site.py                          # site/ with everything
  python tools/make_site.py --strip-commentary       # also remove the teacher's spoken commentary text from the library
  python tools/make_site.py --library-only out.js --strip-commentary   # just write a stripped library file

What --strip-commentary removes: in every SGF comment (C property) the body of each section whose header starts with
"【老师讲解" (the teacher's words, transcribed from the videos). The header and its time link (@video|mm:ss) stay, so the viewer still
shows a "老师讲解" card with a link that jumps to that moment of the video. Key points (要点), AI evaluation, context notes and every
other section are kept as they are.

The output has the files the viewer needs plus _headers (Cloudflare Pages and Netlify), robots.txt and a short README.
Content Security Policy: the one inline script in index.html is allowed by its sha256 hash, so scripts need no 'unsafe-inline'.
"""
import argparse
import base64
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHELL_FILES = ['index.html', 'mobile.js', 'pwa.js', 'sw.js', 'engine_core.js', 'engine_net.js', 'engine_panel.js', 'quiz_core.js', 'quiz.js',
               'manifest.webmanifest']
ICONS = ['icon-192.png', 'icon-512.png', 'icon-maskable-512.png', 'apple-touch-icon.png']
TEACHER = '【老师讲解'
OMITTED = '(讲解文字已省略,点时间链接看视频)'


def _scan_value(s, i):
    """s[i] == '['. Return the index just after the matching ']' (in SGF a backslash escapes the next character)."""
    i += 1
    while i < len(s):
        if s[i] == '\\':
            i += 2
            continue
        if s[i] == ']':
            return i + 1
        i += 1
    return len(s)


def strip_comment(value):
    """value is the raw (still escaped) text between [ and ] of a C property. Sections start with 【 at the start of a line."""
    out = []
    for p in re.split(r'(?:(?<=\n)|^)(?=【)', value):
        if p.startswith(TEACHER):
            m = re.match(r'【[^】]*】', p)
            out.append((m.group(0) if m else TEACHER) + OMITTED + ('\n' if p.endswith('\n') else ''))
        else:
            out.append(p)
    return ''.join(out)


def strip_sgf(sgf):
    """Return the SGF with the teacher sections of every C[...] value removed. Other properties are copied byte for byte."""
    res, i, n = [], 0, len(sgf)
    while i < n:
        if sgf[i] != '[':
            res.append(sgf[i])
            i += 1
            continue
        j = _scan_value(sgf, i)
        k, ident = len(res) - 1, ''
        while k >= 0 and len(res[k]) == 1 and res[k].isalpha():  # the property name just before the bracket
            ident = res[k] + ident
            k -= 1
        body = sgf[i + 1:j - 1]
        res.append('[' + (strip_comment(body) if ident == 'C' else body) + ']')
        i = j
    return ''.join(res)


def load_library(text):
    m = re.match(r'^(window\.LIB=)(.*?)(;window\.LIBT=.*)$', text, re.S)
    if not m:
        raise ValueError('data/library.js does not look like window.LIB=[...];window.LIBT=...')
    return m.group(1), json.loads(m.group(2)), m.group(3)


def strip_library(text):
    head, lib, tail = load_library(text)
    removed = 0
    for c in lib:
        before = c.get('sgf', '')
        after = strip_sgf(before)
        removed += len(before) - len(after)
        c['sgf'] = after
    return head + json.dumps(lib, ensure_ascii=False, separators=(',', ':')) + tail, removed


def csp(index_html):
    hashes = []
    for m in re.finditer(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', index_html, re.S):
        hashes.append("'sha256-" + base64.b64encode(hashlib.sha256(m.group(1).encode('utf-8')).digest()).decode() + "'")
    return ("default-src 'self'; script-src 'self' " + ' '.join(hashes) + "; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self' https: http://127.0.0.1:* http://localhost:* http://[::1]:*; manifest-src 'self'; worker-src 'self'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def headers_text(index_html):
    return f"""# Cloudflare Pages and Netlify read this file as it is. Both use the same format.
/*
  Content-Security-Policy: {csp(index_html)}
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=()
  X-Robots-Tag: noindex, nofollow
  Cross-Origin-Opener-Policy: same-origin

/index.html
  Cache-Control: no-cache

/sw.js
  Cache-Control: no-cache

/manifest.webmanifest
  Content-Type: application/manifest+json
  Cache-Control: no-cache

/data/library.js
  Cache-Control: public, max-age=0, must-revalidate

/icons/*
  Cache-Control: public, max-age=31536000, immutable
"""


def build(out, strip, root=ROOT):
    if out.exists():
        shutil.rmtree(out)
    (out / 'data').mkdir(parents=True)
    (out / 'icons').mkdir()
    for f in SHELL_FILES:
        shutil.copyfile(root / f, out / f)
    for f in ICONS:
        shutil.copyfile(root / 'icons' / f, out / 'icons' / f)
    lib_text = (root / 'data' / 'library.js').read_text(encoding='utf-8')
    removed = 0
    if strip:
        lib_text, removed = strip_library(lib_text)
    (out / 'data' / 'library.js').write_text(lib_text, encoding='utf-8')
    index = (out / 'index.html').read_bytes().decode('utf-8')  # bytes as served: the hash must see the same line endings
    (out / '_headers').write_text(headers_text(index), encoding='utf-8')
    (out / 'robots.txt').write_text('User-agent: *\nDisallow: /\n', encoding='utf-8')
    note = 'The library in this folder has the teacher commentary text removed.\n' if strip else ''
    (out / 'README.txt').write_text('Static site built by tools/make_site.py. Upload this folder as it is. See docs/MOBILE-AND-HOSTING.md.\n' + note,
                                    encoding='utf-8')
    return removed


def main(argv=None):
    ap = argparse.ArgumentParser(description='Build a deployable static folder from the viewer files (nothing is uploaded).')
    ap.add_argument('--out', default=str(ROOT / 'site'), help='output folder (deleted and recreated)')
    ap.add_argument('--strip-commentary', action='store_true', help="remove the teacher's spoken commentary text")
    ap.add_argument('--library-only', metavar='FILE', help='only write the (stripped) library to FILE and stop')
    a = ap.parse_args(argv)
    if a.library_only:
        text = (ROOT / 'data' / 'library.js').read_text(encoding='utf-8')
        removed = 0
        if a.strip_commentary:
            text, removed = strip_library(text)
        Path(a.library_only).write_text(text, encoding='utf-8')
        print('wrote %s (%d characters of commentary removed)' % (a.library_only, removed))
        return 0
    removed = build(Path(a.out), a.strip_commentary)
    print('built %s (%d characters of commentary removed)' % (a.out, removed))
    return 0


if __name__ == '__main__':
    sys.exit(main())
