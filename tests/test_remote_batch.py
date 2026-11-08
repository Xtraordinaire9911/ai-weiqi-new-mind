"""The cloud batch path (remote/): what the notebook produces must be accepted by the hardened pipeline as it is.

A fake engine (fake_katago.py) answers the json protocol, so no GPU, no model and no network are needed. The fake numbers are
made up and say nothing about Go. They only exercise the logic: fingerprint, side-to-move perspective, resume, ordering,
the notebook cells themselves.
"""
import json
import os
import re
import shlex
import stat
import subprocess
import sys
import time
import zipfile

import pytest

import analyze2 as an
import analyze_remote as ar
import make_notebook as mn
import pack_inputs as pk
import setup_katago as sk
import treesync as ts
from wqutil import atomic_write_json, read_json

HERE = os.path.dirname(os.path.abspath(__file__))
FAKE = os.path.join(HERE, "fake_katago.py")
ENGINE = "%s %s" % (shlex.quote(sys.executable), shlex.quote(FAKE))
SCRIPT = os.path.join(os.path.dirname(HERE), "remote", "analyze_remote.py")
posix_only = pytest.mark.skipif(os.name != "posix", reason="uses a shell wrapper around the fake engine")


@pytest.fixture(autouse=True)
def isolate():
    """analyze_remote sets environment variables and widens the engine's start wait: undo both after every test."""
    saved, orig, orig_query = dict(os.environ), an.Engine.get_for, an.query
    for k in [k for k in os.environ if k.startswith(("FAKE_", "WEIQI_"))]:
        del os.environ[k]
    yield
    os.environ.clear()
    os.environ.update(saved)
    an.Engine.get_for, an.query = orig, orig_query
    for obj, attr in ((an.Engine, "_wq_orig_get_for"), (an, "_wq_orig_query")):
        if hasattr(obj, attr):
            delattr(obj, attr)


def big_tree(depth=4, cols=(1, 10), rows=(2, 11), far=False, first="B"):
    """Synthetic tree with many branch points of both colours: a setup node, then a binary tree of alternating moves.

    far=True adds a stone far outside the lesson area, which makes analyze2 send a control query without it at every branch point.
    first is the colour of the teacher's first move after the setup, that is the side to move at the setup node.
    """
    K = lambda c, r: r * 18 + c
    N = []

    def add(par, mv, setup=False, pos=""):
        N.append({"id": len(N), "par": par, "mv": mv, "v": [[0.0, 1.0, 0]], "ch": [], "dead": False, "setup": setup, "n": 0, "pos": pos})
        if par is not None:
            N[par]["ch"].append(len(N) - 1)
        return len(N) - 1

    add(None, None)
    pos = "B%dW%d" % (K(3, 3), K(4, 3)) + ("W%d" % K(16, 17) if far else "")
    s = add(0, None, True, pos)
    free = iter([(c, r) for r in range(*rows) for c in range(*cols) if (c, r) not in ((3, 3), (4, 3))])

    def grow(par, colour, d, p):
        if d == 0:
            return
        for _ in range(2):
            c, r = next(free)
            q = p + colour + str(K(c, r))
            n = add(par, [K(c, r), colour], pos=q)
            grow(n, "W" if colour == "B" else "B", d - 1, q)

    grow(s, first, depth, pos)
    return N


def put_tree(folder, name, N):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(str(folder), "g_%s.n.json" % name)
    atomic_write_json(path, N)
    return path


def run(inp, out, *extra):
    return ar.main(["--in", str(inp), "--out", str(out), "--engine-cmd", ENGINE, "--window", "2"] + list(extra))


def strip_meta(A):
    A = dict(A)
    A.pop("_meta", None)
    return A


# ------------------------------------------------------------------ the output is accepted as it is

def test_cloud_output_is_accepted_by_the_pipeline_without_stamping(toy, capsys):
    """Same checks the local pipeline makes: fingerprint, schema, perspective, complete flag, then a real SGF build."""
    import wq
    nj = put_tree(toy.W, "toy-group", toy.N)
    assert run(nj, toy.W) == 0
    A = read_json(os.path.join(toy.W, "g_toy-group.a2.json"))
    meta = A["_meta"]
    assert meta["schema"] == ts.SCHEMA and meta["persp"] == "stm" and meta["complete"] is True
    assert meta["tree_fp"] == ts.tree_fingerprint(toy.N) and meta["report_as"] == "BLACK" and meta["report_as_source"] == "selftest"
    assert ts.check_analysis(toy.N, A) == ("ok", "")
    for k in ("1", "2"):   # the branch points of the toy tree
        scores = [m["s"] for m in A[k]["cand"] if not m.get("f")]
        assert scores == sorted(scores, reverse=True), "the first candidate is the best one for the side to move"
    forced = [m for k, a in A.items() if k != "_meta" for m in a["cand"] if m.get("f")]
    assert forced and all(m["v"] == 100 and m["p"] == -1 for m in forced), "the teacher's moves are evaluated by force with 100 visits"
    assert not ts.perspective_suspect(A)[0]
    capsys.readouterr()
    assert wq.main(["check", "toy-group", "--work", toy.W]) == 0
    assert "analysis: ok" in capsys.readouterr().out
    toy.o.stageB("toy-group", [1])   # orch2 would merge the file; it must not start its own analysis nor call it stale
    assert toy.o.sgfcheck.metrics(open(toy.sgf_file, encoding="utf-8").read())["an"] > 0, "the SGF carries the cloud analysis"
    side = read_json(os.path.join(toy.W, "g_toy-group.a2.meta.json"))
    assert side["queries_total"] > 0 and side["sec_per_query"] is not None and side["tree_fp"] == meta["tree_fp"]


def test_wrong_report_mode_is_caught_and_never_shipped(tmp_path):
    """An engine told it reports side to move while it reports Black: White nodes are upside down. The file must not travel back."""
    put_tree(tmp_path / "in", "big", big_tree(4))
    os.environ["WEIQI_REPORT_AS"] = "SIDETOMOVE"   # wrong on purpose, the fake engine reports BLACK
    assert run(tmp_path / "in", tmp_path / "out") == 1
    out = tmp_path / "out"
    assert not (out / "g_big.a2.json").exists() and (out / "g_big.a2.json.suspect").exists()
    assert read_json(str(out / "run_summary.json"))["groups"][0]["status"] == "suspect"


def test_phase_one_query_count_matches_the_package_numbers(tmp_path):
    """The numbers pack_inputs prints (branch points plus control queries) are what analyze2 really sends."""
    # 126 moves and one stone far away: the 3% to 97% region rule leaves that stone outside, so every branch point gets a control search
    N = big_tree(6, cols=(1, 12), rows=(2, 14), far=True)
    d = pk.describe(N)
    assert d["branch_nodes"] == 63 and d["queries_main"] == 126, "every branch point also gets a control search without the far stone"
    put_tree(tmp_path / "in", "far", N)
    log = tmp_path / "q.log"
    os.environ["FAKE_QUERY_LOG"] = str(log)
    assert run(tmp_path / "in", tmp_path / "out") == 0
    ids = [x for x in log.read_text(encoding="utf-8").split() if x != "selftest"]
    assert sum(1 for x in ids if not x.startswith("f")) == d["queries_main"]
    assert any(x.startswith("f") for x in ids), "phase 2 asked for the teacher's moves"


# ------------------------------------------------------------------ who plays first at a setup node

def test_side_to_move_rule():
    """Opposite of the last move on the path; at a setup node the colour the teacher plays next (majority, tie to B, dead ones ignored)."""
    N = big_tree(2, first="W")
    assert ar.side_to_move(N, 1, []) == "W", "setup node whose children are white moves"
    assert ar.side_to_move(N, 2, [2]) == "B", "after a white move"
    assert ar.side_to_move(N, 3, [2, 3]) == "W", "after a black move"
    assert ar.side_to_move(big_tree(2), 1, []) == "B"
    M = big_tree(2, first="W")
    M[M[1]["ch"][0]]["mv"][1] = "B"          # children W, B: tie
    assert ar.side_to_move(M, 1, []) == "B"
    M[1]["ch"].append(len(M))                # a third child, white: majority W
    M.append({"id": len(M), "par": 1, "mv": [7, "W"], "v": [], "ch": [], "dead": False, "setup": False, "n": 0, "pos": ""})
    assert ar.side_to_move(M, 1, []) == "W"
    M[-1]["dead"] = True                     # a dead child does not vote
    assert ar.side_to_move(M, 1, []) == "B"
    assert ar.side_to_move([{"id": 0, "par": None, "mv": None, "ch": [], "dead": False, "setup": True, "pos": "", "v": [], "n": 0}], 0, []) == "B", "no children: Black"


@pytest.mark.parametrize("first", ["W", "B"])
def test_a_setup_node_is_analysed_for_the_side_the_teacher_plays_next(tmp_path, first):
    """Incident: a request without moves carried no initialPlayer, KataGo assumed Black, and a position set up from stones where
    the teacher continues with White was analysed for the wrong side. The fake engine answers for the player it is told about."""
    N = big_tree(6, cols=(1, 12), rows=(2, 14), far=True, first=first)   # far stone: the setup node also gets its control query "1_0"
    put_tree(tmp_path / "in", "t", N)
    log = tmp_path / "req.log"
    os.environ["FAKE_REQUEST_LOG"] = str(log)
    assert run(tmp_path / "in", tmp_path / "out") == 0
    A = read_json(str(tmp_path / "out" / "g_t.a2.json"))
    assert A["1"]["turn"] == first and A["1_0"]["turn"] == first, "recorded turn = the colour the teacher plays next"
    for k, a in A.items():
        if re.fullmatch(r"\d+", k) and N[int(k)]["mv"]:
            assert a["turn"] != N[int(k)]["mv"][1], "nodes with moves: the opposite of the last mover, as before"
    reqs = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()]
    setup = [r for r in reqs if r["moves"] == 0]
    assert sorted(r["id"] for r in setup) == ["1", "1_0"] and all(r["initialPlayer"] == first for r in setup), "the request itself says who plays"
    assert all(r["initialPlayer"] is None for r in reqs if r["moves"] > 0), "requests with moves are unchanged"
    if first == "W":
        # the bug as it was: without the fix the same tree is analysed for Black at the setup node
        os.environ["WEIQI_KATAGO_CMD"] = json.dumps([sys.executable, FAKE])
        os.environ["WEIQI_WINDOW"] = "2"
        an.query = an._wq_orig_query   # undo the fix, as pipeline/analyze2.py in this branch still behaves
        assert an.analyze(N, str(tmp_path / "old.a2.json"), 220, 100) == 0
        assert read_json(str(tmp_path / "old.a2.json"))["1"]["turn"] == "B", "unpatched analyze2 analyses the white-to-move setup node for Black"


def test_the_fix_does_not_stack_and_yields_to_an_analyze2_that_sets_the_player():
    N = big_tree(2, first="W")
    R = an.region(N)
    ar.fix_initial_player()
    ar.fix_initial_player()
    assert an._wq_orig_query.__module__ == "analyze2", "wrapped once, not twice"
    assert an.query(N, R, [], 1, True, "1", 10)["initialPlayer"] == "W"
    an.query = an._wq_orig_query
    del an._wq_orig_query
    real = an.query
    an.query = lambda *a, **k: dict(real(*a, **k), initialPlayer="B")   # an analyze2 that already sets the player is left alone
    ar.fix_initial_player()
    assert an.query(N, R, [], 1, True, "1", 10)["initialPlayer"] == "B"


# ------------------------------------------------------------------ resume

def test_crashed_engine_then_rerun_asks_only_for_what_is_missing(tmp_path):
    put_tree(tmp_path / "in", "big", big_tree(4))
    out, log = tmp_path / "out", tmp_path / "q.log"
    os.environ.update(FAKE_CRASH_AFTER="3", FAKE_QUERY_LOG=str(log))
    assert run(tmp_path / "in", out) == 4, "an engine failure ends the batch with exit code 4"
    assert not (out / "g_big.a2.json").exists()
    saved = set(read_json(str(out / "g_big.a2.json.part"))["done"])
    assert saved, "answers received before the crash are kept"
    log.unlink()
    del os.environ["FAKE_CRASH_AFTER"]
    assert run(tmp_path / "in", out) == 0
    asked = log.read_text(encoding="utf-8").split()
    assert not (saved & set(asked)), "nothing that was answered before is asked again"
    ref = tmp_path / "ref"
    assert run(tmp_path / "in", ref) == 0
    assert strip_meta(read_json(str(out / "g_big.a2.json"))) == strip_meta(read_json(str(ref / "g_big.a2.json"))), "resumed run equals an uninterrupted run"
    assert not (out / "g_big.a2.json.part").exists()


def test_hard_killed_run_continues_from_its_checkpoint(tmp_path):
    """The process itself is killed (SIGKILL / Colab reset), not just the engine. The checkpoint is written atomically and is enough."""
    N = big_tree(6, cols=(1, 13), rows=(2, 14))
    put_tree(tmp_path / "in", "big", N)
    out, log = tmp_path / "out", tmp_path / "q.log"
    cmd = [sys.executable, SCRIPT, "--in", str(tmp_path / "in"), "--out", str(out), "--engine-cmd", ENGINE, "--window", "4"]
    p = subprocess.Popen(cmd, env=dict(os.environ, FAKE_DELAY="0.02", FAKE_QUERY_LOG=str(log)), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    part = out / "g_big.a2.json.part"
    try:
        deadline = time.time() + 60
        while time.time() < deadline and not (part.exists() and len(read_json(str(part), default={}).get("done", {})) >= 25):
            time.sleep(0.05)
        assert part.exists(), "the run never wrote a checkpoint"
    finally:
        p.kill()
        p.wait()
    time.sleep(0.5)   # the orphaned fake engine sees EOF and exits
    assert not (out / "g_big.a2.json").exists(), "killed before it finished"
    saved = set(read_json(str(part))["done"])
    log.unlink()
    r = subprocess.run(cmd, env=dict(os.environ, FAKE_QUERY_LOG=str(log)), capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert r.returncode == 0, r.stdout[-500:] + r.stderr[-500:]
    assert "resuming: %d results" % len(saved) in r.stdout + r.stderr
    assert not (saved & set(log.read_text(encoding="utf-8").split())), "the checkpointed answers were not asked again"
    A = read_json(str(out / "g_big.a2.json"))
    assert ts.check_analysis(N, A) == ("ok", "")


def test_valid_result_is_skipped_and_a_stale_one_is_replaced(tmp_path, capsys):
    N = big_tree(3)
    put_tree(tmp_path / "in", "big", N)
    out, log = tmp_path / "out", tmp_path / "q.log"
    os.environ["FAKE_QUERY_LOG"] = str(log)
    assert run(tmp_path / "in", out) == 0
    first = (out / "g_big.a2.json").read_bytes()
    n_asked = len(log.read_text(encoding="utf-8").split())
    capsys.readouterr()
    assert run(tmp_path / "in", out) == 0
    assert "skip (exists, valid)" in capsys.readouterr().out
    assert len(log.read_text(encoding="utf-8").split()) == n_asked, "the engine got no query for a valid group"
    assert (out / "g_big.a2.json").read_bytes() == first
    N2 = [dict(n, ch=list(n["ch"])) for n in N]   # the tree changed (a video was added to the group): the old result is stale
    N2.append({"id": len(N2), "par": 2, "mv": [17 * 18 + 17, "W"], "v": [[0.0, 1.0, 0]], "ch": [], "dead": False, "setup": False, "n": 0, "pos": ""})
    N2[2]["ch"].append(len(N2) - 1)
    put_tree(tmp_path / "in", "big", N2)
    assert run(tmp_path / "in", out) == 0
    assert (out / "g_big.a2.json.stale").read_bytes() == first, "the old file is kept for inspection, never reused"
    assert ts.check_analysis(N2, read_json(str(out / "g_big.a2.json"))) == ("ok", "")


# ------------------------------------------------------------------ packing and ordering

def test_manifest_sets_the_order_and_a_changed_tree_is_refused(tmp_path):
    work = tmp_path / "work"
    put_tree(work, "zz-last", big_tree(3))
    put_tree(work, "aa-first", big_tree(2))
    zp = str(tmp_path / "n_json_test.zip")
    m = pk.pack(str(work), ["zz-last", "aa-first"], zp)
    assert m["order"] == ["zz-last", "aa-first"]
    ind = tmp_path / "in"
    with zipfile.ZipFile(zp) as z:
        z.extractall(ind)
    assert sorted(os.listdir(ind)) == ["g_aa-first.n.json", "g_zz-last.n.json", "manifest.json"]
    assert run(ind, tmp_path / "out") == 0
    assert [g["group"] for g in read_json(str(tmp_path / "out" / "run_summary.json"))["groups"]] == ["g_zz-last", "g_aa-first"], "manifest order, not alphabetical"
    N = read_json(str(ind / "g_aa-first.n.json"))
    N.append(dict(N[-1], id=len(N), par=1, ch=[], mv=[17 * 18 + 17, "B"]))
    N[1]["ch"].append(len(N) - 1)
    atomic_write_json(str(ind / "g_aa-first.n.json"), N)
    assert run(ind, tmp_path / "out2") == 1
    assert not (tmp_path / "out2" / "g_aa-first.a2.json").exists(), "a tree that changed after packing is not analysed"
    assert (tmp_path / "out2" / "g_zz-last.a2.json").exists(), "the other group is not affected"


def test_pack_refuses_anything_that_could_carry_commentary(tmp_path):
    N = big_tree(2)
    work = tmp_path / "work"
    put_tree(work, "ok", N)
    pk.check_pure_tree(N)
    for bad in (dict(N[2], text="the teacher says this is the best move"), dict(N[2], pos="B1 and some words"), dict(N[2], mv=[5, "X"])):
        M = [dict(n) for n in N]
        M[2] = bad
        with pytest.raises(ValueError):
            pk.check_pure_tree(M)
    M = [dict(n) for n in N]
    M[2]["extra"] = "x"
    put_tree(work, "text", M)
    with pytest.raises(ValueError):
        pk.pack(str(work), ["ok", "text"], str(tmp_path / "x.zip"))
    assert not (tmp_path / "x.zip").exists()
    pk.pack(str(work), ["ok"], str(tmp_path / "ok.zip"))
    with zipfile.ZipFile(tmp_path / "ok.zip") as z:
        assert sorted(z.namelist()) == ["g_ok.n.json", "manifest.json"]
        assert z.read("g_ok.n.json") == (work / "g_ok.n.json").read_bytes(), "the tree goes in byte for byte"


def test_list_missing_and_skip_valid(tmp_path, capsys):
    work = tmp_path / "work"
    put_tree(work, "done", big_tree(3))
    put_tree(work, "todo", big_tree(2))
    assert run(work / "g_done.n.json", work) == 0
    capsys.readouterr()
    assert pk.main(["--work", str(work), "--list-missing"]) == 0
    out = capsys.readouterr().out
    assert "todo" in out and "done" not in out.replace("todo", "")
    assert pk.main(["--work", str(work), "--out", str(tmp_path / "p.zip"), "--skip-valid", "done", "todo"]) == 0
    with zipfile.ZipFile(tmp_path / "p.zip") as z:
        assert sorted(z.namelist()) == ["g_todo.n.json", "manifest.json"]


# ------------------------------------------------------------------ engine command and weights

def wrapper(tmp_path):
    """A 'katago' that answers `version` and otherwise runs the fake engine, remembering its arguments."""
    w = tmp_path / "katago"
    w.write_text('#!/bin/sh\nif [ "$1" = version ]; then echo "KataGo v0.0.0-test"; echo "Using FAKE backend"; exit 0; fi\n'
                 'echo "$@" >> "$WRAPPER_ARGS"\nexec "%s" "%s"\n' % (sys.executable, FAKE), encoding="utf-8")
    w.chmod(w.stat().st_mode | stat.S_IXUSR)
    return str(w)


@posix_only
def test_real_engine_command_cfg_and_weights_check(tmp_path):
    put_tree(tmp_path / "in", "big", big_tree(3))
    model = tmp_path / "net.bin.gz"
    model.write_bytes(b"not a real network")
    digest = ar.sha256_of(str(model))
    args_file = tmp_path / "args.txt"
    os.environ["WRAPPER_ARGS"] = str(args_file)
    base = ["--in", str(tmp_path / "in"), "--out", str(tmp_path / "out"), "--katago", wrapper(tmp_path), "--model", str(model), "--window", "2"]
    assert ar.main(base + ["--expect-sha256", "0" * 64]) == 2, "other weights: refuse before the engine starts"
    assert not args_file.exists()
    assert ar.main(base + ["--expect-sha256", digest]) == 0
    line = args_file.read_text(encoding="utf-8")
    assert "analysis -model %s -config" % model in line and "-override-config reportAnalysisWinratesAs=BLACK" in line
    cfg = (tmp_path / "out" / "katago_cfg" / "analysis.cfg").read_text(encoding="utf-8")
    for want in ("reportAnalysisWinratesAs = BLACK", "maxVisits = 500", "numAnalysisThreads = 2", "numSearchThreadsPerAnalysisThread = 16", "nnMaxBatchSize = 64", "nnRandomize = true"):
        assert want in cfg, "the cloud config keeps the local search settings: " + want
    side = read_json(str(tmp_path / "out" / "g_big.a2.meta.json"))
    assert side["model_sha256"] == digest and "KataGo v0.0.0-test" in side["katago"] and side["visits"] == 220 and side["forced_visits"] == 100


def test_slow_cold_start_needs_the_longer_wait(tmp_path):
    put_tree(tmp_path / "in", "big", big_tree(2))
    os.environ["FAKE_START_DELAY"] = "2"
    assert run(tmp_path / "in", tmp_path / "o1", "--start-timeout", "1") == 4, "no answer within the start wait: engine failure, nothing written"
    assert not (tmp_path / "o1" / "g_big.a2.json").exists()
    assert run(tmp_path / "in", tmp_path / "o2", "--start-timeout", "30") == 0


def test_katago_download_is_checked_against_the_published_checksum(tmp_path, monkeypatch, capsys):
    f = tmp_path / "katago-v1.18.2-cuda12.1-cudnn9.8.0-linux-x64.zip"
    f.write_bytes(b"swapped binary")
    assert sk.verify_zip(str(f), f.name) is False and not f.exists(), "a mismatch deletes the file"
    f.write_bytes(b"same bytes")
    monkeypatch.setitem(sk.KNOWN_SHA256, f.name, sk.sha256_file(str(f)))
    assert sk.verify_zip(str(f), f.name) is True and f.exists()
    assert sk.verify_zip(str(f), "katago-other-build.zip") is True, "an unknown build is reported as not verified, not blocked"
    assert "not verified" in capsys.readouterr().out
    assert all(len(v) == 64 for v in sk.KNOWN_SHA256.values())


# ------------------------------------------------------------------ the notebook

def notebook_cells():
    with open(os.path.join(os.path.dirname(mn.__file__), "katago_batch.ipynb"), encoding="utf-8") as f:
        return json.load(f)["cells"]


def src(cell):
    return "".join(cell["source"])


def test_notebook_is_current_and_its_code_is_valid():
    """Fails when a script was changed and make_notebook.py was not run again."""
    committed = {"cells": notebook_cells()}
    assert committed["cells"] == mn.build()["cells"], "katago_batch.ipynb is out of date: run python remote/make_notebook.py"
    written = []
    for c in committed["cells"]:
        if c["cell_type"] != "code":
            continue
        text = src(c)
        if text.startswith("%%writefile "):
            name, body = text.split("\n", 1)
            name = name.split(" ", 1)[1]
            written.append(name)
            folder = mn.PIPELINE if name in ("treesync.py", "wqutil.py", "analyze2.py") else os.path.dirname(mn.__file__)
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                assert body.rstrip("\n") == f.read().rstrip("\n"), "%s inside the notebook differs from the repository file" % name
        else:
            compile(text, "<cell %s>" % c["id"], "exec")
    assert written == ["treesync.py", "wqutil.py", "analyze2.py", "analyze_remote.py", "setup_katago.py"]
    assert mn.WEIGHTS_SHA256 in src(next(c for c in committed["cells"] if "EXPECTED_SHA256" in src(c)))


def test_notebook_stays_inside_the_batch_only_rules():
    """No tunnel, no server, no keep alive trick in anything the notebook runs (Colab and Kaggle terms)."""
    forbidden = ("ngrok", "cloudflared", "localtunnel", "colab_ssh", "serve_forever", "http.server", "setInterval", "keep_alive", "keepalive",
                 "socket.socket", "HTTPServer", "sshd", "remote_debugging")
    for c in notebook_cells():
        if c["cell_type"] == "code":
            low = src(c)
            assert not [w for w in forbidden if w in low], (c["id"], [w for w in forbidden if w in low])


@posix_only
def test_notebook_cells_run_end_to_end_with_the_fake_engine(tmp_path, monkeypatch):
    """The real cells, in order, on a machine without a GPU: a fake nvidia-smi, a fake network file and a fake KataGo.

    Only the KataGo download cell is replaced (it needs the internet). Everything else, including the scripts written by the
    %%writefile cells and run as separate processes exactly as in Colab, is the notebook as shipped."""
    monkeypatch.chdir(tmp_path)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    smi = bindir / "nvidia-smi"
    smi.write_text("#!/bin/sh\necho 'FAKE GPU for tests'\n", encoding="utf-8")
    smi.chmod(smi.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ["PATH"])
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: None)
    work = tmp_path / "w"
    put_tree(work, "g-one", big_tree(3, first="W"))
    put_tree(work, "g-two", big_tree(2))
    pk.pack(str(work), ["g-two"], str(tmp_path / "n_json_a.zip"))   # two packages: the notebook merges their manifests, in zip name order
    pk.pack(str(work), ["g-one"], str(tmp_path / "n_json_b.zip"))
    model = tmp_path / "kata1-fake.bin.gz"
    model.write_bytes(b"not a network")
    digest = ar.sha256_of(str(model))
    os.environ["WRAPPER_ARGS"] = str(tmp_path / "args.txt")
    cells = [c for c in notebook_cells() if c["cell_type"] == "code"]
    ns = {"__name__": "notebook"}
    for c in cells:
        text = src(c)
        if text.startswith("%%writefile "):
            name, body = text.split("\n", 1)
            (tmp_path / name.split(" ", 1)[1]).write_text(body + "\n", encoding="utf-8")
            continue
        if "setup_katago.py" in text and "ENV = json.load" in text:   # the download cell
            ns["ENV"] = {"katago": wrapper(tmp_path), "model": ns["MODEL"]}
            continue
        text = text.replace(mn.WEIGHTS_SHA256, digest)
        exec(compile(text, "<cell %s>" % c["id"], "exec"), ns)
    assert ns["MODEL"] == str(model) and [os.path.basename(f) for f in ns["inp"]] == ["g_g-one.n.json", "g_g-two.n.json"]
    out = tmp_path / "out"
    summary = read_json(str(out / "run_summary.json"))
    assert [g["group"] for g in summary["groups"]] == ["g_g-two", "g_g-one"] and all(g["status"] == "done" for g in summary["groups"]), "manifest order, all done"
    with zipfile.ZipFile(tmp_path / "a2_results.zip") as z:
        names = sorted(z.namelist())
        assert names == ["g_g-one.a2.json", "g_g-one.a2.meta.json", "g_g-two.a2.json", "g_g-two.a2.meta.json", "run_info.txt", "run_summary.json"]
        for g in ("g-one", "g-two"):
            A = json.loads(z.read("g_%s.a2.json" % g))
            N = read_json(str(work / ("g_%s.n.json" % g)))
            assert ts.check_analysis(N, A) == ("ok", ""), "what the notebook ships passes the pipeline's own check"
            assert A["_meta"]["persp"] == "stm" and A["_meta"]["report_as_source"] == "selftest"
        assert json.loads(z.read("g_g-one.a2.json"))["1"]["turn"] == "W", "the setup node whose children are white moves is analysed for White"
        assert "sha256 %s" % digest in z.read("run_info.txt").decode("utf-8")
    assert not list(out.glob("*.part")) and not list(out.glob("*.suspect"))
