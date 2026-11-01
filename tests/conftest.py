"""Shared pytest setup. The pipeline scripts are plain modules, so put pipeline/ on sys.path."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE = os.path.join(ROOT, "pipeline")
if PIPELINE not in sys.path:
    sys.path.insert(0, PIPELINE)
