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
