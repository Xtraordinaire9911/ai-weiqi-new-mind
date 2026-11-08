"""KataGo local analysis of every branch point of a variation tree.

Usage: analyze2.py n.json out.json [main_visits=220] [teacher_move_visits=100]     (env LIMIT=n: only the first n nodes)

Reads the tree, asks KataGo (JSON analysis engine) about each branch point inside the region the
lesson is about, evaluates the teacher's moves separately, and writes out.json:
  { "<node id>": {turn, score, wr, cand:[...]}, "<id>_0": same without stones outside the region, "_meta": {...} }

Scores are ALWAYS stored from the side to move (stm). KataGo reports them from Black's point of view
when reportAnalysisWinratesAs=BLACK, so convert() flips them for White. How the engine reports is not
assumed: a handicap position with White to move is asked first (detect_report_as).

Who moves first is never left to KataGo: a node without moves (a position set up from stones) is sent with an explicit
initialPlayer, the colour the teacher plays next (side_to_move). Nodes with moves get their side from the moves.

Robustness: results are checkpointed to out.json.part (resume after a crash, same tree only), progress with an
ETA goes to out.json.progress.log, a silent or dead engine ends the run with a clear message instead of a hang.
"""
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time

from treesync import make_meta, perspective_suspect, tree_fingerprint
from wqutil import atomic_write_json, read_json, setup_stdio, utf8_env

L = 'ABCDEFGHJKLMNOPQRST'
C = 18  # columns of the recognised board (see board.py)


# ---------------------------------------------------------------- configuration (env overrides, defaults = the original install)

def cfg():
    root = os.environ.get('WEIQI_KATAGO_ROOT', r'D:\workspace\fun\Weiqi\Weiqi_AI')
    E = os.environ.get('WEIQI_KATAGO_DIR', os.path.join(root, 'engine', 'katago-v1.18.0-opencl-windows-x64'))
    return {
        'dir': E,
        'config': os.path.join(E, 'analysis.cfg'),
        'model': os.environ.get('WEIQI_KATAGO_MODEL', os.path.join(root, 'weights', 'network_file', 'kata1-tf3-b11c768-s12752M-d6531M.bin.gz')),
        'window': int(os.environ.get('WEIQI_WINDOW', '8')),            # queries in flight at once (never write everything up front: pipe deadlock risk)
        'stall': float(os.environ.get('WEIQI_STALL_S', '900')),        # seconds without any answer before we give up
    }


def engine_cmd(c):
    if os.environ.get('WEIQI_KATAGO_CMD'):          # a json list; used by the tests to plug in a fake engine
        return json.loads(os.environ['WEIQI_KATAGO_CMD'])
    return [os.path.join(c['dir'], 'katago.exe'), 'analysis', '-model', c['model'], '-config', c['config']]


def cfg_report_as(path):
    """reportAnalysisWinratesAs from the engine config file, or None."""
    try:
        with open(path, encoding='utf-8-sig') as f:
            for line in f:
                m = re.match(r'\s*reportAnalysisWinratesAs\s*=\s*(\w+)', line)
                if m:
                    return m.group(1).upper()
    except OSError:
        pass
    return None


# ---------------------------------------------------------------- perspective (incident 1: Black scores used as side-to-move)

def stm_sign(turn, report_as):
    """Factor that turns a score lead reported by KataGo into the side-to-move value."""
    if report_as == 'SIDETOMOVE':
        return 1
    if report_as == 'BLACK':
        return 1 if turn == 'B' else -1
    if report_as == 'WHITE':
        return 1 if turn == 'W' else -1
    raise ValueError('unknown reportAnalysisWinratesAs %r' % report_as)


def stm_winrate(wr, turn, report_as):
    return wr if stm_sign(turn, report_as) == 1 else 1 - wr


def convert(d, report_as):
    """One KataGo answer -> our record, everything from the side to move. The ONLY place that flips signs."""
    r = d['rootInfo']
    t = r['currentPlayer']
    sg = stm_sign(t, report_as)
    mi = sorted(d['moveInfos'], key=lambda m: m['order'])
    return {'turn': t, 'score': round(sg * r['scoreLead'], 1), 'wr': round(stm_winrate(r['winrate'], t, report_as), 3),
            'cand': [{'m': m['move'], 'v': m['visits'], 's': round(sg * m['scoreLead'], 1),
                      'wr': round(stm_winrate(m['winrate'], t, report_as), 3), 'p': round(m['prior'], 3), 'pv': m['pv'][:8]}
                     for m in mi[:14]]}


def selftest_query():
    """Nine handicap stones, White to move: Black is far ahead, so who the numbers are 'for' shows immediately."""
    stars = [['B', p] for p in ('D4', 'D10', 'D16', 'K4', 'K10', 'K16', 'Q4', 'Q10', 'Q16')]
    return {'id': 'selftest', 'initialStones': stars, 'moves': [], 'initialPlayer': 'W', 'rules': 'japanese', 'komi': 0.5,
            'boardXSize': 19, 'boardYSize': 19, 'maxVisits': 16, 'analyzeTurns': [0]}


def detect_report_as(eng, cfg_file, log):
    """How does this engine report winrates? Returns (BLACK|SIDETOMOVE|WHITE, source).

    Order: env WEIQI_REPORT_AS, a live check with the handicap position, the config file, else BLACK (the original setup).
    A live check beats the config file because the file is only what we hope was loaded.
    """
    if os.environ.get('WEIQI_REPORT_AS'):
        return os.environ['WEIQI_REPORT_AS'].upper(), 'env'
    from_cfg = cfg_report_as(cfg_file)
    try:
        eng.send(selftest_query())
        r = eng.get_for('selftest', 120)['rootInfo']
        if r['currentPlayer'] == 'W':
            found = 'BLACK' if r['winrate'] > 0.65 else ('SIDETOMOVE' if r['winrate'] < 0.35 else None)
            if found:
                if from_cfg and from_cfg != found:
                    log('WARN the engine reports %s but %s says %s: using what the engine really does' % (found, cfg_file, from_cfg))
                return found, 'selftest'
    except (KeyError, TypeError) as e:
        log('WARN perspective self test gave no usable answer (%s), falling back' % e)
    if from_cfg:
        return from_cfg, 'cfg'
    log('WARN could not determine the score perspective, assuming BLACK like the original config')
    return 'BLACK', 'assumed'


# ---------------------------------------------------------------- the engine process

class EngineError(RuntimeError):
    pass


class Engine:
    """KataGo analysis engine behind a reader thread, so waiting for an answer can time out."""

    def __init__(self, cmd, errfile, stall=900):
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errfile, text=True,
                                  encoding='utf-8', env=utf8_env())
        self.q = queue.Queue()
        self.stall = stall
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            self.q.put(line)
        self.q.put(None)  # EOF: the engine is gone

    def send(self, req):
        try:
            self.p.stdin.write(json.dumps(req) + '\n')
            self.p.stdin.flush()
        except (OSError, ValueError) as e:
            raise EngineError('engine is not accepting input (%s); exit code %s' % (e, self.p.poll()))

    def get(self, timeout=None):
        """Next answer line as dict. Raises EngineError when the engine died or stays silent."""
        wait = timeout or self.stall
        try:
            line = self.q.get(timeout=wait)
        except queue.Empty:
            raise EngineError('no answer from KataGo for %d s (stalled?)' % wait)
        if line is None:
            self.q.put(None)
            raise EngineError('KataGo exited (code %s)' % self.p.poll())
        try:
            return json.loads(line)
        except ValueError:
            return {'_raw': line.strip()[:200]}

    def get_for(self, qid, timeout):
        while True:
            d = self.get(timeout)
            if d.get('id') == qid:
                return d

    def close(self):
        try:
            self.p.stdin.close()
        except OSError:
            pass
        try:
            self.p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.p.kill()


# ---------------------------------------------------------------- tree, region, queries

def region(N):
    """Rectangle that covers the lesson: 3%..97% quantiles of all move points +2 lines, snapped to the edges. None if no moves."""
    cs = set()
    for n in N:
        if n['dead']:
            continue
        if n['mv'] is not None:
            cs.add((n['mv'][0] % C, n['mv'][0] // C))
        elif n['par'] == 0:
            for t in re.findall(r'[BW]\d+', n['pos']):
                k = int(t[1:])
                cs.add((k % C, k // C))
    if not cs:
        return None
    xs = sorted(c for c, _ in cs)
    ys = sorted(r for _, r in cs)
    pc = lambda a, p: a[min(len(a) - 1, int(len(a) * p))]
    x0 = max(0, pc(xs, .03) - 2)
    x1 = min(17, pc(xs, .97) + 2)
    y0 = max(0, pc(ys, .03) - 2)
    y1 = min(18, pc(ys, .97) + 2)
    if x0 <= 3:
        x0 = 0
    if y1 >= 15:
        y1 = 18
    if x1 >= 14:
        x1 = 17
    if y0 <= 3:
        y0 = 0
    return dict(x0=x0, x1=x1, y0=y0, y1=y1)


def gtp(c, r):
    return L[c] + str(19 - r)


def allowed(R):
    """GTP points of the region: the only moves KataGo may suggest."""
    return [gtp(x, y) for x in range(R['x0'], R['x1'] + 1) for y in range(R['y0'], R['y1'] + 1)]


def parse_pos(pos):
    d = {}
    for t in re.findall(r'[BW]\d+', pos):
        k = int(t[1:])
        d[(k % C, k // C)] = t[0]
    return d


def inreg(R, c, r):
    return R['x0'] <= c <= R['x1'] and R['y0'] <= r <= R['y1']


def path_of(N, i):
    p = []
    while N[i]['mv'] is not None:
        p.append(i)
        i = N[i]['par']
    return i, p[::-1]


def stones_at(N, i):
    """All stones at node i (setup position + moves): decides whether anything lies outside the region."""
    ri, p = path_of(N, i)
    d = dict(parse_pos(N[ri]['pos']))
    for j in p:
        d[(N[j]['mv'][0] % C, N[j]['mv'][0] // C)] = N[j]['mv'][1]
    return d


def query(N, R, allow, i, ctx, qid, visits):
    """KataGo request for node i. ctx=False drops the stones outside the region (the 'without outside influence' control)."""
    ri, p = path_of(N, i)
    ini = [[v, gtp(*k)] for k, v in parse_pos(N[ri]['pos']).items() if ctx or inreg(R, *k)]
    mv = [[N[j]['mv'][1], gtp(N[j]['mv'][0] % C, N[j]['mv'][0] // C)] for j in p
          if (ctx or inreg(R, N[j]['mv'][0] % C, N[j]['mv'][0] // C))]
    req = {'id': qid, 'initialStones': ini, 'moves': mv, 'rules': 'japanese', 'komi': 6.5, 'boardXSize': 19, 'boardYSize': 19,
           'analyzeTurns': [len(mv)], 'maxVisits': visits,
           'allowMoves': [{'player': 'B', 'moves': allow, 'untilDepth': 40}, {'player': 'W', 'moves': allow, 'untilDepth': 40}]}
    if not mv:
        # Incident 12: with no moves KataGo guesses who plays first (mostly Black), so a position set up from stones where the
        # teacher continues with White was analysed for the wrong side. Say it explicitly. This also covers a control
        # query (ctx=False) whose moves all lie outside the region.
        req['initialPlayer'] = side_to_move(N, i)
    return req


def live_children(N, i):
    return [c for c in N[i]['ch'] if not N[c]['dead']]


def side_to_move(N, i):
    """'B' or 'W' for node i: the opposite of the colour that just moved, else (a position set up from stones, or the empty
    board) the colour the teacher plays next, i.e. the majority among its live children (a tie goes to Black), else 'B'."""
    if N[i]['mv'] is not None:
        return 'W' if N[i]['mv'][1] == 'B' else 'B'
    cols = [N[c]['mv'][1] for c in live_children(N, i) if N[c]['mv']]
    return max(sorted(set(cols)), key=cols.count) if cols else 'B'


def wrong_turns(N, entries):
    """Keys ('<id>' or '<id>_0') of entries about a node without a move (a position set up from stones, or the empty board)
    whose recorded turn is not side_to_move(). A node with a move cannot go wrong this way: KataGo reads the side from the moves.
    `entries` is an a2.json dict or a checkpoint's `done`; stubs without a turn (engine errors) are skipped."""
    bad = []
    for k, a in entries.items():
        m = re.fullmatch(r'(\d+)(_0)?', k)
        if not m or not isinstance(a, dict) or a.get('turn') not in ('B', 'W'):
            continue
        i = int(m.group(1))
        if i < len(N) and not N[i]['dead'] and N[i]['mv'] is None and a['turn'] != side_to_move(N, i):
            bad.append(k)
    return bad


def branch_nodes(N):
    """Nodes worth analysing: branch points (leaves and single chains mean nothing) and the first node after a setup."""
    todo = [i for i in range(len(N)) if not N[i]['dead'] and len(live_children(N, i)) >= 2]
    rootkids = [i for i in range(len(N)) if not N[i]['dead'] and N[i]['setup'] and len(live_children(N, i)) == 1 and N[i]['par'] == 0]
    return sorted(set(todo + rootkids))


# ---------------------------------------------------------------- progress and checkpoint

class Progress:
    """Progress lines with counts and ETA: <out>.progress.log (append), <out>.progress.json (latest) and stderr."""

    def __init__(self, out):
        self.log_path, self.json_path = out + '.progress.log', out + '.progress.json'
        self.phase, self.total, self.base, self.nodes_total = '', 0, 0, 0
        self.t0, self.last = time.time(), 0.0

    def start(self, phase, total, already, nodes_total, nodes_done):
        self.phase, self.total, self.base, self.nodes_total = phase, total, already, nodes_total
        self.t0, self.last = time.time(), 0.0
        self.tick(already, nodes_done, force=True)

    def tick(self, done, nodes_done, force=False):
        now = time.time()
        if not force and now - self.last < 5:
            return
        self.last = now
        el = now - self.t0
        new = done - self.base  # answered in this run (resumed ones cost no time)
        eta = (self.total - done) * el / new if new > 0 else None
        line = '%s %s: %d/%d queries, nodes %d/%d, elapsed %ds, eta %s' % (
            time.strftime('%H:%M:%S'), self.phase, done, self.total, nodes_done, self.nodes_total, el,
            ('%ds' % eta) if eta is not None else 'n/a')
        print(line, file=sys.stderr, flush=True)
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
            atomic_write_json(self.json_path, {'phase': self.phase, 'done': done, 'total': self.total, 'nodes_done': nodes_done,
                                               'nodes_total': self.nodes_total, 'elapsed_s': round(el),
                                               'eta_s': None if eta is None else round(eta), 'updated': time.strftime('%Y-%m-%d %H:%M:%S')})
        except OSError:
            pass


def load_part(path, fp, visits, report_as):
    """Results of an interrupted run, only if they belong to this tree, these visits and this score perspective."""
    d = read_json(path, default=None, quarantine=True)
    if isinstance(d, dict) and d.get('tree_fp') == fp and d.get('visits') == visits and d.get('report_as') == report_as:
        return d.get('done', {})
    return {}


# ---------------------------------------------------------------- the run

def run_queries(eng, reqs, done, convert_fn, save, prog, window, node_of, every=25):
    """Send the reqs that are not in `done` yet, at most `window` in flight, and store the converted answers in `done`."""
    it = iter([r for r in reqs if r['id'] not in done])
    inflight = set()
    got = base = sum(1 for r in reqs if r['id'] in done)
    nodes = {node_of(r['id']) for r in reqs if r['id'] in done}

    def feed():
        while len(inflight) < window:
            r = next(it, None)
            if r is None:
                return
            eng.send(r)
            inflight.add(r['id'])

    feed()
    since, last_save = 0, time.time()
    while inflight:
        d = eng.get()
        qid = d.get('id')
        if qid not in inflight:
            print('engine: ignoring %s' % json.dumps(d, ensure_ascii=False)[:160], file=sys.stderr)  # a warning line or a stray answer
            continue
        inflight.discard(qid)
        done[qid] = convert_fn(d) if 'moveInfos' in d else {'err': json.dumps(d, ensure_ascii=False)[:120]}
        got += 1
        nodes.add(node_of(qid))
        since += 1
        if since >= every or time.time() - last_save > 30:
            save()
            since, last_save = 0, time.time()
        prog.tick(got, len(nodes))
        feed()
    save()
    prog.tick(got, len(nodes), force=True)
    return got - base


def search_nodes(eng, N, R, allow, nodes, VB, VF, conv, done, save, prog, window):
    """The two search phases for `nodes`. Returns {request id: record}: '<id>' (main search, the teacher's moves attached as
    forced candidates) and '<id>_0' (the control run without the stones outside the region, when there are such stones).

    `done` holds answers already known (a checkpoint) and receives the new ones. analyze() runs this for every branch
    node, fixturns.py (wq.py fix-setup-turns) for the few nodes whose entries have to be redone.
    """
    base_of = lambda q: q.split('_')[0]
    # phase 1: main search at every node (+ a control run without the stones outside the region)
    reqs = []
    for i in nodes:
        reqs.append(query(N, R, allow, i, True, '%d' % i, VB))
        if any(not inreg(R, *k) for k in stones_at(N, i)):
            reqs.append(query(N, R, allow, i, False, '%d_0' % i, min(VB, 200)))
    already = sum(1 for r in reqs if r['id'] in done)
    prog.start('phase 1/2 main search', len(reqs), already, len(nodes), len({base_of(r['id']) for r in reqs if r['id'] in done}))
    run_queries(eng, reqs, done, conv, save, prog, window, base_of)
    res = {r['id']: done[r['id']] for r in reqs}
    # phase 2: the teacher's move at each node, if the main search did not look at it enough
    reqs2, need = [], []
    for i in nodes:
        a = res.get('%d' % i)
        if not a or 'cand' not in a:
            continue
        tv = max(m['v'] for m in a['cand'])
        for ch in live_children(N, i):
            if N[ch]['mv'] is None:
                continue
            m = gtp(N[ch]['mv'][0] % C, N[ch]['mv'][0] // C)
            cm = next((x for x in a['cand'] if x['m'] == m), None)
            if cm and cm['v'] >= max(10, .1 * tv):
                continue
            if m not in allow:
                continue  # outside the region (tenuki): not evaluated
            reqs2.append(query(N, R, allow, ch, True, 'f%d' % ch, VF))
            need.append((i, ch, m))
    prog.start('phase 2/2 teacher moves', len(reqs2), sum(1 for r in reqs2 if r['id'] in done), len(reqs2), 0)
    run_queries(eng, reqs2, done, conv, save, prog, window, lambda q: q)
    for i, ch, m in need:
        f, a = done.get('f%d' % ch), res['%d' % i]
        if not f or 'cand' not in f or not f['cand']:
            continue
        t = f['cand'][0]
        a['cand'].append({'m': m, 'v': VF, 's': round(-f['score'], 1), 'wr': round(1 - f['wr'], 3), 'p': -1, 'pv': [m] + t['pv'][:7], 'f': 1})
    return res


def analyze(N, out, VB, VF, limit=0, log=lambda s: print(s, file=sys.stderr, flush=True)):
    """Whole run. Exit code: 0 ok, 2 nothing to analyse, 3 suspicious scores written, 4 engine failed, 5 engine missing."""
    c = cfg()
    R = region(N)
    if R is None:
        log('ERROR the tree has no moves: nothing to analyse (did board recognition fail for every video?)')
        return 2
    allow = allowed(R)
    todo = branch_nodes(N)
    if limit:
        todo = todo[:limit]
    fp = tree_fingerprint(N)
    log('region %s, branch nodes %d, tree %s' % (R, len(todo), fp))
    t0 = time.time()
    try:
        errf = open(out + '.err', 'wb')   # KataGo's own log
    except OSError as e:
        log('ERROR cannot write next to %s: %s' % (out, e))
        return 5
    try:
        eng = Engine(engine_cmd(c), errf, c['stall'])
    except OSError as e:
        errf.close()
        log('ERROR cannot start KataGo: %s (set WEIQI_KATAGO_DIR / WEIQI_KATAGO_MODEL)' % e)
        return 5
    prog = Progress(out)
    part, done, state = out + '.part', {}, {'report_as': None}

    def save():
        if done:
            atomic_write_json(part, {'tree_fp': fp, 'visits': [VB, VF], 'report_as': state['report_as'], 'done': done})

    try:
        report_as, source = detect_report_as(eng, c['config'], log)
        state['report_as'] = report_as
        log('score perspective of the engine: %s (%s), stored as side to move' % (report_as, source))
        done.update(load_part(part, fp, [VB, VF], report_as))
        stale = wrong_turns(N, done)
        for k in stale:   # a checkpoint from before incident 12 may hold setup nodes analysed for the wrong side
            del done[k]
        if stale:
            log('WARN dropped %d checkpoint results with the wrong side to move, they are asked again: %s' % (len(stale), ', '.join(stale)))
        if done:
            log('resuming: %d results from an earlier run' % len(done))
        conv = lambda d: convert(d, report_as)
        res = search_nodes(eng, N, R, allow, todo, VB, VF, conv, done, save, prog, c['window'])
    except EngineError as e:
        save()
        log('ERROR %s. %d results are kept in %s, run again to continue.' % (e, len(done), part))
        eng.close()
        errf.close()
        return 4
    except BaseException:
        save()
        eng.close()
        errf.close()
        raise
    eng.close()
    errf.close()
    errors = sum(1 for v in res.values() if 'err' in v)
    res['_meta'] = make_meta(N, visits=[VB, VF], region=R, complete=not limit, report_as=report_as, report_as_source=source,
                             errors=errors, queries=len(res), elapsed_s=round(time.time() - t0))
    atomic_write_json(out, res)
    try:
        os.remove(part)
    except OSError:
        pass
    log('done in %ds, %d entries, %d errors' % (time.time() - t0, len(res) - 1, errors))
    sus, stats = perspective_suspect(res)
    if sus:
        log('ERROR the scores look like Black perspective (first candidate is not the best one: %s). They will not be merged.' % stats)
        return 3
    return 0


def main(argv=None):
    setup_stdio()
    argv = argv if argv is not None else sys.argv
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 1
    N = read_json(argv[1])
    VB = int(argv[3]) if len(argv) > 3 else 220
    VF = int(argv[4]) if len(argv) > 4 else 100
    return analyze(N, argv[2], VB, VF, limit=int(os.environ.get('LIMIT', '0')))


if __name__ == '__main__':
    sys.exit(main())
