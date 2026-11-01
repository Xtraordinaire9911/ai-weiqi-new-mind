#!/usr/bin/env python3
"""Local sanity checks for the repository. Standard library only, no GPU, no video, no KataGo.

Run it before you open a pull request:

    python tools/check_repo.py                     # run every check
    python tools/check_repo.py --only sgf,library  # run a few of them
    python tools/check_repo.py --list              # list the checks

Checks:
    html      files referenced by index.html exist, duplicate ids, inline script syntax (needs node)
    json      every *.json / *.ipynb file parses
    library   data/library.js parses and matches data/sgf/ exactly (rerun tools/build.ps1 after editing an SGF)
    sgf       parentheses and brackets balance, property syntax, coordinate range, board size
    python    *.py files compile (nothing is executed)
    files     no videos, weights, binaries or key files, no huge files, no names Windows cannot check out
    secrets   rough scan for common token and private key patterns (not a replacement for a real scanner)

Exit code 0 means no errors (warnings are possible), 1 means at least one error.
"""
from __future__ import annotations

import argparse
import ast
import bisect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
MAX_SHOWN_PER_FILE = 8

# Files that should not go into a public repository (copyright, licenses, size, safety).
FORBIDDEN_SUFFIXES = (
    ".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv",                      # video
    ".mp3", ".wav", ".m4a", ".flac", ".aac", ".opus",                     # audio
    ".bin.gz", ".onnx", ".pt", ".pth", ".ckpt", ".safetensors", ".gguf",  # network weights
    ".exe", ".dll", ".so", ".dylib",                                      # third party binaries
)
FORBIDDEN_NAMES = ("kaggle.json", ".env", "id_rsa", "id_ed25519", "credentials.json", "token.json")
FORBIDDEN_NAME_SUFFIXES = (".pem", ".p12", ".pfx")
WARN_SUFFIXES = (".zip", ".7z", ".rar", ".tar", ".gz")
WARN_SIZE = 5 * 1024 * 1024
ERR_SIZE = 20 * 1024 * 1024
WIN_ILLEGAL = re.compile(r'[<>:"|?*\x00-\x1f]')

SECRET_PATTERNS = [
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b"), "error"),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"), "error"),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "error"),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "error"),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"), "error"),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY"), "error"),
    ("Kaggle API key", re.compile(r'"key"\s*:\s*"[0-9a-f]{32}"'), "error"),
    ("hard coded password or token", re.compile(r"""(?i)\b(?:password|passwd|secret|token|api[_-]?key)\b\s*[:=]\s*['"][A-Za-z0-9_\-/+=]{20,}['"]"""), "warning"),
]
SKIP_SECRET_SCAN = ("data/library.js",)


class Report:
    def __init__(self) -> None:
        self.errors = 0
        self.warnings = 0

    def _emit(self, level: str, check: str, path: str | None, msg: str, hint: str | None, line: int | None) -> None:
        where = (path or "-") + (f":{line}" if line else "")
        print(f"{level} {where}: [{check}] {msg}" + (f" (fix: {hint})" if hint else ""))

    def error(self, check: str, path: str | None, msg: str, hint: str | None = None, line: int | None = None) -> None:
        self.errors += 1
        self._emit("ERROR", check, path, msg, hint, line)

    def warn(self, check: str, path: str | None, msg: str, hint: str | None = None, line: int | None = None) -> None:
        self.warnings += 1
        self._emit("WARNING", check, path, msg, hint, line)

    def info(self, check: str, msg: str) -> None:
        print(f"  [{check}] {msg}")


def list_files() -> list[Path]:
    """Tracked files plus untracked files that are not ignored, relative to ROOT. Falls back to a directory walk."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT, capture_output=True, check=True,
        ).stdout
        files = [Path(p.decode("utf-8")) for p in out.split(b"\0") if p]
    except (OSError, subprocess.CalledProcessError):
        files = []
        for dp, dns, fns in os.walk(ROOT):
            dns[:] = [d for d in dns if d not in (".git", "node_modules", "__pycache__")]
            for fn in fns:
                files.append((Path(dp) / fn).relative_to(ROOT))
    return sorted({f for f in files if (ROOT / f).is_file()})


def rel(p: Path) -> str:
    return p.as_posix()


def read_text(p: Path) -> str:
    return (ROOT / p).read_bytes().decode("utf-8-sig")


# ---- html --------------------------------------------------------------------------------
class _HtmlScan(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.refs: list[tuple[str, str, int]] = []
        self.ids: dict[str, list[int]] = defaultdict(list)
        self.inline: list[tuple[int, str]] = []
        self._buf: list[str] | None = None
        self._start = 0

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        line = self.getpos()[0]
        if a.get("id"):
            self.ids[a["id"]].append(line)
        if tag == "script":
            if a.get("src"):
                self.refs.append(("script src", a["src"], line))
            else:
                self._buf, self._start = [], line
        elif tag == "link" and a.get("href"):
            self.refs.append(("link href", a["href"], line))
        elif tag in ("img", "source", "video", "audio", "iframe", "embed") and a.get("src"):
            self.refs.append((f"{tag} src", a["src"], line))
        elif tag == "a" and a.get("href"):
            self.refs.append(("a href", a["href"], line))

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._buf is not None:
            self.inline.append((self._start, "".join(self._buf)))
            self._buf = None


def _is_external(ref: str) -> bool:
    return bool(re.match(r"^(?:[a-zA-Z][a-zA-Z0-9+.\-]*:|//|#)", ref)) or ref == ""


def check_html(rep: Report, files: list[Path]) -> None:
    htmls = [f for f in files if f.suffix.lower() == ".html" and f.parent == Path(".")]
    if not htmls:
        rep.error("html", "index.html", "no index.html in the repository root", "the viewer entry point lives in the root")
        return
    node = shutil.which("node")
    for f in htmls:
        path = rel(f)
        scan = _HtmlScan()
        try:
            scan.feed(read_text(f))
            scan.close()
        except Exception as e:  # noqa: BLE001
            rep.error("html", path, f"could not parse HTML: {e}")
            continue
        for kind, ref, line in scan.refs:
            if _is_external(ref):
                continue
            target = (ROOT / f.parent / unquote(re.split(r"[?#]", ref)[0])).resolve()
            try:
                target.relative_to(ROOT)
            except ValueError:
                rep.error("html", path, f'{kind}="{ref}" points outside the repository', "use a relative path inside the repo", line)
                continue
            if not target.exists():
                hint = "run tools/build.ps1 to create data/library.js" if ref.endswith("library.js") else "check the path and its letter case"
                rep.error("html", path, f'{kind}="{ref}" does not exist', hint, line)
        for i, lines in scan.ids.items():
            if len(lines) > 1:
                rep.warn("html", path, f'id="{i}" appears more than once (lines {", ".join(map(str, lines))})', "getElementById only returns the first one", lines[1])
        if node:
            for start, code in scan.inline:
                if not code.strip():
                    continue
                with tempfile.TemporaryDirectory() as td:
                    js = Path(td) / "inline.js"
                    js.write_text(code, encoding="utf-8")
                    # vm.Script only compiles, it never runs the code, and parses it like a browser classic script
                    r = subprocess.run(
                        [node, "-e", "const fs=require('fs');new (require('vm').Script)(fs.readFileSync(process.argv[1],'utf8'),{filename:'inline.js'})", str(js)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                    )
                if r.returncode != 0:
                    lines = [l for l in r.stderr.splitlines() if l.strip()]
                    m = re.search(r"inline\.js:(\d+)", r.stderr)
                    line = start + int(m.group(1)) - 1 if m else start
                    detail = next((l for l in lines if "Error" in l), lines[0] if lines else "unknown error")
                    rep.error("html", path, f"syntax error in inline script: {detail}", "the whole page breaks when a script does not parse", line)
        else:
            rep.warn("html", path, "node not found, inline script syntax was not checked", "safe to ignore if you do not have node installed")
        rep.info("html", f"{path}: {len(scan.refs)} references, {len(scan.inline)} inline scripts")


# ---- json --------------------------------------------------------------------------------
def check_json(rep: Report, files: list[Path]) -> None:
    n = 0
    for f in files:
        if f.suffix.lower() not in (".json", ".ipynb"):
            continue
        n += 1
        path = rel(f)
        try:
            data = json.loads(read_text(f))
        except UnicodeDecodeError as e:
            rep.error("json", path, f"not valid UTF-8: {e}", "save the file as UTF-8")
            continue
        except json.JSONDecodeError as e:
            rep.error("json", path, f"JSON syntax error: {e.msg} (line {e.lineno}, column {e.colno})", "usual causes are a trailing comma, single quotes or comments", e.lineno)
            continue
        if f.suffix.lower() == ".ipynb":
            if not isinstance(data, dict) or "cells" not in data or "nbformat" not in data:
                rep.error("json", path, "does not look like a notebook (missing cells or nbformat)")
                continue
            with_out = sum(1 for c in data["cells"] if c.get("cell_type") == "code" and c.get("outputs"))
            if with_out:
                rep.warn("json", path, f"{with_out} code cells still have output", "clear all outputs before committing so paths, tokens and personal details do not leak")
    rep.info("json", f"{n} JSON and notebook files parsed")


# ---- SGF ---------------------------------------------------------------------------------
POINT = re.compile(r"^(?:[a-s]{2}|tt)?$")
POINT_LIST_ITEM = re.compile(r"^[a-s]{2}(?::[a-s]{2})?$")
PROPS_MOVE = {"B", "W"}
PROPS_POINTS = {"AB", "AW", "AE", "TR", "SQ", "CR", "MA", "TB", "TW", "SL", "DD"}


def sgf_validate(text: str) -> tuple[list[tuple[int, str]], dict[str, str]]:
    errs: list[tuple[int, str]] = []
    root: dict[str, str] = {}
    nl = [m.start() for m in re.finditer("\n", text)]

    def line_of(pos: int) -> int:
        return bisect.bisect_left(nl, pos) + 1

    n = len(text)
    i = 0
    depth = 0
    in_node = False
    expect_node = False
    node_no = 0
    started = False
    while i < n:
        c = text[i]
        if c in " \t\r\n﻿":
            i += 1
            continue
        if c == "(":
            depth += 1
            started = True
            expect_node = True
            in_node = False
            i += 1
            continue
        if c == ")":
            if expect_node:
                errs.append((line_of(i), "')' with no node before it (empty branch)"))
            if depth == 0:
                errs.append((line_of(i), "extra ')' (parentheses do not match)"))
            else:
                depth -= 1
            expect_node = False
            in_node = False
            i += 1
            continue
        if c == ";":
            if depth == 0:
                errs.append((line_of(i), "node ';' outside the outermost parentheses"))
            in_node = True
            expect_node = False
            node_no += 1
            i += 1
            continue
        if c.isascii() and c.isalpha():
            j = i
            while j < n and text[j].isascii() and text[j].isalpha():
                j += 1
            ident = text[i:j]
            ident_line = line_of(i)
            if not in_node:
                errs.append((ident_line, f"property {ident} is not inside a node (missing ';' or parenthesis)"))
            elif ident != ident.upper():
                errs.append((ident_line, f"property name {ident} should be upper case (FF[4])"))
            k = j
            while k < n and text[k] in " \t\r\n":
                k += 1
            if k >= n or text[k] != "[":
                errs.append((ident_line, f"property {ident} has no [value]; a ']' inside a comment must be written as \\]"))
                i = j
                continue
            while k < n and text[k] == "[":
                start = k
                k += 1
                buf: list[str] = []
                closed = False
                while k < n:
                    ch = text[k]
                    if ch == "\\":
                        buf.append(text[k + 1:k + 2])
                        k += 2
                        continue
                    if ch == "]":
                        closed = True
                        break
                    buf.append(ch)
                    k += 1
                if not closed:
                    errs.append((line_of(start), f"the '[' of property {ident} has no closing ']'"))
                    return errs, root
                val = "".join(buf)
                k += 1
                vline = line_of(start)
                if ident in PROPS_MOVE and not POINT.match(val):
                    errs.append((vline, f"{ident}[{val[:12]}] is not a valid point (two letters a to s on a 19x19 board)"))
                elif ident in PROPS_POINTS and not POINT_LIST_ITEM.match(val):
                    errs.append((vline, f"{ident}[{val[:12]}] is not a valid point or point range"))
                elif ident == "LB" and not re.match(r"^[a-s]{2}:", val):
                    errs.append((vline, f"LB[{val[:12]}] should look like point:text"))
                if node_no == 1 and depth == 1 and ident not in root:
                    root[ident] = val
                m = k
                while m < n and text[m] in " \t\r\n":
                    m += 1
                if m < n and text[m] == "[":
                    k = m
            i = k
            continue
        errs.append((line_of(i), f"unexpected character {c!r} (probably an unescaped ']' or '\\' inside a comment)"))
        nxt = text.find("\n", i)  # skip to the next line to avoid a flood of follow-up errors
        i = n if nxt < 0 else nxt
    if not started:
        errs.append((1, "no SGF content (a file should start with '(;')"))
    if depth > 0:
        errs.append((line_of(n - 1), f"parentheses do not match: {depth} closing ')' missing"))
    return errs, root


# Older versions of tools/build.ps1 wrote placeholder files with an unescaped "C[]" in the text. Those files
# only get one summary warning until real content replaces them; any other problem is still an error.
SKELETON_DEFECT = "各节点C[]里"


def check_sgf(rep: Report, files: list[Path]) -> None:
    n = 0
    skeletons: list[str] = []
    for f in files:
        if f.suffix.lower() != ".sgf":
            continue
        n += 1
        path = rel(f)
        try:
            text = (ROOT / f).read_bytes().decode("utf-8")
        except UnicodeDecodeError as e:
            rep.error("sgf", path, f"not valid UTF-8 (byte {e.start})", "save as UTF-8 without BOM, the files declare CA[UTF-8]")
            continue
        if text.startswith("﻿"):
            rep.warn("sgf", path, "file starts with a BOM", "tools/build.ps1 writes UTF-8 without BOM and some SGF editors dislike a BOM")
        if "\x00" in text:
            rep.error("sgf", path, "contains a NUL character")
            continue
        errs, root = sgf_validate(text)
        if errs and SKELETON_DEFECT in text:
            errs2, root2 = sgf_validate(text.replace(SKELETON_DEFECT, "各节点C\\[\\]里"))
            if not errs2:
                skeletons.append(path)
                errs, root = [], root2
        for ln, msg in errs[:MAX_SHOWN_PER_FILE]:
            rep.error("sgf", path, msg, line=ln)
        if len(errs) > MAX_SHOWN_PER_FILE:
            rep.error("sgf", path, f"{len(errs) - MAX_SHOWN_PER_FILE} more syntax errors not shown")
        if errs:
            continue
        for key, want in (("SZ", "19"), ("GM", "1"), ("FF", "4"), ("CA", "UTF-8")):
            got = root.get(key)
            if got is None:
                rep.warn("sgf", path, f"root node has no {key}[{want}]", "use GM[1]FF[4]CA[UTF-8]SZ[19]")
            elif got.strip().upper() != want.upper():
                (rep.error if key == "SZ" else rep.warn)("sgf", path, f"root node has {key}[{got}], expected {key}[{want}]", "the viewer draws a 19x19 board" if key == "SZ" else None)
    if skeletons:
        rep.warn(
            "sgf", skeletons[0],
            f"{len(skeletons)} placeholder files contain an unescaped ']' from the old build.ps1 text (first one shown)",
            "harmless for filled groups and fixed for new placeholders; to clean up, delete the empty placeholders and rerun tools/build.ps1",
        )
    rep.info("sgf", f"{n} SGF files checked")


# ---- library.js --------------------------------------------------------------------------
LIB_RE = re.compile(r"^\s*window\.LIB\s*=\s*(\[.*\])\s*;\s*window\.LIBT\s*=\s*'([^']*)'\s*;\s*$", re.S)
BVID = re.compile(r"^BV[0-9A-Za-z]{10}$")


def _lf(s: str) -> str:
    """Compare with LF line endings: core.autocrlf=true on Windows turns checked out files into CRLF without changing them."""
    return s.replace("\r\n", "\n")


def check_library(rep: Report, files: list[Path]) -> None:
    lib = Path("data/library.js")
    if lib not in files:
        rep.error("library", rel(lib), "data/library.js is missing", "run: powershell -ExecutionPolicy Bypass -File tools/build.ps1")
        return
    m = LIB_RE.match(read_text(lib))
    if not m:
        rep.error("library", rel(lib), "format is not `window.LIB=[...];window.LIBT='...';`", "do not edit it by hand, rebuild it with tools/build.ps1")
        return
    try:
        entries = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        rep.error("library", rel(lib), f"window.LIB is not valid JSON: {e.msg} (character {e.pos})", "rebuild it with tools/build.ps1")
        return
    if not isinstance(entries, list) or not entries:
        rep.error("library", rel(lib), "window.LIB is empty or not an array")
        return
    on_disk = {f.as_posix()[len("data/sgf/"):-len(".sgf")]: f for f in files if f.as_posix().startswith("data/sgf/") and f.suffix.lower() == ".sgf"}
    seen: set[str] = set()
    stale = 0
    for idx, e in enumerate(entries):
        where = f"window.LIB[{idx}]"
        if not isinstance(e, dict):
            rep.error("library", rel(lib), f"{where} is not an object")
            continue
        missing = [k for k in ("id", "source", "series", "name", "videos", "sgf") if k not in e]
        if missing:
            rep.error("library", rel(lib), f"{where} is missing fields: {', '.join(missing)}", "rebuild it with tools/build.ps1")
            continue
        cid = e["id"]
        if cid in seen:
            rep.error("library", rel(lib), f"duplicate id: {cid}")
        seen.add(cid)
        if cid != f"{e['source']}/{e['series']}/{e['name']}":
            rep.error("library", rel(lib), f"{where} has an id that does not match source/series/name: {cid}")
        for v in e["videos"]:
            if not isinstance(v, dict) or not BVID.match(str(v.get("bvid", ""))):
                rep.error("library", rel(lib), f"{cid}: bad video id: {v!r}", "Bilibili ids look like BV1Y8411R7uM")
        src = on_disk.get(cid)
        if src is None:
            rep.error("library", rel(lib), f"{cid} is in library.js but data/sgf/{cid}.sgf does not exist", "rerun tools/build.ps1 after deleting an SGF")
        elif _lf(read_text(src)) != _lf(e["sgf"]):
            stale += 1
            rep.error("library", rel(src), "differs from the copy packed into data/library.js (library.js is out of date)", "rerun tools/build.ps1 and commit both")
    for cid, src in sorted(on_disk.items()):
        if cid not in seen:
            rep.error("library", rel(src), "is not packed into data/library.js", "rerun tools/build.ps1 after adding an SGF")
    rep.info("library", f"{len(entries)} groups, {stale} out of sync, data timestamp {m.group(2)}")


# ---- python ------------------------------------------------------------------------------
def check_python(rep: Report, files: list[Path]) -> None:
    n = 0
    for f in files:
        if f.suffix.lower() != ".py":
            continue
        n += 1
        try:
            ast.parse((ROOT / f).read_bytes(), filename=rel(f))
        except SyntaxError as e:
            rep.error("python", rel(f), f"syntax error: {e.msg}", "reproduce with: python -m py_compile <file>", e.lineno)
        except (UnicodeDecodeError, ValueError) as e:
            rep.error("python", rel(f), f"could not decode or parse: {e}")
    rep.info("python", f"{n} Python files checked")


# ---- files -------------------------------------------------------------------------------
def check_files(rep: Report, files: list[Path]) -> None:
    for f in files:
        p = rel(f)
        low = p.lower()
        name = f.name.lower()
        if low.endswith(FORBIDDEN_SUFFIXES) or name in FORBIDDEN_NAMES or low.endswith(FORBIDDEN_NAME_SUFFIXES):
            rep.error(
                "files", p, "this kind of file should not be committed to a public repository",
                "videos, weights and third party binaries carry copyright or license duties and keys can leak; add it to .gitignore and document how to download it",
            )
            continue
        if low.endswith(WARN_SUFFIXES):
            rep.warn("files", p, "archives and intermediate files usually do not belong in the repo", "if you really need it, explain why in the pull request")
        size = (ROOT / f).stat().st_size
        if size > ERR_SIZE:
            rep.error("files", p, f"file is too large ({size / 1048576:.1f} MiB, limit 20 MiB)", "GitHub rejects files over 100 MiB and big files slow down every clone; use a release attachment or external storage")
        elif size > WARN_SIZE:
            rep.warn("files", p, f"file is large ({size / 1048576:.1f} MiB)", "make sure it has to be in the repo")
        for part in f.parts:
            if WIN_ILLEGAL.search(part) or part.endswith((" ", ".")):
                rep.error("files", p, f"name contains characters Windows does not allow, or ends with a space or dot: {part!r}", "rename it; the Clean function in tools/build.ps1 strips these characters")
                break
    rep.info("files", f"{len(files)} files checked")


# ---- secrets -----------------------------------------------------------------------------
def check_secrets(rep: Report, files: list[Path]) -> None:
    scanned = 0
    for f in files:
        p = rel(f)
        if p in SKIP_SECRET_SCAN:
            continue
        full = ROOT / f
        if full.stat().st_size > 2 * 1024 * 1024:
            continue
        data = full.read_bytes()
        if b"\x00" in data[:4096]:
            continue
        text = data.decode("utf-8", errors="replace")
        scanned += 1
        for label, rx, level in SECRET_PATTERNS:
            for m in rx.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                shown = m.group(0)[:4] + "..." + f"({len(m.group(0))} characters)"
                msg = f"looks like a {label}: {shown}"
                hint = "revoke it on the provider side right away (deleting the file is not enough, history keeps it) and use environment variables or the platform secret store"
                (rep.error if level == "error" else rep.warn)("secrets", p, msg, hint, line)
                break
    rep.info("secrets", f"{scanned} text files scanned")


CHECKS = {
    "html": check_html,
    "json": check_json,
    "library": check_library,
    "sgf": check_sgf,
    "python": check_python,
    "files": check_files,
    "secrets": check_secrets,
}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # keep Chinese file names printable on Windows consoles
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="Local sanity checks (no GPU, no third party packages)")
    ap.add_argument("--only", help="comma separated list: " + ",".join(CHECKS))
    ap.add_argument("--list", action="store_true", help="list the checks and exit")
    args = ap.parse_args(argv)
    if args.list:
        for k in CHECKS:
            print(k)
        return 0

    wanted = [s.strip() for s in args.only.split(",")] if args.only else list(CHECKS)
    unknown = [w for w in wanted if w not in CHECKS]
    if unknown:
        ap.error(f"unknown check: {', '.join(unknown)}")

    rep = Report()
    files = list_files()
    print(f"repository root: {ROOT} ({len(wanted)} checks)")
    for name in wanted:
        print(f"== {name}")
        CHECKS[name](rep, files)
    print()
    print(f"result: {rep.errors} errors, {rep.warnings} warnings")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
