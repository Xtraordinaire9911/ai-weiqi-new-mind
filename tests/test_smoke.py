"""Smoke tests: every pipeline script must at least compile."""
import glob
import os
import py_compile

from conftest import PIPELINE


def test_pipeline_scripts_compile(tmp_path):
    files = glob.glob(os.path.join(PIPELINE, "*.py"))
    assert files, "no pipeline scripts found"
    for i, f in enumerate(files):
        # cfile goes to tmp so the repo stays clean
        py_compile.compile(f, cfile=str(tmp_path / ("%d.pyc" % i)), doraise=True)
