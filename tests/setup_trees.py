"""Shared fixtures of the incident 12 tests (a position set up from stones analysed for the wrong side).

The trees and the fake engine are test fixtures, not real KataGo output.
"""
import os

import analyze2 as an
from wqutil import atomic_write_json


def node(i, par, mv=None, ch=(), setup=False, dead=False, pos=""):
    """One node of a saved tree (n.json). mv is [point index, colour] like build_tree writes it."""
    return {"id": i, "par": par, "mv": mv, "v": [[0.0, 1.0, 0]], "ch": list(ch), "dead": dead, "setup": setup, "n": 0, "pos": pos}


def tree():
    """0 empty board; 1 setup, the teacher plays White (2, 3); 4 setup, the teacher plays Black (5, 6); 7 setup, one White move
    (8); 9 setup, mixed (2 Black 1 White: 10, 11, 12); 13 setup whose only children are dead; 14 a setup with a White and a
    Black child, a tie (15, 16). Stones sit in the upper right corner so the region is a corner."""
    return [
        node(0, None, ch=[1, 4, 7, 9, 13, 14], pos=""),
        node(1, 0, ch=[2, 3], setup=True, pos="B69"),
        node(2, 1, mv=[106, "W"]), node(3, 1, mv=[87, "W"]),
        node(4, 0, ch=[5, 6], setup=True, pos="B69W106"),
        node(5, 4, mv=[87, "B"]), node(6, 4, mv=[88, "B"]),
        node(7, 0, ch=[8], setup=True, pos="B52"),
        node(8, 7, mv=[69, "W"]),
        node(9, 0, ch=[10, 11, 12], setup=True, pos="B52W104"),
        node(10, 9, mv=[69, "B"]), node(11, 9, mv=[70, "B"]), node(12, 9, mv=[87, "W"]),
        node(13, 0, ch=[17], setup=True, pos="B67"),
        node(14, 0, ch=[15, 16], setup=True, pos="B67W104"),
        node(15, 14, mv=[69, "W"]), node(16, 14, mv=[70, "B"]),
        node(17, 13, mv=[70, "B"], dead=True),
    ]


def run_analysis(tmp, N, name="toy-group", **env):
    nj = os.path.join(tmp, "g_%s.n.json" % name)
    out = os.path.join(tmp, "g_%s.a2.json" % name)
    atomic_write_json(nj, N)
    old = {k: os.environ.get(k) for k in env}
    os.environ.update({k: str(v) for k, v in env.items()})
    try:
        rc = an.main(["analyze2.py", nj, out, "220", "100"])
    finally:
        for k, v in old.items():
            os.environ.pop(k) if v is None else os.environ.__setitem__(k, v)
    return rc, out


def forget_initial_player(monkeypatch):
    """What the code did before the fix: the same request without initialPlayer."""
    real = an.query

    def old_query(*a, **k):
        r = real(*a, **k)
        r.pop("initialPlayer", None)
        return r

    monkeypatch.setattr(an, "query", old_query)
