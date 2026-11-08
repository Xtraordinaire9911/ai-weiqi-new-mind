#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cloud batch runner for the KataGo analysis of variation trees (Colab, Kaggle, Slurm nodes).

It does NOT carry a copy of the analysis logic any more. Every group is analysed by pipeline/analyze2.py, the same
module the local pipeline runs, so the result is the same kind of file by construction:
  * scores and winrates stored from the side to move (reportAnalysisWinratesAs=BLACK is converted in analyze2.convert),
    with a live perspective check against the engine;
  * region, branch points, 220 main visits, 100 forced visits for the teacher's moves, control search without outside stones;
  * a window of queries in flight (never everything at once, so the pipe cannot deadlock), a checkpoint (<out>.part) so a
    killed run resumes, a stall timeout so a silent engine ends the run with a message;
  * a "_meta" block with the tree fingerprint, schema, perspective and the complete flag, so wq.py check, treesync.check_analysis
    and orch2 accept the file as it is. No wq.py stamp is needed.
analyze2.py, treesync.py and wqutil.py are looked up next to this file (the notebook writes them there) or in ../pipeline.

Input : <in>/g_<name>.n.json (the tree the local pipeline wrote), optionally <in>/manifest.json from pack_inputs.py
        (processing order and the tree fingerprints, which are checked before anything is run)
Output: <out>/g_<name>.a2.json            the analysis, exactly what analyze2.py writes
        <out>/g_<name>.a2.meta.json       side note for humans: seconds, queries, seconds per query, KataGo version, weights hash
        <out>/run_summary.json            one entry per group of this run

Usage:
  python analyze_remote.py --in ./in --out ./out --katago ./katago --model ./model.bin.gz [--expect-sha256 HASH]
A group that already has a valid a2.json is skipped, a killed run continues from its checkpoint, --force recomputes.
Exit code: 0 all groups fine, 1 a group failed or needs a look, 2 bad input, 4 engine failed (re-run to continue), 5 engine missing.
"""
import argparse
import glob
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def _pipeline_dir():
    """Where analyze2.py, treesync.py and wqutil.py live: next to this file (notebook) or in the repo's pipeline/ folder."""
    for d in (HERE, os.path.join(os.path.dirname(HERE), 'pipeline')):
        if all(os.path.exists(os.path.join(d, f)) for f in ('analyze2.py', 'treesync.py', 'wqutil.py')):
            return d
    sys.exit('analyze2.py, treesync.py and wqutil.py not found next to %s or in ../pipeline' % __file__)


sys.path.insert(0, _pipeline_dir())
import analyze2 as an  # noqa: E402
import treesync as ts  # noqa: E402
from wqutil import atomic_write_json, read_json, setup_stdio  # noqa: E402

TREE_KEYS = ('id', 'par', 'mv', 'ch', 'dead', 'setup', 'pos')

# Same parameters as the local analysis.cfg (checked against it); only the log directory differs.
CFG = """# Written by analyze_remote.py; the search parameters match the local analysis.cfg, only the log directory differs
logDir = {logdir}
reportAnalysisWinratesAs = BLACK
maxVisits = 500
numAnalysisThreads = {nat}
numSearchThreadsPerAnalysisThread = {nst}
nnMaxBatchSize = {bs}
nnCacheSizePowerOfTwo = 23
nnMutexPoolSizePowerOfTwo = 17
nnRandomize = true
"""


# ---------------------------------------------------------------- input checks

def validate_tree(N):
    """Raise ValueError with a plain message when N is not a tree analyze2 can use (fingerprint and indexing need these fields)."""
    if not isinstance(N, list) or not N or not all(isinstance(n, dict) for n in N):
        raise ValueError('not a list of nodes')
    for k, n in enumerate(N):
        missing = [f for f in TREE_KEYS if f not in n]
        if missing:
            raise ValueError('node %d lacks %s' % (k, ', '.join(missing)))
        if n['id'] != k:
            raise ValueError('node at position %d has id %r (analyze2 indexes the list by id)' % (k, n['id']))


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def engine_version(katago):
    """First lines of `katago version` (prints text only, does not load a network), or ''."""
    try:
        r = subprocess.run([katago, 'version'], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
        return ' | '.join(x.strip() for x in r.stdout.splitlines()[:4] if x.strip())
    except (OSError, subprocess.SubprocessError):
        return ''


def widen_startup_wait(seconds):
    """analyze2 waits 120 s for the answer to its perspective self test, and that wait includes loading the network.

    A cold cloud GPU can need longer (CUDA kernels are compiled at start), so the wait is raised here instead of editing
    pipeline/analyze2.py, which must stay identical to the local copy. Calling it again replaces the earlier value."""
    orig = getattr(an.Engine, '_wq_orig_get_for', None) or an.Engine.get_for

    def get_for(self, qid, timeout):
        return orig(self, qid, seconds if qid == 'selftest' else timeout)

    an.Engine._wq_orig_get_for = orig
    an.Engine.get_for = get_for


def side_to_move(N, i, p):
    """'B' or 'W' for node i: the opposite of the last move on its path, else the colour the teacher plays next
    (majority of the live children, a tie goes to B), else 'B'. Same rule as the fix in the local analyze2.py."""
    if p:
        return 'W' if N[p[-1]]['mv'][1] == 'B' else 'B'
    cols = [N[c]['mv'][1] for c in an.live_children(N, i) if N[c]['mv']]
    return max(sorted(set(cols)), key=cols.count) if cols else 'B'


def fix_initial_player():
    """Bug fix: a request without moves carried no initialPlayer, so KataGo assumed Black and a position set up from stones
    where the teacher continues with White was analysed for the wrong side (the scores were then converted for Black too).

    The request is completed here, for requests without moves only, and only when analyze2 has not set the player itself,
    so this stays a no-op once pipeline/analyze2.query() does it. Requests that have moves are not touched. Calling it
    again does not stack the wrapper."""
    orig = getattr(an, '_wq_orig_query', None) or an.query

    def query(N, R, allow, i, ctx, qid, visits):
        req = orig(N, R, allow, i, ctx, qid, visits)
        if not req['moves'] and 'initialPlayer' not in req:
            req['initialPlayer'] = side_to_move(N, i, an.path_of(N, i)[1])
        return req

    an._wq_orig_query = orig
    an.query = query


def order_files(files, manifest):
    """Manifest order first (pack_inputs.py puts the groups the local run reaches last at the front), the rest by name."""
    names = (manifest or {}).get('order') or []
    rank = {'g_%s' % n: i for i, n in enumerate(names)}
    return sorted(files, key=lambda f: (rank.get(os.path.basename(f)[:-len('.n.json')], len(rank)), os.path.basename(f)))


# ---------------------------------------------------------------- one group

def entry_stats(A):
    """(branch nodes, forced evaluations, queries) of a finished analysis, for the side file."""
    meta = A.get('_meta') or {}
    forced = sum(1 for k, a in A.items() if k != '_meta' and isinstance(a, dict) for c in a.get('cand', []) if c.get('f'))
    nodes = sum(1 for k in A if re.fullmatch(r'\d+', k))
    return nodes, forced, meta.get('queries', 0)


def run_group(path, outp, a, info):
    """Analyse one tree. Returns (status, exit code to stop with or 0). Status: done, skipped, failed, suspect."""
    name = os.path.basename(path)[:-len('.n.json')]
    try:
        N = read_json(path)
        validate_tree(N)
    except (ValueError, OSError) as e:
        print('  ERROR %s: %s' % (path, e), flush=True)
        return 'failed', 0
    fp = ts.tree_fingerprint(N)
    want = (info.get('groups') or {}).get(name[2:], {}).get('tree_fp')
    if want and want != fp:
        print('  ERROR %s changed after packing (fingerprint %s, manifest says %s): pack it again' % (name, fp, want), flush=True)
        return 'failed', 0
    old = read_json(outp, default=None) if os.path.exists(outp) else None
    if old is not None and not a.force:
        st, msg = ts.check_analysis(N, old)
        if st == 'ok':
            print('  skip (exists, valid): %s' % outp, flush=True)
            return 'skipped', 0
        print('  existing %s is %s (%s): moved aside, running again' % (os.path.basename(outp), st, msg), flush=True)
        os.replace(outp, outp + '.stale')
    elif old is None and os.path.exists(outp):
        os.replace(outp, outp + '.stale')   # unreadable (half written by something else): keep it for inspection, never reuse
    if a.force and os.path.exists(outp + '.part'):
        os.remove(outp + '.part')    # --force means from scratch, not from an old checkpoint
    t0 = time.time()
    rc = an.analyze(N, outp, a.visits, a.forced, limit=a.limit)
    dt = time.time() - t0
    if rc in (4, 5):
        return 'failed', rc          # the engine itself is the problem: stop the batch, a re-run continues from the checkpoint
    if rc == 2:
        return 'failed', 0
    if rc == 3:                      # perspective looks wrong: analyze2 wrote the file but it must never travel back
        os.replace(outp, outp + '.suspect')
        return 'suspect', 0
    A = read_json(outp)
    st, msg = ts.check_analysis(N, A)
    if st != ('incomplete' if a.limit else 'ok'):
        print('  ERROR the finished file is not accepted by treesync.check_analysis: %s %s' % (st, msg), flush=True)
        os.replace(outp, outp + '.rejected')
        return 'failed', 0
    nodes, forced, queries = entry_stats(A)
    total = queries + forced
    meta = {'group': name, 'seconds': round(dt), 'queries_main': queries, 'queries_forced': forced, 'queries_total': total,
            'sec_per_query': round(dt / total, 2) if total else None, 'branch_nodes': nodes, 'region': A['_meta'].get('region'),
            'visits': a.visits, 'forced_visits': a.forced, 'errors': A['_meta'].get('errors', 0), 'report_as': A['_meta'].get('report_as'),
            'tree_fp': fp, 'finished': time.strftime('%Y-%m-%d %H:%M:%S'),
            'note': 'seconds covers the last run only; a resumed group counts from the resume'}
    meta.update(info.get('run', {}))
    atomic_write_json(outp[:-len('.json')] + '.meta.json', meta, ensure_ascii=False, indent=1)
    print('  done %s: %ds, %d main + %d forced queries, %.1f s per query' % (name, dt, queries, forced, dt / total if total else 0), flush=True)
    if meta['errors']:
        print('  WARNING %d queries returned an error: those nodes have no AI data' % meta['errors'], flush=True)
        return 'failed', 0
    return 'done', 0


# ---------------------------------------------------------------- command line

def build_engine(a, outdir):
    """Put the engine command and the settings analyze2 reads from the environment in place. Returns (info about the engine, exit code)."""
    run = {}
    if a.engine_cmd:
        os.environ['WEIQI_KATAGO_CMD'] = json.dumps(shlex.split(a.engine_cmd))
        run['engine'] = 'custom command (tests)'
    else:
        if not a.model or not os.path.exists(a.model):
            print('Model file not found: %r (pass the .bin.gz with --model)' % a.model, file=sys.stderr)
            return None, 2
        cfgdir = os.path.join(outdir, 'katago_cfg')
        os.makedirs(cfgdir, exist_ok=True)
        cfg = os.path.join(cfgdir, 'analysis.cfg')   # the file name analyze2 expects inside WEIQI_KATAGO_DIR
        if a.cfg:
            txt = open(a.cfg, encoding='utf-8', errors='replace').read()
            if not re.search(r'^\s*reportAnalysisWinratesAs\s*=\s*BLACK\b', txt, re.M):
                print('warning: the supplied cfg has no reportAnalysisWinratesAs = BLACK; it is forced with -override-config.', file=sys.stderr)
            open(cfg, 'w', encoding='utf-8').write(txt)
        else:
            # KataGo's own log goes to the local temp folder: the output folder may be a synced Drive folder
            logdir = os.path.join(tempfile.gettempdir(), 'katago_logs').replace('\\', '/')
            open(cfg, 'w', encoding='utf-8').write(CFG.format(logdir=logdir, nat=a.threads, nst=a.search_threads, bs=a.batch))
        os.environ['WEIQI_KATAGO_DIR'] = cfgdir
        os.environ['WEIQI_KATAGO_MODEL'] = a.model
        os.environ['WEIQI_KATAGO_CMD'] = json.dumps([a.katago, 'analysis', '-model', a.model, '-config', cfg,
                                                     '-override-config', 'reportAnalysisWinratesAs=BLACK'])
        run['katago'] = engine_version(a.katago)
        run['model'] = os.path.basename(a.model)
        run['model_bytes'] = os.path.getsize(a.model)
        run['model_sha256'] = sha256_of(a.model)
        print('KataGo:', run['katago'] or '(version unknown)')
        print('weights: %s, %d bytes, sha256 %s' % (run['model'], run['model_bytes'], run['model_sha256']), flush=True)
        if a.expect_sha256 and a.expect_sha256.lower() != run['model_sha256']:
            print('The weights file is not the one the local pipeline uses (expected sha256 %s). Results would not be comparable '
                  'with the existing analysis. Upload the right file, or drop --expect-sha256 if you really mean it.' % a.expect_sha256, file=sys.stderr)
            return None, 2
    os.environ['WEIQI_WINDOW'] = str(a.window)
    os.environ['WEIQI_STALL_S'] = str(a.stall)
    widen_startup_wait(a.start_timeout)
    fix_initial_player()
    run['initial_player'] = 'explicit for requests without moves (side_to_move)'
    return {'run': run}, 0


def main(argv=None):
    setup_stdio()
    ap = argparse.ArgumentParser(description='Cloud batch runner around pipeline/analyze2.py')
    ap.add_argument('--in', dest='inp', required=True, help='directory containing g_*.n.json, or a single n.json file')
    ap.add_argument('--out', required=True, help='output directory (g_*.a2.json is written here)')
    ap.add_argument('--katago', default=os.environ.get('KATAGO_BIN', './katago'))
    ap.add_argument('--model', default=os.environ.get('KATAGO_MODEL', ''))
    ap.add_argument('--expect-sha256', default='', help='refuse to run when the weights file has another sha256 (same network as the local machine)')
    ap.add_argument('--cfg', default='', help='your own analysis.cfg; generated automatically if omitted (reportAnalysisWinratesAs=BLACK is forced anyway)')
    ap.add_argument('--engine-cmd', default='', help='(for tests) use this command instead of katago, e.g. "python fake_katago.py"')
    ap.add_argument('--visits', type=int, default=220, help='main search visits (local baseline 220)')
    ap.add_argument('--forced', type=int, default=100, help='forced evaluation visits (local baseline 100)')
    ap.add_argument('--threads', type=int, default=2, help='numAnalysisThreads (can be raised to 3~4 on a strong GPU)')
    ap.add_argument('--search-threads', type=int, default=16)
    ap.add_argument('--batch', type=int, default=64, help='nnMaxBatchSize')
    ap.add_argument('--window', type=int, default=8, help='queries in flight at once (never write everything up front)')
    ap.add_argument('--stall', type=float, default=900, help='seconds without any answer before the run gives up')
    ap.add_argument('--start-timeout', type=float, default=600, help='seconds to wait for the first answer (network load plus self test)')
    ap.add_argument('--limit', type=int, default=int(os.environ.get('LIMIT', '0')), help='analyze only the first N branch points per group (trial run, the result is marked incomplete)')
    ap.add_argument('--force', action='store_true', help='recompute even if a valid a2.json already exists')
    ap.add_argument('--only', default='', help='only process groups whose file name contains this substring')
    a = ap.parse_args(argv)

    files = [a.inp] if os.path.isfile(a.inp) else sorted(glob.glob(os.path.join(a.inp, 'g_*.n.json')))
    manifest = read_json(os.path.join(a.inp, 'manifest.json'), default=None) if os.path.isdir(a.inp) else None
    if a.only:
        files = [f for f in files if a.only in os.path.basename(f)]
    if not files:
        print('No g_*.n.json found in %s' % a.inp, file=sys.stderr)
        return 2
    files = order_files(files, manifest)
    os.makedirs(a.out, exist_ok=True)
    info, rc = build_engine(a, a.out)
    if rc:
        return rc
    info['groups'] = (manifest or {}).get('groups', {})
    print('%d groups to look at, window %d, %d/%d visits' % (len(files), a.window, a.visits, a.forced), flush=True)
    summary, T0, stop = [], time.time(), 0
    for k, f in enumerate(files, 1):
        name = os.path.basename(f)[:-len('.n.json')]
        print('[%d/%d] %s' % (k, len(files), name), flush=True)
        t0 = time.time()
        status, stop = run_group(f, os.path.join(a.out, name + '.a2.json'), a, info)
        summary.append({'group': name, 'status': status, 'seconds': round(time.time() - t0)})
        if stop:
            print('Stopping: the engine failed. Everything answered so far is kept in the .part file, run the same command again to continue.', flush=True)
            break
    atomic_write_json(os.path.join(a.out, 'run_summary.json'), {'finished': time.strftime('%Y-%m-%d %H:%M:%S'), 'total_seconds': round(time.time() - T0),
                                                                'groups': summary}, ensure_ascii=False, indent=1)
    bad = [s['group'] for s in summary if s['status'] in ('failed', 'suspect')]
    print('summary: %s' % ', '.join('%s=%d' % (st, sum(1 for s in summary if s['status'] == st)) for st in ('done', 'skipped', 'failed', 'suspect')))
    if bad:
        print('groups that need a look: %s' % ', '.join(bad))
    print('all done ->', os.path.abspath(a.out))
    return stop or (1 if bad else 0)


if __name__ == '__main__':
    sys.exit(main())
