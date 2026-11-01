"""Static rules over the pipeline sources, so a later edit cannot quietly undo the hardening."""
import ast
import glob
import os

import pytest

from conftest import PIPELINE

# mkfix.py is rewritten in a later commit of this branch.
LEGACY = {"mkfix.py"}


def _sources():
    for f in sorted(glob.glob(os.path.join(PIPELINE, "*.py"))):
        name = os.path.basename(f)
        with open(f, encoding="utf-8") as fh:
            yield name, ast.parse(fh.read(), filename=f)


def _open_mode(call):
    """Return the mode string of an open() call ('r' when not given)."""
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
        return str(call.args[1].value)
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return "r"


def _is_err_file(call):
    # KataGo's stderr dump (<out>.err) is a plain log, not data other stages read.
    a = call.args[0] if call.args else None
    return isinstance(a, ast.BinOp) and isinstance(a.right, ast.Constant) and a.right.value == ".err"


@pytest.mark.parametrize("name,tree", list(_sources()), ids=lambda v: v if isinstance(v, str) else "")
def test_outputs_are_written_atomically(name, tree):
    if name in LEGACY or name == "wqutil.py":
        pytest.skip("not covered")
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr == "dump" and getattr(f.value, "id", "") == "json":
            bad.append("json.dump at line %d" % node.lineno)
        if isinstance(f, ast.Name) and f.id == "open":
            mode = _open_mode(node)
            if ("w" in mode or "x" in mode) and not _is_err_file(node):
                bad.append("open(..., %r) at line %d" % (mode, node.lineno))
    assert not bad, "%s writes non-atomically, use wqutil.atomic_write_*: %s" % (name, bad)


@pytest.mark.parametrize("name,tree", list(_sources()), ids=lambda v: v if isinstance(v, str) else "")
def test_text_io_names_its_encoding(name, tree):
    """Incident: json read with the platform default (cp936) instead of utf-8."""
    if name in LEGACY:
        pytest.skip("not covered")
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        kws = {k.arg: k.value for k in node.keywords}
        if isinstance(f, ast.Name) and f.id == "open":
            if "b" not in _open_mode(node) and "encoding" not in kws:
                bad.append("open() without encoding at line %d" % node.lineno)
        name_ = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if name_ in ("run", "Popen", "check_output"):
            text = any(isinstance(kws.get(k), ast.Constant) and kws[k].value is True for k in ("text", "universal_newlines"))
            if text and "encoding" not in kws:
                bad.append("subprocess text mode without encoding at line %d" % node.lineno)
    assert not bad, "%s: %s" % (name, bad)


def test_powershell_scripts_with_non_ascii_have_a_bom():
    """Windows PowerShell 5.1 reads a BOM-less script as ANSI and garbles Chinese text."""
    tools = os.path.join(os.path.dirname(PIPELINE), "tools")
    bad = []
    for f in sorted(glob.glob(os.path.join(tools, "*.ps1"))):
        data = open(f, "rb").read()
        if any(b > 127 for b in data) and not data.startswith(b"\xef\xbb\xbf"):
            bad.append(os.path.basename(f))
    # sync_pipeline.ps1 has a Chinese comment and no BOM. tools/ is out of scope for this branch,
    # see docs/PREMORTEM.md. Any new offender fails the test.
    assert set(bad) <= {"sync_pipeline.ps1"}, "BOM missing: %s" % bad
