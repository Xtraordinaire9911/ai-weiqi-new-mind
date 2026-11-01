#!/usr/bin/env python3
"""Check that bilingual text is written Chinese first, then English.

The rule of this repository: every bilingual text goes Chinese first, English
second. A Chinese paragraph comes first and its English counterpart sits
directly below it. Headings, table cells and pull request titles read
"中文 / English". This script finds text that breaks the rule. It only reads, it
never edits. Standard library only.

Usage:
    python tools/check_bilingual.py                      # the default document set of the repo
    python tools/check_bilingual.py docs/WORKFLOW.md     # some files
    python tools/check_bilingual.py pr-body.md           # a stand alone pull request body
    python tools/check_bilingual.py --pr 12              # title and body of a pull request (needs gh)
    python tools/check_bilingual.py --pr-json prs.json   # the JSON printed by gh pr view/list
    python tools/check_bilingual.py --title "Add x / 添加 x"
    python tools/check_bilingual.py --fix-suggest FILE   # also print what to swap, edits nothing

Exit code: 0 no problem, 1 at least one problem, 2 an input could not be read.

Run the tests in Docker (no venv, nothing is installed on the host):
    docker run --rm -v "$PWD":/app -w /app python:3.12-slim sh -c "pip install -q --root-user-action=ignore pytest && python -m pytest -q tests/test_check_bilingual.py"
In Git Bash on Windows put MSYS_NO_PATHCONV=1 in front of docker so that /app is not rewritten.

What it checks (these rule names show up in the output):
    order/paragraph  an English paragraph directly followed by its Chinese paragraph
    order/list       an English list item directly followed by its Chinese item
    order/grouped    all Chinese items first, then all English ones, instead of pairs
    order/heading    "What changed / 改动内容" instead of "改动内容 / What changed"
    order/cell       the same inside a table cell
    order/title      the same in a pull request title
    order/inline     the same in a short line or list item
    order/yaml       the same in a value of an issue form
    missing/*        an English only paragraph, item, heading, cell or title

Fenced code, inline code, URLs, HTML comments and paths are ignored. Wrap a
region in <!-- bilingual-check: off --> and <!-- bilingual-check: on --> to
skip it, or put <!-- bilingual-check: skip-file --> anywhere to skip a file.

How a text is classified: the share of Han characters among Han characters plus
Latin letters. At least 0.30 is Chinese. Below 0.05 with enough words is English.
Up to 0.20 with five or more words still counts as English, because English
text often quotes Chinese names. Anything in between is "mixed" and is only
used as a neighbour, never reported. In a short "A / B" text the sides are
judged against each other, so a Chinese part that is mostly a product name
still counts as the Chinese part.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set, Tuple

# ---------------------------------------------------------------------------
# Configuration. Edit here or use the command line options.
# ---------------------------------------------------------------------------

# Files checked when no file is named on the command line (paths relative to the root).
# "*" does not cross a slash, "**" does.
DEFAULT_PATTERNS = [
    "README.md",
    "CONTRIBUTING.md",
    "NOTICE.md",
    "CHANGELOG.md",
    "docs/*.md",
    "remote/README.md",
    ".github/*.md",
    ".github/ISSUE_TEMPLATE/*.md",
    ".github/ISSUE_TEMPLATE/*.yml",
    ".github/ISSUE_TEMPLATE/*.yaml",
    ".github/PULL_REQUEST_TEMPLATE/*.md",
]

# Files that are English only on purpose. A pattern without a slash is matched
# against the file name, a pattern with a slash against the path.
DEFAULT_EXEMPT = [
    "LICENSE",
    "LICENSE.*",
    "LICENSE-*.txt",
    "COPYING*",
    ".gitmessage",
]

ZH_MIN = 0.30        # share of Han characters from which a text counts as Chinese
EN_MAX = 0.05        # below this share a text counts as English
EN_SOFT_MAX = 0.20   # up to this share it is still English if it has enough words ...
EN_SOFT_WORDS = 5    # ... at least this many
MIN_WORDS_PARAGRAPH = 3
MIN_WORDS_CELL = 2
MIN_WORDS_SHORT = 1  # headings, titles, table header cells

# YAML keys whose values are not human text.
YAML_SKIP_KEYS = {
    "id", "type", "url", "labels", "assignees", "blank_issues_enabled", "required",
    "default", "multiple", "validations", "options_default", "projects", "visibility",
}

# ---------------------------------------------------------------------------
# Text classification
# ---------------------------------------------------------------------------

ZH, EN, MIXED, NONE = "zh", "en", "mixed", "none"


def _range(*pairs):
    return "".join(chr(a) + "-" + chr(b) for a, b in pairs)


# Han characters (the CJK ideograph blocks, compatibility ideographs and the extension planes).
_HAN = _range((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x2FA1F))
_LATIN = "A-Za-z" + _range((0x00C0, 0x024F))
CJK_RE = re.compile("[" + _HAN + "]")
LATIN_RE = re.compile("[" + _LATIN + "]")
WORD_RE = re.compile("[" + _LATIN + "]{3,}")
MASK = chr(0xE000)  # private use character that replaces masked text

_CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.S)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_TARGET = re.compile(r"(?<=\])\([^)]*\)")
_AUTOLINK = re.compile(r"<(?:https?|ftp|mailto):[^>\s]*>", re.I)
# URLs and domains are ASCII only, so Chinese text glued to a URL is not swallowed.
_URL = re.compile(r"(?:https?|ftp)://[A-Za-z0-9._~:/?#@!$&'*+,;=%\-\[(]+|www\.[A-Za-z0-9._~:/?#@!$&'*+,;=%\-]+", re.I)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_DOMAIN = re.compile(
    r"(?<![A-Za-z0-9_@.-])(?:[A-Za-z0-9-]+\.)+(?:com|org|net|io|ai|dev|co|de|cn|edu|gov|app|me|info|so|tv)\b", re.I)
_HTML_TAG = re.compile(r"</?(?!br\b)[A-Za-z][^<>]*>", re.I)
_ENTITY = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z]+);")
_PATH = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z0-9_.~-]*(?:/[A-Za-z0-9_.<>{}*~-]+)+/?")
_FILE = re.compile(
    r"(?<![A-Za-z0-9_])[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\."
    r"(?:md|py|json|js|ps1|yml|yaml|sh|txt|html|sgf|ipynb|cfg|bat|toml|ini|csv|png|jpg|gif|svg|pdf)\b"
)

# A separator between the two languages of one short text: " / ", a full width slash or <br>.
SEP_RE = re.compile(r"\s+/\s+|\s*" + chr(0xFF0F) + r"\s*|<br\s*/?>", re.I)


def mask_spans(text: str) -> str:
    """Blank out code, URLs, paths and tags, keeping every index unchanged."""
    def blank(m: "re.Match[str]") -> str:
        return MASK * len(m.group(0))

    for rx in (_CODE_SPAN, _IMAGE, _LINK_TARGET, _AUTOLINK, _URL, _EMAIL, _DOMAIN, _HTML_TAG,
               _ENTITY, _PATH, _FILE):
        text = rx.sub(blank, text)
    return text


@dataclass(frozen=True)
class Stat:
    cjk: int         # Han characters
    letters: int     # Latin letters
    words: int       # words of three or more letters, acronyms in capitals left out
    masked: float    # share of the text that is code, URLs or paths

    @property
    def share(self) -> float:
        total = self.cjk + self.letters
        return self.cjk / total if total else 0.0


def stat(text: str) -> Stat:
    masked = mask_spans(text)
    words = sum(1 for w in WORD_RE.findall(masked) if not w.isupper())
    ratio = masked.count(MASK) / max(1, len(masked.strip()))
    return Stat(len(CJK_RE.findall(masked)), len(LATIN_RE.findall(masked)), words, ratio)


def classify(text: str, min_words: int = MIN_WORDS_PARAGRAPH) -> str:
    """Return ZH, EN, MIXED or NONE (no letters, or too short to say)."""
    s = stat(text)
    if s.cjk + s.letters == 0:
        return NONE
    share = s.share
    if share >= ZH_MIN:
        return ZH
    if s.masked >= 0.5:
        return NONE  # mostly code or links, a reference line
    if s.cjk == 0 or share < EN_MAX:
        return EN if s.words >= min_words else NONE
    if share <= EN_SOFT_MAX and s.words >= max(min_words, EN_SOFT_WORDS):
        return EN
    return MIXED


def side_classes(parts: Sequence[str]) -> List[str]:
    """Classify the parts of one "A / B" text. Looser than classify(), because the pair gives context."""
    stats = [stat(p) for p in parts]
    base: List[str] = []
    for s in stats:
        if s.cjk + s.letters == 0:
            base.append(NONE)
        elif s.share >= ZH_MIN:
            base.append(ZH)
        elif s.words >= 1 and s.share <= EN_SOFT_MAX:
            base.append(EN)
        else:
            base.append(MIXED)
    out = list(base)
    for k, s in enumerate(stats):
        # Some Han characters in one part and none anywhere else: that part is the Chinese one,
        # even if it is mostly a product name or a license title.
        if base[k] in (EN, MIXED) and s.cjk > 0:
            others = [t for j, t in enumerate(stats) if j != k and t.cjk + t.letters > 0]
            if others and all(t.cjk == 0 for t in others):
                out[k] = ZH
    for k, s in enumerate(stats):
        # A mixed part next to a clearly Chinese part is the English one.
        if out[k] == MIXED and s.words >= 1:
            for j in (k - 1, k + 1):
                if 0 <= j < len(stats) and base[j] == ZH and stats[j].share >= 0.6 \
                        and stats[j].share - s.share >= 0.3:
                    out[k] = EN
    return out


def split_parts(raw: str) -> List[str]:
    """Split a short text at the language separators. Code and URLs never split."""
    masked = mask_spans(raw)
    parts: List[str] = []
    last = 0
    for m in SEP_RE.finditer(masked):
        parts.append(raw[last:m.start()])
        last = m.end()
    parts.append(raw[last:])
    return [p.strip() for p in parts]


_CONNECTORS = {"for", "of", "and", "the", "on", "in", "to", "with", "by", "a", "an", "at", "from", "as", "or"}


def looks_like_name(raw: str, title_case: bool) -> bool:
    """True for a lone link, an identifier or (with title_case) a product name such as "Hugging Face Jobs"."""
    text = raw.strip()
    if re.fullmatch(r"\[[^\]]*\]\([^)]*\)|(?:https?|ftp)://\S+", text):
        return True
    plain = _CODE_SPAN.sub(" ", text)
    plain = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", plain)
    plain = re.sub(r"[*_~]", "", plain)
    plain = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", plain)
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9.+_'-]*", plain)
    if not tokens:
        return True
    if len(tokens) == 1 and (re.search(r"[-_.]", tokens[0]) or re.search(r"[a-z][A-Z]", tokens[0])):
        return True
    if title_case and 2 <= len(tokens) <= 6:
        if all(t[0].isupper() or t[0].isdigit() or t.lower() in _CONNECTORS for t in tokens) \
                and any(t[0].isupper() for t in tokens):
            return True
    return False


def pair_status(raw: str, min_words: int, strict: bool = False, names: bool = False
                ) -> Tuple[str, List[str], int]:
    """Judge a short text such as a heading, a cell, a title or a one line "A / B" pair.

    Returns (status, parts, index). Status is "order" when parts[index] is English and
    parts[index+1] is Chinese, "ok" for a Chinese part followed by an English one,
    "missing" for English only text, "skip" for everything else. With strict=True both
    sides of a pair must be substantial (two English words, two Han characters), which
    keeps a stray "Kaggle / LRZ" inside a Chinese sentence from counting as a pair.
    """
    parts = split_parts(raw)
    if len(parts) >= 2:
        classes = side_classes(parts)
        stats = [stat(p) for p in parts]
        for k in range(len(parts) - 1):
            a, b = classes[k], classes[k + 1]
            if (a, b) not in ((EN, ZH), (ZH, EN)):
                continue
            en_stat, zh_stat = (stats[k], stats[k + 1]) if a == EN else (stats[k + 1], stats[k])
            if strict and not (en_stat.words >= 2 and zh_stat.cjk >= 2):
                continue
            return ("order" if a == EN else "ok"), parts, k
    if classify(raw, min_words) == EN and not looks_like_name(raw, names):
        return "missing", parts, -1
    return "skip", parts, -1


def snippet(text: str, width: int = 60) -> str:
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) > width:
        flat = flat[: width - 3].rstrip() + "..."
    return flat


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

@dataclass
class Problem:
    path: str
    line: int
    kind: str          # "order" or "missing"
    rule: str          # paragraph, list, heading, cell, title, inline, yaml
    reason: str
    suggestion: str = ""
    count: int = 1

    def format(self, with_suggestion: bool = False) -> str:
        out = "%s:%d: %s/%s: %s" % (self.path, self.line, self.kind, self.rule, self.reason)
        if with_suggestion and self.suggestion:
            out += "\n" + "\n".join("    suggest: " + s for s in self.suggestion.split("\n"))
        return out


@dataclass
class Report:
    path: str
    problems: List[Problem] = field(default_factory=list)
    skipped: str = ""

    def count(self, kind: str) -> int:
        return sum(p.count for p in self.problems if p.kind == kind)


def lines_label(start: int, end: int) -> str:
    return "line %d" % start if start == end else "lines %d-%d" % (start, end)


# ---------------------------------------------------------------------------
# Markdown parsing (a small subset of CommonMark, enough for these documents)
# ---------------------------------------------------------------------------

@dataclass
class Line:
    no: int
    text: str


@dataclass
class Item:
    start: int
    end: int
    blocks: List["Block"]


@dataclass
class Block:
    kind: str                       # para, heading, table, list, quote, code, html, rule
    start: int
    end: int
    lines: List[Line] = field(default_factory=list)       # para
    text: str = ""                                         # heading
    prefix: str = ""                                       # heading: the "## " marker
    rows: List[Tuple[int, List[str]]] = field(default_factory=list)  # table: (line, cells)
    items: List[Item] = field(default_factory=list)       # list
    children: List["Block"] = field(default_factory=list)  # quote


FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
HR = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
QUOTE = re.compile(r"^ {0,3}> ?")
LIST = re.compile(r"^( {0,3})([-+*]|\d{1,9}[.)])(?:( +)(.*)|$)")
TABLE_DELIM = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
BLOCK_TAGS = (
    "address|article|aside|blockquote|center|dd|details|dialog|div|dl|dt|fieldset|figcaption|"
    "figure|footer|form|h1|h2|h3|h4|h5|h6|header|hr|li|main|nav|ol|p|pre|section|summary|"
    "table|tbody|td|tfoot|th|thead|tr|ul"
)
HTML_BLOCK = re.compile(r"^ {0,3}</?(?:%s)(?:\s|/?>|$)" % BLOCK_TAGS, re.I)
DIRECTIVE = re.compile(r"bilingual-check:\s*(off|on|skip-file)", re.I)


def is_blank(s: str) -> bool:
    return not s.strip()


def indent_of(s: str) -> int:
    return len(s) - len(s.lstrip(" "))


def fence_open(s: str) -> Optional[str]:
    """The fence string if the line opens a fenced code block."""
    m = FENCE_OPEN.match(s)
    if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
        return m.group(1)
    return None


def starts_block(s: str) -> bool:
    """True if a line starts a block that may interrupt a paragraph."""
    if fence_open(s) or ATX.match(s) or HR.match(s) or QUOTE.match(s) or HTML_BLOCK.match(s):
        return True
    m = LIST.match(s)
    if m:
        marker, rest = m.group(2), m.group(4)
        if rest is None or not rest.strip():
            return False
        return marker[0] in "-+*" or marker.rstrip(".)") == "1"
    return False


def strip_comments(raw_lines: Sequence[str]) -> Tuple[List[str], bool]:
    """Blank HTML comments (outside fenced code) and regions switched off by a directive.

    Returns the cleaned lines and a skip-file flag.
    """
    out: List[str] = []
    in_comment = False
    in_fence = ""
    off = False
    skip_file = False
    for line in raw_lines:
        if not in_comment:
            fm = re.match(r"^\s*(`{3,}|~{3,})", line)
            if in_fence:
                # inside fenced code: only look for the closing fence
                if fm and fm.group(1)[0] == in_fence[0] and len(fm.group(1)) >= len(in_fence) \
                        and not line.strip().strip(fm.group(1)[0]):
                    in_fence = ""
                out.append("" if off else line)
                continue
            if fm:
                in_fence = fm.group(1)
                out.append("" if off else line)
                continue
        result: List[str] = []
        pos = 0
        while pos < len(line):
            if in_comment:
                end = line.find("-->", pos)
                if end < 0:
                    chunk, pos = line[pos:], len(line)
                else:
                    chunk, pos = line[pos:end + 3], end + 3
                    in_comment = False
                dm = DIRECTIVE.search(chunk)
                if dm:
                    word = dm.group(1).lower()
                    if word == "skip-file":
                        skip_file = True
                    else:
                        off = word == "off"
                result.append(" " * len(chunk))
            else:
                start = line.find("<!--", pos)
                if start < 0:
                    result.append(line[pos:])
                    break
                result.append(line[pos:start] + "    ")
                in_comment = True
                pos = start + 4
        out.append("" if off else "".join(result))
    return out, skip_file


def parse_blocks(lines: List[Line]) -> List[Block]:
    blocks: List[Block] = []
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        s = ln.text
        if is_blank(s):
            i += 1
            continue
        # indented code block
        if indent_of(s) >= 4:
            j = i
            last = i
            while j < n and (is_blank(lines[j].text) or indent_of(lines[j].text) >= 4):
                if not is_blank(lines[j].text):
                    last = j
                j += 1
            blocks.append(Block("code", ln.no, lines[last].no))
            i = last + 1
            continue
        # fenced code
        fence = fence_open(s)
        if fence:
            j = i + 1
            while j < n:
                cm = re.match(r"^ {0,3}(%s{%d,})[ \t]*$" % (re.escape(fence[0]), len(fence)), lines[j].text)
                if cm:
                    break
                j += 1
            end = min(j, n - 1)
            blocks.append(Block("code", ln.no, lines[end].no))
            i = j + 1
            continue
        # ATX heading
        m = ATX.match(s)
        if m:
            blocks.append(Block("heading", ln.no, ln.no, text=(m.group(2) or "").strip(),
                                prefix=m.group(1) + " "))
            i += 1
            continue
        if HR.match(s):
            blocks.append(Block("rule", ln.no, ln.no))
            i += 1
            continue
        # block quote
        if QUOTE.match(s):
            inner: List[Line] = []
            j = i
            prev_text = False
            while j < n:
                t = lines[j].text
                if QUOTE.match(t):
                    body = QUOTE.sub("", t, count=1)
                    inner.append(Line(lines[j].no, body))
                    prev_text = not is_blank(body)
                elif not is_blank(t) and prev_text and not starts_block(t):
                    inner.append(Line(lines[j].no, t))
                else:
                    break
                j += 1
            blocks.append(Block("quote", ln.no, lines[j - 1].no, children=parse_blocks(inner)))
            i = j
            continue
        # list
        if LIST.match(s):
            block, i = parse_list(lines, i)
            blocks.append(block)
            continue
        # html block
        if HTML_BLOCK.match(s):
            j = i
            while j < n and not is_blank(lines[j].text):
                j += 1
            blocks.append(Block("html", ln.no, lines[j - 1].no))
            i = j
            continue
        # table
        if "|" in s and i + 1 < n and "|" in lines[i + 1].text and TABLE_DELIM.match(lines[i + 1].text):
            rows = [(ln.no, split_row(s))]
            j = i + 2
            while j < n and not is_blank(lines[j].text) and "|" in lines[j].text \
                    and not starts_block(lines[j].text):
                rows.append((lines[j].no, split_row(lines[j].text)))
                j += 1
            blocks.append(Block("table", ln.no, lines[j - 1].no, rows=rows))
            i = j
            continue
        # paragraph (or setext heading)
        para = [ln]
        j = i + 1
        heading = False
        while j < n:
            t = lines[j].text
            if is_blank(t):
                break
            sm = SETEXT.match(t)
            if sm:
                heading = True
                j += 1
                break
            if starts_block(t):
                break
            if "|" in t and j + 1 < n and "|" in lines[j + 1].text and TABLE_DELIM.match(lines[j + 1].text):
                break
            para.append(lines[j])
            j += 1
        if heading:
            text = " ".join(p.text.strip() for p in para)
            blocks.append(Block("heading", para[0].no, para[-1].no, text=text))
        else:
            blocks.append(Block("para", para[0].no, para[-1].no, lines=para))
        i = j
    return blocks


def parse_list(lines: List[Line], i: int) -> Tuple[Block, int]:
    n = len(lines)
    first = LIST.match(lines[i].text)
    assert first is not None
    kind = first.group(2)[0] if first.group(2)[0] in "-+*" else first.group(2)[-1]
    items: List[Item] = []
    while i < n:
        m = LIST.match(lines[i].text)
        if not m:
            break
        k = m.group(2)[0] if m.group(2)[0] in "-+*" else m.group(2)[-1]
        if k != kind:
            break
        marker_width = len(m.group(1)) + len(m.group(2))
        spaces = len(m.group(3) or "")
        rest = m.group(4) or ""
        content_indent = marker_width + (spaces if 0 < spaces <= 4 and rest.strip() else 1)
        item_lines = [Line(lines[i].no, rest)]
        last_no = lines[i].no
        i += 1
        while i < n:
            t = lines[i].text
            if is_blank(t):
                j = i
                while j < n and is_blank(lines[j].text):
                    j += 1
                if j < n and indent_of(lines[j].text) >= content_indent:
                    for q in range(i, j):
                        item_lines.append(Line(lines[q].no, ""))
                    i = j
                    continue
                break
            if indent_of(t) >= content_indent:
                item_lines.append(Line(lines[i].no, t[content_indent:]))
                last_no = lines[i].no
                i += 1
                continue
            prev = item_lines[-1].text if item_lines else ""
            if not is_blank(prev) and not starts_block(t) and not LIST.match(t):
                item_lines.append(Line(lines[i].no, t.lstrip()))
                last_no = lines[i].no
                i += 1
                continue
            break
        items.append(Item(item_lines[0].no, last_no, parse_blocks(item_lines)))
        # does a sibling follow after blank lines?
        j = i
        while j < n and is_blank(lines[j].text):
            j += 1
        if j < n and LIST.match(lines[j].text) and indent_of(lines[j].text) < content_indent:
            sm = LIST.match(lines[j].text)
            assert sm is not None
            sk = sm.group(2)[0] if sm.group(2)[0] in "-+*" else sm.group(2)[-1]
            if sk == kind and not HR.match(lines[j].text):
                i = j
                continue
        break
    return Block("list", items[0].start, items[-1].end, items=items), i


def split_row(text: str) -> List[str]:
    s = text.strip()
    masked = _CODE_SPAN.sub(lambda m: MASK * len(m.group(0)), s)
    cells: List[str] = []
    last = 0
    for m in re.finditer(r"(?<!\\)\|", masked):
        cells.append(s[last:m.start()])
        last = m.end()
    cells.append(s[last:])
    if s.startswith("|") and cells:
        cells = cells[1:]
    if s.endswith("|") and not s.endswith("\\|") and cells:
        cells = cells[:-1]
    return [c.strip().replace("\\|", "|") for c in cells]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

@dataclass
class Unit:
    cls: str
    start: int
    end: int
    text: str
    kind: str            # "paragraph" or "list"
    container: str = "doc"


@dataclass
class Segment:
    start: int
    end: int
    text: str


class Context:
    def __init__(self, path: str):
        self.path = path
        self.problems: List[Problem] = []

    def add(self, line: int, kind: str, rule: str, reason: str, suggestion: str = "") -> None:
        self.problems.append(Problem(self.path, line, kind, rule, reason, suggestion))


def paragraph_segments(lines: Sequence[Line]) -> List[Segment]:
    """Split a paragraph at hard line breaks, but only if the pieces differ in language."""
    whole = Segment(lines[0].no, lines[-1].no, " ".join(ln.text.strip() for ln in lines))
    segs: List[Segment] = []
    cur: List[Tuple[int, str]] = []

    def close() -> None:
        texts = [t for _, t in cur if t]
        if texts:
            segs.append(Segment(cur[0][0], cur[-1][0], " ".join(texts)))
        cur.clear()

    for ln in lines:
        pieces = re.split(r"<br\s*/?>", ln.text, flags=re.I)
        for k, piece in enumerate(pieces):
            cur.append((ln.no, piece.strip()))
            if k < len(pieces) - 1:
                close()
        if ln.text.endswith("  ") or ln.text.rstrip().endswith("\\"):
            close()
    close()
    if len(segs) < 2:
        return [whole]
    classes = {classify(s.text) for s in segs}
    if ZH in classes and EN in classes:
        return segs
    return [whole]


def swap_text(parts: List[str], k: int) -> str:
    swapped = list(parts)
    swapped[k], swapped[k + 1] = swapped[k + 1], swapped[k]
    return " / ".join(swapped)


def check_short(ctx: Context, line: int, raw: str, rule: str, min_words: int,
                prefix: str = "", suffix: str = "") -> str:
    """Check one heading, cell or title. Returns the pair status."""
    status, parts, k = pair_status(raw, min_words)
    if status == "order":
        new = swap_text(parts, k)
        ctx.add(line, "order", rule,
                'English comes first: "%s"; write the Chinese first' % snippet(raw, 70),
                'replace with: %s%s%s' % (prefix, new, suffix))
    elif status == "missing":
        ctx.add(line, "missing", rule,
                'no Chinese in "%s"' % snippet(raw, 70),
                'write it as: %s<Chinese> / %s%s' % (prefix, raw.strip(), suffix))
    return status


def inline_pair(seg_text: str) -> Optional[Tuple[str, List[str], int]]:
    """A short line that holds an "A / B" pair of different languages."""
    if len(seg_text) > 400:
        return None
    status, parts, k = pair_status(seg_text, MIN_WORDS_SHORT, strict=True)
    if status in ("order", "ok"):
        return status, parts, k
    return None


BARRIER = object()  # stands for a self contained "A / B" line between two runs


def make_units(block: Block, ctx: Context, container: str) -> List[object]:
    """Units of one paragraph, with BARRIER for a line that holds its own "A / B" pair."""
    out: List[object] = []
    for seg in paragraph_segments(block.lines):
        pair = inline_pair(seg.text)
        if pair is not None:
            status, parts, k = pair
            if status == "order":
                ctx.add(seg.start, "order", "inline",
                        'English comes first: "%s"; write the Chinese first' % snippet(seg.text, 70),
                        "replace with: " + swap_text(parts, k))
            out.append(BARRIER)
            continue
        cls = classify(seg.text)
        if cls == NONE:
            continue
        out.append(Unit(cls, seg.start, seg.end, seg.text, "paragraph", container))
    return out


def pair_units(run: List[Unit], ctx: Context, report_lone: bool) -> None:
    """Pair the units of one run, left to right. Chinese then English is right."""
    lone_en: List[Unit] = []
    lone_zh: List[Unit] = []
    # Two or more Chinese units followed by two or more English ones (or the other way round)
    # are grouped by language instead of paired. Every English unit of such a block is reported.
    segments: List[Tuple[str, List[int]]] = []
    for idx, u in enumerate(run):
        if segments and segments[-1][0] == u.cls:
            segments[-1][1].append(idx)
        else:
            segments.append((u.cls, [idx]))
    grouped: Set[int] = set()
    for (cls_a, idx_a), (cls_b, idx_b) in zip(segments, segments[1:]):
        if {cls_a, cls_b} == {ZH, EN} and len(idx_a) >= 2 and len(idx_b) >= 2:
            grouped.update(idx_a if cls_a == EN else idx_b)
    if grouped:
        if report_lone:
            for idx in sorted(grouped):
                report_grouped(run[idx], ctx)
        run = [u for idx, u in enumerate(run) if idx not in grouped]
    i = 0
    n = len(run)
    # An English line at the start followed by correct pairs is a lone English line.
    if n >= 3 and n % 2 == 1 and all(u.cls == (EN if k % 2 == 0 else ZH) for k, u in enumerate(run)):
        lone_en.append(run[0])
        i = 1
    while i < n:
        u = run[i]
        nxt = run[i + 1] if i + 1 < n else None
        prev = run[i - 1] if i > 0 else None
        if u.cls == ZH:
            if nxt is not None and nxt.cls == EN:
                i += 2
            else:
                lone_zh.append(u)
                i += 1
            continue
        if u.cls != EN:
            i += 1
            continue
        if nxt is not None and nxt.cls == ZH:
            report_order(u, nxt, ctx)
            i += 2
            continue
        if (nxt is not None and nxt.cls == MIXED) or (prev is not None and prev.cls == MIXED):
            i += 1
            continue
        lone_en.append(u)
        i += 1
    if not report_lone:
        return
    for u in lone_en:
        if lone_zh:
            report_grouped(u, ctx)  # Chinese parts without English and English parts without Chinese
        else:
            report_missing(u, ctx)


def unit_noun(u: Unit) -> str:
    return "list item" if u.kind == "list" else "paragraph"


def report_order(en: Unit, zh: Unit, ctx: Context) -> None:
    noun = unit_noun(en)
    rule = "list" if en.kind == "list" else "paragraph"
    suggestion = "swap %s with %s" % (lines_label(en.start, en.end), lines_label(zh.start, zh.end))
    if en.kind == "list":
        suggestion += " (move the whole items)"
    elif en.container == "item":
        suggestion += " (keep the list marker on the first line)"
    ctx.add(en.start, "order", rule,
            'English %s (%s) comes before its Chinese %s (%s): "%s"'
            % (noun, lines_label(en.start, en.end), noun, lines_label(zh.start, zh.end), snippet(en.text)),
            suggestion)


def report_grouped(u: Unit, ctx: Context) -> None:
    noun = unit_noun(u)
    ctx.add(u.start, "order", "grouped",
            'English %s (%s) is not directly below its Chinese %s, the two languages are grouped in blocks: "%s"'
            % (noun, lines_label(u.start, u.end), noun, snippet(u.text)),
            "move it directly below the Chinese %s it translates" % noun)


def report_missing(u: Unit, ctx: Context) -> None:
    noun = unit_noun(u)
    rule = "list" if u.kind == "list" else "paragraph"
    ctx.add(u.start, "missing", rule,
            'English %s (%s) has no Chinese counterpart: "%s"' % (noun, lines_label(u.start, u.end), snippet(u.text)),
            "add the Chinese %s above %s" % (noun, lines_label(u.start, u.end)))


def analyze_blocks(blocks: List[Block], ctx: Context, report_lone: bool = True,
                   container: str = "doc") -> None:
    run: List[Unit] = []

    def flush() -> None:
        pair_units(run, ctx, report_lone)
        run.clear()

    for b in blocks:
        if b.kind == "para":
            for u in make_units(b, ctx, container):
                if u is BARRIER:
                    flush()
                elif isinstance(u, Unit):
                    run.append(u)
        elif b.kind == "code":
            continue
        elif b.kind == "heading":
            flush()
            check_short(ctx, b.start, b.text, "heading", MIN_WORDS_SHORT, prefix=b.prefix)
        elif b.kind == "table":
            flush()
            check_table(b, ctx)
        elif b.kind == "list":
            flush()
            analyze_list(b, ctx)
        elif b.kind == "quote":
            flush()
            analyze_blocks(b.children, ctx, report_lone, "quote")
        else:
            flush()
    flush()


def check_table(b: Block, ctx: Context) -> None:
    for idx, (line, cells) in enumerate(b.rows):
        min_words = MIN_WORDS_SHORT if idx == 0 else MIN_WORDS_CELL
        has_zh_cell = any(classify(c, 1) == ZH and pair_status(c, 1)[0] == "skip" for c in cells)
        for cell in cells:
            status, parts, k = pair_status(cell, min_words, names=True)
            if status == "order":
                ctx.add(line, "order", "cell",
                        'English comes first: "%s"; write the Chinese first' % snippet(cell, 70),
                        "replace the cell with: " + swap_text(parts, k))
            elif status == "missing" and not has_zh_cell:
                ctx.add(line, "missing", "cell", 'no Chinese in cell "%s"' % snippet(cell, 70),
                        "write the cell as: <Chinese> / %s" % cell.strip())


def item_info(item: Item) -> Tuple[str, bool]:
    """Class of a list item for the sibling pairing, and whether it is a real barrier."""
    classes: Set[str] = set()
    barrier = False
    for b in item.blocks:
        if b.kind == "para":
            for seg in paragraph_segments(b.lines):
                if inline_pair(seg.text) is not None:
                    barrier = True
                else:
                    classes.add(classify(seg.text))
        elif b.kind in ("table", "heading", "quote", "html"):
            barrier = True
    if barrier or (ZH in classes and EN in classes):
        return "BARRIER", True
    if MIXED in classes:
        return MIXED, False
    if ZH in classes:
        return ZH, False
    if EN in classes:
        return EN, False
    return NONE, False


def analyze_list(lst: Block, ctx: Context) -> None:
    run: List[Unit] = []

    def flush() -> None:
        pair_units(run, ctx, True)
        run.clear()

    for item in lst.items:
        cls, barrier = item_info(item)
        simple = cls in (ZH, EN, MIXED, NONE)
        analyze_blocks(item.blocks, ctx, report_lone=not simple, container="item")
        if barrier:
            flush()
            continue
        if cls == NONE:
            continue
        first = next((b for b in item.blocks if b.kind == "para"), None)
        text = " ".join(ln.text.strip() for ln in first.lines) if first else ""
        run.append(Unit(cls, item.start, item.end, text, "list"))
    flush()


def check_markdown(lines: List[Line], ctx: Context) -> None:
    analyze_blocks(parse_blocks(lines), ctx)


# ---------------------------------------------------------------------------
# YAML issue forms (light, line based)
# ---------------------------------------------------------------------------

YAML_KV = re.compile(r"^(\s*)(?:-\s+)?([A-Za-z_][\w-]*):(?:\s+(.*))?$")
YAML_ITEM = re.compile(r"^(\s*)-\s+(?!\w[\w-]*:\s)(.+)$")


def unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def check_yaml(lines: List[str], ctx: Context) -> None:
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        m = YAML_KV.match(line)
        if m:
            key, val = m.group(2), (m.group(3) or "").strip()
            if key in YAML_SKIP_KEYS:
                i += 1
                continue
            if re.match(r"^[|>][+-]?\d*$", val):
                base = len(m.group(1)) + (2 if re.match(r"^\s*-\s", line) else 0)
                j = i + 1
                block: List[Line] = []
                width = None
                while j < n and (is_blank(lines[j]) or indent_of(lines[j]) > base):
                    if width is None and not is_blank(lines[j]):
                        width = indent_of(lines[j])
                    block.append(Line(j + 1, lines[j][width:] if width and not is_blank(lines[j]) else ""))
                    j += 1
                check_markdown(block, ctx)
                i = j
                continue
            val = unquote(val)
            if val and not val.startswith(("[", "{", "&", "*")):
                check_short(ctx, i + 1, val, "yaml", MIN_WORDS_CELL)
            i += 1
            continue
        im = YAML_ITEM.match(line)
        if im:
            val = unquote(im.group(2))
            if val and not val.startswith(("[", "{")):
                check_short(ctx, i + 1, val, "yaml", MIN_WORDS_CELL)
        i += 1


# ---------------------------------------------------------------------------
# Entry points for one text
# ---------------------------------------------------------------------------

def finish(ctx: Context, doc_text: str) -> List[Problem]:
    """Sort the problems and fold the missing ones if the whole text has no Chinese."""
    problems = sorted(ctx.problems, key=lambda p: (p.line, p.kind))
    if not CJK_RE.search(mask_spans(doc_text)):
        missing = [p for p in problems if p.kind == "missing"]
        if len(missing) > 1:
            total = sum(p.count for p in missing)
            first = missing[0]
            folded = Problem(ctx.path, first.line, "missing", "document",
                             "no Chinese text at all in this document (%d English parts)" % total,
                             "write each English part as Chinese first, English second", count=total)
            problems = [p for p in problems if p.kind != "missing"] + [folded]
            problems.sort(key=lambda p: (p.line, p.kind))
    return problems


def check_text(text: str, path: str = "<text>", yaml: bool = False) -> Report:
    """Check a Markdown (or YAML form) text. Line numbers start at 1."""
    if text.startswith(chr(0xFEFF)):
        text = text[1:]
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cleaned, skip_file = strip_comments(raw_lines)
    if skip_file:
        return Report(path, [], skipped="skip-file directive")
    ctx = Context(path)
    if yaml:
        check_yaml([row.expandtabs(4) for row in cleaned], ctx)
    else:
        lines = [Line(k + 1, l.expandtabs(4)) for k, l in enumerate(cleaned)]
        # YAML front matter
        if lines and lines[0].text.strip() == "---":
            for k in range(1, len(lines)):
                if lines[k].text.strip() in ("---", "..."):
                    lines = lines[k + 1:]
                    break
        check_markdown(lines, ctx)
    return Report(path, finish(ctx, "\n".join(cleaned)))


def check_title(title: str, path: str = "<title>") -> Report:
    """Check a pull request title: it must read "中文标题 / English title"."""
    ctx = Context(path)
    title = title.strip()
    if title:
        check_short(ctx, 1, title, "title", MIN_WORDS_SHORT)
    return Report(path, ctx.problems)


# ---------------------------------------------------------------------------
# Files and the command line
# ---------------------------------------------------------------------------

def glob_to_regex(pattern: str) -> "re.Pattern[str]":
    out = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "*":
            if pattern[i:i + 2] == "**":
                out.append(".*")
                i += 2
                if pattern[i:i + 1] == "/":
                    i += 1
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def matches_any(rel: str, patterns: Iterable[str]) -> bool:
    name = rel.rsplit("/", 1)[-1]
    for pat in patterns:
        rx = glob_to_regex(pat)
        if rx.match(name if "/" not in pat else rel):
            return True
    return False


def default_files(root: Path, patterns: Sequence[str]) -> List[Path]:
    found: Set[Path] = set()
    for pat in patterns:
        rx = glob_to_regex(pat)
        head = pat.split("*", 1)[0]
        base = root / head.rsplit("/", 1)[0] if "/" in head else root
        if not base.is_dir():
            continue
        walker = base.rglob("*") if "**" in pat else base.glob("*")
        for p in walker:
            if p.is_file() and rx.match(p.relative_to(root).as_posix()):
                found.add(p)
    return sorted(found)


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace")


def load_exempt_file(path: str) -> List[str]:
    out = []
    for line in read_text(Path(path)).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def run_gh(args: Sequence[str]) -> str:
    proc = subprocess.run(["gh", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError("gh %s failed: %s" % (" ".join(args), proc.stderr.decode("utf-8", "replace").strip()))
    return proc.stdout.decode("utf-8", errors="replace")


def pr_reports(data: object, label: str) -> List[Report]:
    """Reports for a JSON object (one pull request) or a list of them."""
    items = data if isinstance(data, list) else [data]
    reports: List[Report] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        num = item.get("number")
        tag = "PR #%s" % num if num is not None else label
        reports.append(check_title(str(item.get("title") or ""), tag + " title"))
        reports.append(check_text(str(item.get("body") or ""), tag + " body"))
    return reports


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Check that bilingual text is written Chinese first, then English. Read only.")
    ap.add_argument("files", nargs="*", help="Markdown or pull request body files ('-' reads stdin); "
                                             "without any input the default document set is checked")
    ap.add_argument("--pr", type=int, action="append", default=[], metavar="N",
                    help="check the title and body of pull request N (runs gh pr view)")
    ap.add_argument("--pr-json", action="append", default=[], metavar="FILE",
                    help="check pull requests from JSON in the shape gh prints (an object or a list with title and body)")
    ap.add_argument("--repo", metavar="OWNER/REPO", help="repository for --pr (passed to gh -R)")
    ap.add_argument("--title", action="append", default=[], metavar="TEXT", help="check a pull request title")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent),
                    help="repository root for the default document set (default: the parent of tools/)")
    ap.add_argument("--include", action="append", default=[], metavar="GLOB",
                    help="add a pattern to the default document set")
    ap.add_argument("--exempt", action="append", default=[], metavar="GLOB",
                    help="skip files matching this pattern (added to the built in list)")
    ap.add_argument("--exempt-file", metavar="FILE", help="file with one exempt pattern per line")
    ap.add_argument("--fix-suggest", action="store_true",
                    help="print the lines to swap or the text to write; nothing is edited")
    return ap


def run(argv: Optional[Sequence[str]] = None, stdin: Optional[str] = None) -> int:
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        # Chinese text must survive a console with a legacy code page
        if (getattr(stream, "encoding", "") or "").lower().replace("-", "") != "utf8":
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            except (AttributeError, ValueError):
                pass
    exempt = list(DEFAULT_EXEMPT) + list(args.exempt)
    errors: List[str] = []
    if args.exempt_file:
        try:
            exempt += load_exempt_file(args.exempt_file)
        except OSError as exc:
            errors.append("cannot read %s: %s" % (args.exempt_file, exc))

    reports: List[Report] = []
    root = Path(args.root)
    explicit = bool(args.files or args.pr or args.pr_json or args.title)

    paths: List[Tuple[str, Optional[Path]]] = []
    for f in args.files:
        paths.append((f, None if f == "-" else Path(f)))
    if not explicit:
        for p in default_files(root, list(DEFAULT_PATTERNS) + list(args.include)):
            paths.append((p.relative_to(root).as_posix(), p))
    for label, path in paths:
        rel = label.replace("\\", "/")
        if matches_any(rel, exempt):
            reports.append(Report(label, [], skipped="exempt"))
            continue
        try:
            if path is None:
                text = stdin if stdin is not None else sys.stdin.buffer.read().decode("utf-8", "replace")
                label = "<stdin>"
            else:
                text = read_text(path)
        except OSError as exc:
            errors.append("cannot read %s: %s" % (label, exc))
            continue
        reports.append(check_text(text, label, yaml=label.lower().endswith((".yml", ".yaml"))))

    for title in args.title:
        reports.append(check_title(title))
    for num in args.pr:
        try:
            cmd = ["pr", "view", str(num), "--json", "title,body,number"]
            if args.repo:
                cmd += ["-R", args.repo]
            reports += pr_reports(json.loads(run_gh(cmd)), "PR #%d" % num)
        except (RuntimeError, OSError, ValueError) as exc:
            errors.append("pull request %d: %s" % (num, exc))
    for jf in args.pr_json:
        try:
            reports += pr_reports(json.loads(read_text(Path(jf))), jf)
        except (OSError, ValueError) as exc:
            errors.append("cannot read %s: %s" % (jf, exc))

    total_order = total_missing = 0
    for rep in reports:
        if rep.skipped:
            print("skip: %s (%s)" % (rep.path, rep.skipped), file=sys.stderr)
        for p in rep.problems:
            print(p.format(args.fix_suggest))
        total_order += rep.count("order")
        total_missing += rep.count("missing")
    checked = sum(1 for r in reports if not r.skipped)
    total = total_order + total_missing
    noun = "input" if checked == 1 else "inputs"
    if total:
        print("Checked %d %s: %d problems (%d order, %d missing translation)."
              % (checked, noun, total, total_order, total_missing))
    else:
        print("Checked %d %s: no problems." % (checked, noun))
    for e in errors:
        print("error: " + e, file=sys.stderr)
    if errors:
        return 2
    return 1 if total else 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
