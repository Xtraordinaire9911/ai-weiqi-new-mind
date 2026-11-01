#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""katago_bridge.py -- wraps the KataGo analysis engine in a very small HTTP interface for the josekiapp compute switch and engine panel.

Depends only on the Python standard library. It does one thing: forward (and validate) KataGo analysis JSON queries. It offers no shell, file or proxy functionality.

Intended (compliant) use:
  A. Local machine: run KataGo on your own computer and point the page at http://127.0.0.1:8787  (loopback only, not exposed)
  B. Your own / your university's machines: LRZ / a lab server / a rented cloud GPU VM -- reach it through SSH port forwarding or a reverse proxy with TLS
  X. **Do not** expose it through ngrok, cloudflared or similar tunnels from the Colab free tier or Kaggle: the Colab free-tier FAQ explicitly prohibits
     "connecting to remote proxies / SSH / remote desktop / web services unrelated to interactive computing", and Kaggle is not designed for it either, so the account may be banned. See README.md.

Endpoints (all need the token; none of them accepts a file path):
  GET  /health     engine state, KataGo version, backend (OpenCL, CUDA, TensorRT, Eigen, Metal, ...), active model id, limits and features
  GET  /models     the networks / configs the OPERATOR allowed (ids and labels only, never paths)
  POST /analyze    one query, one answer (the original endpoint, unchanged)
  POST /stream     one query, NDJSON answers over a chunked response (one line per update, the last one has "done": true)
  POST /terminate  stop the running streaming search now (KataGo "terminate"), frees the GPU
  POST /switch     change the active model / config by id from the operator's allowlist (NDJSON progress, restarts the KataGo subprocess under a lock)

Security design:
  * A token is required (Authorization: Bearer ...); if none is given, a random token is generated on a loopback address and printed once.
    Pass the token via the KATAGO_BRIDGE_TOKEN environment variable or --token-file, not on the command line (ps would show it). The token is compared in constant time,
    it is never read from the URL and never written to the log (the log shows method, path without query string, and status only).
  * Listens on 127.0.0.1 only by default; any other address needs an explicit --host, and a non-loopback address without TLS triggers a loud warning.
  * CORS allows only allowlisted origins (default http://localhost:8765 and http://127.0.0.1:8765; pages opened from file:// need --allow-file-origin).
  * Only analysis queries with allowlisted fields are accepted; maxVisits / number of moves / board size / body size are capped, concurrency is limited, and a streaming
    search is capped by visits and by wall-clock time. Only ONE streaming search can be active (a new one preempts the old one, the bridge has a single token).
  * Models and configs are chosen by id from an allowlist that the operator gives on the command line or in a small JSON file. A request can never name a path.
  * Forces reportAnalysisWinratesAs=BLACK (via -override-config on the command line) and adds bridge.winratesAs to every response so the page can check the perspective;
    the page converts to the side to move's perspective only when it sees BLACK, and otherwise refuses to show the result (to avoid perspective errors happening again).

Examples:
  # local machine (Windows)
  set KATAGO_BRIDGE_TOKEN=pick-a-long-random-string
  python katago_bridge.py --katago D:\\...\\katago.exe --model D:\\...\\kata1-tf3-b11c768-s12752M-d6531M.bin.gz
  # a second network the page may switch to
  python katago_bridge.py --katago ... --model a.bin.gz --allow-model big=b.bin.gz
  # try the UI without a GPU (returns fake data clearly labeled as simulated)
  python katago_bridge.py --fake
  # what you must provide
  python katago_bridge.py --print-setup
"""
import argparse, contextlib, hmac, json, os, queue, re, secrets, select, shlex, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BRIDGE_VERSION = 2
FEATURES = ['stream', 'terminate', 'models', 'switch']
LOC = re.compile(r'^(?:[A-HJ-T](?:1[0-9]|[1-9])|pass)$')
POINT = re.compile(r'^[A-HJ-T](?:1[0-9]|[1-9])$')
ID_OK = re.compile(r'^[A-Za-z0-9._-]{1,48}$')
ALLOWED_KEYS = {'id', 'initialStones', 'initialPlayer', 'moves', 'rules', 'komi', 'boardXSize', 'boardYSize',
                'analyzeTurns', 'maxVisits', 'allowMoves', 'avoidMoves', 'reportDuringSearchEvery'}
RULES = {'japanese', 'chinese', 'tromp-taylor', 'aga', 'korean', 'new-zealand', 'stone-scoring', 'ancient-area'}
GEN_CFG = """logDir = {logdir}
reportAnalysisWinratesAs = BLACK
maxVisits = 500
numAnalysisThreads = {nat}
numSearchThreadsPerAnalysisThread = {nst}
nnMaxBatchSize = {bs}
nnCacheSizePowerOfTwo = 22
nnMutexPoolSizePowerOfTwo = 16
nnRandomize = true
"""
SETUP_TEXT = """You provide exactly these (nothing else is needed):
  1. katago   path of the KataGo executable          --katago PATH   (or env KATAGO_BIN)
  2. model    path of the network file (.bin.gz)     --model PATH    (or env KATAGO_MODEL)
  3. config   analysis config, optional              --config PATH   (or env KATAGO_CONFIG; one is generated when omitted)
  4. port     TCP port, default 8787                 --port N
"""


class BadQuery(ValueError):
    pass


class Unavailable(Exception):
    """The engine is not ready (starting, switching or failed)."""

    def __init__(self, state):
        Exception.__init__(self, 'engine is %s' % state)
        self.state = state


class Busy(Exception):
    pass


def sanitize(q, max_visits=2000, max_moves=500, stream=False):
    """Validate and clean an analysis query sent by the client; returns a new dict (without id)."""
    if not isinstance(q, dict):
        raise BadQuery('the query must be a JSON object')
    extra = set(q) - ALLOWED_KEYS
    if extra:
        raise BadQuery('disallowed fields: ' + ','.join(sorted(map(str, extra))[:5]))

    def pairs(v, name, allow_pass):
        if not isinstance(v, list) or len(v) > max_moves:
            raise BadQuery(name + ' must be an array of at most %d items' % max_moves)
        out = []
        for it in v:
            if (not isinstance(it, list) or len(it) != 2 or it[0] not in ('B', 'W') or not isinstance(it[1], str)
                    or not (LOC if allow_pass else POINT).match(it[1])):
                raise BadQuery(name + ' contains an invalid item: %r' % (it,))
            out.append([it[0], it[1]])
        return out

    c = {}
    c['initialStones'] = pairs(q.get('initialStones', []), 'initialStones', False)
    c['moves'] = pairs(q.get('moves', []), 'moves', True)
    if 'initialPlayer' in q:
        if q['initialPlayer'] not in ('B', 'W'):
            raise BadQuery('initialPlayer must be B or W')
        c['initialPlayer'] = q['initialPlayer']
    c['rules'] = q.get('rules', 'japanese')
    if c['rules'] not in RULES:
        raise BadQuery('rules is not in the allowlist')
    k = q.get('komi', 6.5)
    if isinstance(k, bool) or not isinstance(k, (int, float)) or not -150 <= k <= 150:
        raise BadQuery('invalid komi')
    c['komi'] = k
    for ax in ('boardXSize', 'boardYSize'):
        v = q.get(ax, 19)
        if v not in (9, 13, 19) or isinstance(v, bool):
            raise BadQuery(ax + ' must be 9, 13 or 19')
        c[ax] = v
    if c['boardXSize'] != c['boardYSize']:
        raise BadQuery('only square boards are supported')
    turns = q.get('analyzeTurns')
    if turns is None:
        turns = [len(c['moves'])]
    if (not isinstance(turns, list) or len(turns) != 1 or isinstance(turns[0], bool) or not isinstance(turns[0], int)
            or not 0 <= turns[0] <= len(c['moves'])):
        raise BadQuery('analyzeTurns must be exactly one valid turn number')
    c['analyzeTurns'] = turns
    mv = q.get('maxVisits', 200)
    if isinstance(mv, bool) or not isinstance(mv, int) or not 1 <= mv <= max_visits:
        raise BadQuery('maxVisits must be in 1..%d' % max_visits)
    c['maxVisits'] = mv
    if 'reportDuringSearchEvery' in q:
        if not stream:
            raise BadQuery('reportDuringSearchEvery is only accepted by /stream')
        e = q['reportDuringSearchEvery']
        if isinstance(e, bool) or not isinstance(e, (int, float)) or not 0.1 <= e <= 5:
            raise BadQuery('reportDuringSearchEvery must be between 0.1 and 5 seconds')
        c['reportDuringSearchEvery'] = float(e)
    for key in ('allowMoves', 'avoidMoves'):
        if key in q:
            v = q[key]
            if not isinstance(v, list) or len(v) > 2:
                raise BadQuery(key + ' is invalid')
            out = []
            for it in v:
                if (not isinstance(it, dict) or it.get('player') not in ('B', 'W') or not isinstance(it.get('moves'), list)
                        or len(it['moves']) > 361 or not all(isinstance(m, str) and LOC.match(m) for m in it['moves'])):
                    raise BadQuery(key + ' contains an invalid item')
                ud = it.get('untilDepth', 1)
                if isinstance(ud, bool) or not isinstance(ud, int) or not 1 <= ud <= 100:
                    raise BadQuery('invalid untilDepth')
                out.append({'player': it['player'], 'moves': it['moves'], 'untilDepth': ud})
            c[key] = out
    return c


# --------------------------------------------------------------------------- operator allowlist (models and configs)
def slug_id(name):
    """A safe id from a file name: 'kata1-b18c384nbt-s123.bin.gz' -> 'kata1-b18c384nbt-s123'."""
    s = re.sub(r'(\.bin\.gz|\.txt\.gz|\.gz|\.bin|\.cfg)$', '', os.path.basename(name))
    return re.sub(r'[^A-Za-z0-9._-]+', '-', s).strip('-.')[:48] or 'model'


class Allowlist:
    """Models and configs the operator allowed. Requests refer to entries by id; paths never leave this object."""

    def __init__(self):
        self.items = {'model': {}, 'config': {}}

    def add(self, kind, eid, path, label=None, check=True):
        if not isinstance(eid, str) or not ID_OK.match(eid):
            raise ValueError('bad id %r (use 1..48 characters of A-Z a-z 0-9 . _ -)' % (eid,))
        if not isinstance(path, str) or not path:
            raise ValueError('%s %s: path is missing' % (kind, eid))
        if check and not os.path.isfile(path):
            raise ValueError('%s %s: file not found: %s' % (kind, eid, path))
        self.items[kind][eid] = {'id': eid, 'label': str(label or eid)[:80], 'path': path}

    def has(self, kind, eid):
        return eid in self.items[kind]

    def path(self, kind, eid):
        if not isinstance(eid, str) or eid not in self.items[kind]:
            raise BadQuery('%s id is not in the operator allowlist' % kind)
        return self.items[kind][eid]['path']

    def label(self, kind, eid):
        return self.items[kind][eid]['label'] if eid in self.items[kind] else str(eid)

    def public(self, kind, active):
        out = []
        for e in self.items[kind].values():
            try:
                size = os.path.getsize(e['path'])
            except OSError:
                size = None  # fake models or a file that disappeared
            out.append({'id': e['id'], 'label': e['label'], 'bytes': size, 'active': e['id'] == active})
        return out


def load_models_file(al, path, check=True):
    """Read the operator's JSON allowlist: {"models":[{"id","label","path"}], "configs":[{"id","label","path"}]}; relative paths are relative to the JSON file."""
    base = os.path.dirname(os.path.abspath(path))
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError('the models file must be a JSON object')
    for kind, key in (('model', 'models'), ('config', 'configs')):
        for e in data.get(key, []):
            if not isinstance(e, dict):
                raise ValueError('every entry of %s must be an object' % key)
            p = e.get('path', '')
            if isinstance(p, str) and p and not os.path.isabs(p):
                p = os.path.join(base, p)
            al.add(kind, e.get('id'), p, e.get('label'), check)


def parse_pair(s):
    if '=' not in s:
        raise ValueError('expected ID=PATH, got %r' % s)
    a, b = s.split('=', 1)
    return a.strip(), b.strip()


# --------------------------------------------------------------------------- backend detection
BACKEND_RE = re.compile(r'Using\s+(.+?)\s+backend', re.I)
BACKENDS = {'opencl': 'OpenCL', 'cuda': 'CUDA', 'tensorrt': 'TensorRT', 'eigen': 'Eigen', 'metal': 'Metal', 'rocm': 'ROCm', 'onnx': 'ONNX'}


def backend_from_text(text):
    """Parse the output of `katago version` ('Using OpenCL backend', 'Using Eigen(CPU) backend', ...). Returns a name or 'unknown'."""
    m = BACKEND_RE.search(text or '')
    if not m:
        return 'unknown'
    low = m.group(1).lower()
    for k, v in BACKENDS.items():
        if low.startswith(k):
            return v
    return 'unknown'


def detect_backend(katago_bin, run=subprocess.run):
    """Best effort: ask the binary (`katago version` only prints text, it does not load a network). 'unknown' when it cannot be told."""
    try:
        r = run([katago_bin, 'version'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20, universal_newlines=True, encoding='utf-8', errors='replace')
        return backend_from_text(r.stdout)
    except Exception:
        return 'unknown'


# --------------------------------------------------------------------------- KataGo process management
class KataGo:
    def __init__(self, cmd, stderr_path=None):
        self.cmd = cmd
        self.err = open(stderr_path, 'a', encoding='utf-8') if stderr_path else subprocess.DEVNULL
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err, text=True, encoding='utf-8')
        self.lock = threading.Lock()
        self.waiters = {}
        self.n = 0
        self.dead = False
        self.t = threading.Thread(target=self._reader, daemon=True)
        self.t.start()
        self.info = self._version()

    def _reader(self):
        for line in self.p.stdout:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            w = self.waiters.get(d.get('id'))
            if w is not None:
                w.put(d)
        self.dead = True
        for w in list(self.waiters.values()):
            w.put({'error': 'KataGo process exited', 'id': None})

    def _send(self, obj):
        with self.lock:
            self.p.stdin.write(json.dumps(obj) + '\n')
            self.p.stdin.flush()

    def _version(self):
        qid = self.new_id()
        w = self.waiters[qid] = queue.Queue()
        try:
            self._send({'id': qid, 'action': 'query_version'})
        except OSError:
            self.waiters.pop(qid, None)
            self.close()
            raise RuntimeError('KataGo process exited (wrong model or config path?)')
        t0, d = time.time(), None
        try:
            while d is None:  # loading the model can be slow (the first OpenCL tuning takes several minutes)
                try:
                    d = w.get(timeout=0.25)
                except queue.Empty:
                    if self.dead or self.p.poll() is not None:
                        d = {'error': 'KataGo process exited (wrong model or config path?)'}
                    elif time.time() - t0 > 120:
                        self.close()
                        raise RuntimeError('KataGo did not respond within 120 seconds (first-time OpenCL tuning, model too large, or wrong path?)')
        finally:
            self.waiters.pop(qid, None)
        if 'error' in d:
            self.close()
            raise RuntimeError('KataGo failed to start: %s' % d['error'])
        return {'version': d.get('version'), 'git_hash': d.get('git_hash')}

    def new_id(self):
        with self.lock:
            self.n += 1
            return 'br%d' % self.n

    def terminate(self, qid):
        try:
            self._send({'id': 'term_' + qid, 'action': 'terminate', 'terminateId': qid})
        except Exception:
            pass

    def alive(self):
        return self.p.poll() is None and not self.dead

    def analyze(self, q, qid, timeout, gone=lambda: False):
        return katago_analyze(self, q, qid, timeout, gone)

    def stream(self, q, qid, every, timeout, cancel, gone):
        return katago_stream(self, q, qid, every, timeout, cancel, gone)

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


class FakeKataGo:
    """For trying the UI without a GPU: returns deterministic **fake** analysis (Black's perspective, same format as the real engine); the bridge marks the response with fake=true."""
    dead = False

    def __init__(self, label='FAKE', load_seconds=0.0, rate=600):
        self.info = {'version': 'FAKE', 'git_hash': 'fake'}
        self.label = label
        self.rate = rate  # simulated visits per second
        self.n = 0
        self.lock = threading.Lock()
        self.terminated = []  # ids of searches that were stopped early (the selftest inspects this)
        if load_seconds:
            time.sleep(load_seconds)

    def new_id(self):
        with self.lock:
            self.n += 1
            return 'br%d' % self.n

    def alive(self):
        return True

    def terminate(self, qid):
        pass

    def close(self):
        pass

    def analyze(self, q, qid, timeout, gone=lambda: False):
        return fake_response(q, qid)

    def stream(self, q, qid, every, timeout, cancel, gone):
        """Yields (message, ended) like the real engine: updates grow in visits, the last one has isDuringSearch=False."""
        total, t0, last, seq = q['maxVisits'], time.time(), 0.0, 0
        while True:
            time.sleep(0.02)
            now = time.time()
            stop = cancel.is_set() or gone() or now - t0 > timeout
            if not stop and now - last < every:
                continue
            last = now
            visits = min(total, max(1, int((now - t0) * self.rate)))
            fin = visits >= total or stop
            if stop:
                self.terminated.append(qid)
            d = fake_response(q, qid, visits=visits, step=seq)
            d['isDuringSearch'] = not fin
            seq += 1
            yield d
            if fin:
                return


def fake_response(q, qid, visits=None, step=0):
    L = 'ABCDEFGHJKLMNOPQRST'
    occ = {loc for _, loc in q.get('initialStones', [])} | {loc for _, loc in q['moves'] if loc != 'pass'}
    mv = q['moves']
    t = ('W' if mv[-1][0] == 'B' else 'B') if mv else q.get('initialPlayer', 'B')
    allow = None
    for it in q.get('allowMoves', []):
        if it['player'] == t:
            allow = it['moves']
    if allow is None:
        allow = [L[c] + str(r) for r in range(1, 20) for c in range(19)]
    free = [m for m in allow if m not in occ and m != 'pass']
    # fake data only: prefer points near the last move (or near the stones), so the demo candidates sit where a real search would look
    ref = [loc for _, loc in (mv[-1:] or q.get('initialStones', [])[-1:])]
    if ref and ref[0] != 'pass':
        rc, rr = L.index(ref[0][0]), int(ref[0][1:])
        free.sort(key=lambda m: abs(L.index(m[0]) - rc) + abs(int(m[1:]) - rr))
    vtot = q['maxVisits'] if visits is None else visits
    seed = sum(ord(ch) for _, loc in mv for ch in loc) + len(mv) * 7
    sg = 1 if t == 'B' else -1
    infos = []
    for i, m in enumerate(free[:8]):
        # early on the order is shaken a little (so the demo shows moves changing places), the shake dies out as visits grow
        shake = 0.0 if visits is None else ((seed + i * 5 + step * 3) % 7 - 3) * 0.35 * max(0.0, 1 - vtot / 400.0)
        stm_score = 2.0 - 0.7 * i + ((seed + i * 13) % 5) * 0.1 + shake
        plen = 1 + min(3, vtot // 60) + (1 if i == 0 and vtot > 300 else 0)
        pv = ([m] + free[i + 1:i + 1 + plen])[:1 + plen]
        infos.append({'move': m, 'visits': max(3, int(vtot * (0.5 / (i + 1)))), 'order': i,
                      'scoreLead': round(sg * stm_score, 3), 'winrate': round(0.5 + sg * stm_score / 40, 4),
                      'prior': round(0.3 / (i + 1), 4), 'pv': pv})
    infos.sort(key=lambda d: -sg * d['scoreLead'])  # best for the side to move first, like KataGo's order
    for i, d in enumerate(infos):
        d['order'] = i
    best = infos[0] if infos else {'scoreLead': 0, 'winrate': .5}
    return {'id': qid, 'turnNumber': len(mv), 'isDuringSearch': False,
            'rootInfo': {'currentPlayer': t, 'scoreLead': best['scoreLead'], 'winrate': best['winrate'], 'visits': vtot}, 'moveInfos': infos}


def katago_analyze(kg, q, qid, timeout, gone):
    """Submit one query and wait for the result; terminate it on timeout or when the client disconnects."""
    w = kg.waiters[qid] = queue.Queue()
    try:
        kg._send(dict(q, id=qid))
        t0 = time.time()
        while True:
            try:
                d = w.get(timeout=0.25)
            except queue.Empty:
                if not kg.alive():
                    raise RuntimeError('KataGo process exited')
                if gone():
                    kg.terminate(qid)
                    raise ConnectionAbortedError('client gone')
                if time.time() - t0 > timeout:
                    kg.terminate(qid)
                    raise TimeoutError('analysis timed out (%ds)' % timeout)
                continue
            if 'error' in d:
                raise RuntimeError(str(d['error'])[:200])
            if 'moveInfos' in d or 'noResults' in d:
                return d
            # anything else (warnings etc.): ignore and keep waiting
    finally:
        kg.waiters.pop(qid, None)


def katago_stream(kg, q, qid, every, timeout, cancel, gone):
    """Generator over the updates of one query (reportDuringSearchEvery). The last item has isDuringSearch=False (or noResults).
    When `cancel` is set, the client is gone or the time cap is hit, KataGo gets a terminate action and the generator still yields the final partial result."""
    w = kg.waiters[qid] = queue.Queue()
    try:
        kg._send(dict(q, id=qid, reportDuringSearchEvery=every))
        t0, t_term, t_chk = time.time(), None, 0.0
        while True:
            now = time.time()
            if now - t_chk >= 0.2:  # checked on a clock, not only when the queue is empty: fast updates must not starve the checks
                t_chk = now
                if not kg.alive():
                    raise RuntimeError('KataGo process exited')
                if t_term is None and (cancel.is_set() or gone() or now - t0 > timeout):
                    kg.terminate(qid)
                    t_term = now
                elif t_term is not None and now - t_term > 15:
                    raise RuntimeError('KataGo did not answer the terminate request')
            try:
                d = w.get(timeout=0.2)
            except queue.Empty:
                continue
            if 'error' in d:
                raise RuntimeError(str(d['error'])[:200])
            if 'moveInfos' in d or 'noResults' in d:
                yield d
                if d.get('noResults') or not d.get('isDuringSearch', False):
                    return
            # anything else (warnings etc.): ignore and keep waiting
    finally:
        kg.waiters.pop(qid, None)


# --------------------------------------------------------------------------- engine host (owns the subprocess, restarts it on /switch)
class SearchSlot:
    """Exactly one streaming search at a time (the bridge has one token, so this is one per token). A new search preempts the old one."""

    def __init__(self):
        self.lock = threading.Lock()
        self.cur = None

    def begin(self, cid, qid):
        with self.lock:
            if self.cur is not None:
                self.cur['reason'] = 'preempted'
                self.cur['cancel'].set()
            self.cur = {'cid': cid, 'qid': qid, 'cancel': threading.Event(), 'reason': None, 't0': time.time()}
            return self.cur

    def end(self, s):
        with self.lock:
            if self.cur is s:
                self.cur = None

    def stop(self, cid=None, reason='terminated'):
        with self.lock:
            s = self.cur
            if s is not None and (cid is None or s['cid'] == cid):
                s['reason'] = reason
                s['cancel'].set()
                return True
        return False

    def active(self):
        with self.lock:
            return self.cur is not None and not self.cur['cancel'].is_set()


class EngineHost:
    """Owns the engine object. use() hands it out only while the state is 'ready'; switch() restarts it under a lock and rolls back when the new model fails to load."""

    def __init__(self, factory, allow, model_id, config_id=None):
        self.factory, self.allow = factory, allow
        self.cv = threading.Condition()
        self.switch_lock = threading.Lock()
        self.inflight = 0
        self.eng = None
        self.state = 'starting'
        self.active = {'model': model_id, 'config': config_id}
        self.progress = None
        self.error = None

    def start(self):
        self.eng = self.factory(self.active['model'], self.active['config'], False)
        with self.cv:
            self.state = 'ready'

    @contextlib.contextmanager
    def use(self):
        with self.cv:
            if self.state != 'ready' or self.eng is None:
                raise Unavailable(self.state)
            self.inflight += 1
            eng = self.eng
        try:
            yield eng
        finally:
            with self.cv:
                self.inflight -= 1
                self.cv.notify_all()

    def snapshot(self):
        with self.cv:
            return {'state': self.state, 'model': self.active['model'], 'config': self.active['config'], 'progress': self.progress, 'error': self.error,
                    'info': dict(self.eng.info) if self.eng is not None else {}, 'alive': bool(self.eng is not None and self.eng.alive())}

    def switch(self, model_id, config_id, report, slot):
        """Change the active model / config. Ids are checked against the allowlist BEFORE anything is stopped. report(dict) gets progress messages."""
        model_id = model_id if model_id is not None else self.active['model']
        self.allow.path('model', model_id)  # raises BadQuery for an unknown id
        if config_id is not None:
            self.allow.path('config', config_id)
        else:
            config_id = self.active['config']
        if not self.switch_lock.acquire(False):
            raise Busy('another switch is in progress')
        try:
            prev = dict(self.active)
            report({'state': 'stopping'})
            with self.cv:
                self.state = 'switching'
                self.progress = 'stopping'
                self.error = None
            slot.stop(reason='switch')  # end a running search first: it frees the GPU
            with self.cv:
                self.cv.wait_for(lambda: self.inflight == 0, timeout=20)
                old, self.eng = self.eng, None
            if old is not None:
                old.close()
            report({'state': 'loading', 'model': model_id})
            self.progress = 'loading'
            err = None
            try:
                new = self.factory(model_id, config_id, True)
                now = {'model': model_id, 'config': config_id}
            except Exception as e:  # keep the previous model alive when the new one cannot be loaded
                err = str(e)[:200]
                report({'state': 'rollback', 'error': err})
                try:
                    new = self.factory(prev['model'], prev['config'], True)
                    now = prev
                except Exception as e2:
                    with self.cv:
                        self.state, self.error, self.progress = 'error', 'could not restart the previous model: ' + str(e2)[:150], None
                    report({'state': 'error', 'error': self.error, 'done': True})
                    return False
            with self.cv:
                self.eng, self.active, self.state, self.progress, self.error = new, now, 'ready', None, err
            report({'state': 'ready' if err is None else 'failed', 'model': now['model'], 'error': err, 'done': True})
            return err is None
        finally:
            self.switch_lock.release()


# --------------------------------------------------------------------------- HTTP
class Cfg:
    pass


def origin_ok(cfg, origin):
    if origin is None:
        return True  # curl / non-browser client
    if origin == 'null':
        return cfg.allow_file
    return '*' in cfg.origins or origin in cfg.origins


class Handler(BaseHTTPRequestHandler):
    server_version = 'KataGoBridge/%d' % BRIDGE_VERSION
    protocol_version = 'HTTP/1.1'  # chunked responses need 1.1; every response still ends with Connection: close (one request per connection)

    def log_message(self, fmt, *args):  # never log request headers (they contain the token)
        sys.stderr.write('[bridge] %s %s\n' % (self.address_string(), fmt % args))

    def log_request(self, code='-', size='-'):  # method + path WITHOUT the query string + status: a token pasted into a URL by mistake must not reach the log
        self.log_message('"%s %s" %s', self.command, (self.path or '').split('?')[0][:80], code)

    # ---- helpers
    def _cors(self):
        o = self.headers.get('Origin')
        cfg = self.server.cfg
        if o and origin_ok(cfg, o):
            self.send_header('Access-Control-Allow-Origin', '*' if ('*' in cfg.origins) else o)
            self.send_header('Vary', 'Origin')
            self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Max-Age', '600')
            if self.headers.get('Access-Control-Request-Private-Network', '').lower() == 'true':
                self.send_header('Access-Control-Allow-Private-Network', 'true')

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self._cors()
        self.end_headers()
        self.wfile.write(b)

    def _nd_start(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson; charset=utf-8')
        self.send_header('Transfer-Encoding', 'chunked')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Accel-Buffering', 'no')  # nginx: do not buffer the stream
        self.send_header('Connection', 'close')
        self._cors()
        self.end_headers()
        self.nd_ok = True

    def _nd(self, obj):
        """Write one NDJSON line as one chunk. Returns False once the client is gone."""
        if not self.nd_ok:
            return False
        line = (json.dumps(obj, ensure_ascii=False) + '\n').encode('utf-8')
        try:
            self.wfile.write(b'%x\r\n' % len(line) + line + b'\r\n')
            self.wfile.flush()
            return True
        except (OSError, ValueError):
            self.nd_ok = False
            return False

    def _nd_end(self):
        if self.nd_ok:
            try:
                self.wfile.write(b'0\r\n\r\n')
                self.wfile.flush()
            except (OSError, ValueError):
                pass
        self.nd_ok = False

    def _auth(self):
        cfg = self.server.cfg
        o = self.headers.get('Origin')
        if o and not origin_ok(cfg, o):
            self._json(403, {'error': 'origin not in the allowlist: %s (add it with --allow-origin)' % o})
            return False
        h = self.headers.get('Authorization', '')
        tok = h[7:] if h.startswith('Bearer ') else ''
        if not hmac.compare_digest(tok.encode('utf-8'), cfg.token.encode('utf-8')):
            time.sleep(0.4)  # slow down brute-force guessing
            self._json(401, {'error': 'invalid token'})
            return False
        return True

    def _gone(self):
        try:
            r, _, _ = select.select([self.connection], [], [], 0)
            return bool(r) and self.connection.recv(1, socket.MSG_PEEK) == b''
        except (OSError, ValueError, AttributeError, TypeError):
            return False

    def _body(self, limit=256 * 1024, allow_empty=False):
        """Read and parse the JSON body. Sends the error response and returns None on failure."""
        try:
            n = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            n = -1
        if not (0 < n <= limit or (allow_empty and n == 0)):
            self._json(413, {'error': 'request body is empty or larger than %dKB' % (limit // 1024)})
            return None
        if n == 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as e:
            self._json(400, {'error': str(e)[:200]})
            return None

    def meta(self, ms=None, snap=None):
        s = self.server
        snap = snap or s.host.snapshot()
        m = {'v': BRIDGE_VERSION, 'winratesAs': 'BLACK', 'katago': snap['info'], 'model': s.cfg.model_label(snap['model']), 'modelId': snap['model'],
             'fake': s.cfg.fake, 'maxVisits': s.cfg.max_visits}
        if ms is not None:
            m['ms'] = ms
        return m

    # ---- routes
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header('Content-Length', '0')
        self.send_header('Connection', 'close')
        self.end_headers()

    def do_GET(self):
        path = self.path.split('?')[0]
        if path not in ('/', '/health', '/models'):
            return self._json(404, {'error': 'not found'})
        if not self._auth():
            return
        srv, cfg = self.server, self.server.cfg
        snap = srv.host.snapshot()
        if path == '/models':
            return self._json(200, {'ok': True, 'state': snap['state'], 'active': {'model': snap['model'], 'config': snap['config']},
                                    'models': srv.allow.public('model', snap['model']), 'configs': srv.allow.public('config', snap['config'])})
        m = self.meta(snap=snap)
        m.update({'backend': cfg.backend, 'state': snap['state'], 'progress': snap['progress'], 'error': snap['error'], 'features': FEATURES,
                  'searching': srv.slot.active(),
                  'limits': {'maxVisits': cfg.max_visits, 'streamMaxVisits': cfg.stream_max_visits, 'streamMaxSeconds': cfg.stream_timeout}})
        self._json(200, {'ok': True, 'alive': snap['alive'], 'bridge': m})

    def do_POST(self):
        path = self.path.split('?')[0]
        routes = {'/analyze': self._analyze, '/stream': self._stream, '/terminate': self._terminate, '/switch': self._switch}
        if path not in routes:
            return self._json(404, {'error': 'not found'})
        if not self._auth():
            return
        routes[path]()

    def _terminate(self):
        q = self._body(4096, allow_empty=True)
        if q is None:
            return
        cid = q.get('id') if isinstance(q, dict) else None
        if cid is not None and (not isinstance(cid, (str, int)) or isinstance(cid, bool)):
            return self._json(400, {'error': 'id must be a string or a number'})
        hit = self.server.slot.stop(None if cid is None else cid, 'terminated')
        self._json(200, {'ok': True, 'terminated': hit})

    def _analyze(self):
        cfg = self.server.cfg
        q = self._body()
        if q is None:
            return
        try:
            cid = q.get('id') if isinstance(q, dict) else None
            if not isinstance(cid, (str, int)) or isinstance(cid, bool):
                cid = None
            clean = sanitize(q, cfg.max_visits)
        except BadQuery as e:
            return self._json(400, {'error': str(e)[:200]})
        if not self.server.slots.acquire(timeout=min(30, cfg.timeout)):
            return self._json(429, {'error': 'too many requests in flight, try again later'})
        t0 = time.time()
        try:
            with self.server.host.use() as kg:
                qid = kg.new_id()
                d = kg.analyze(clean, qid, cfg.timeout, self._gone)
                d = dict(d)
                d['id'] = cid
                d['bridge'] = self.meta(round((time.time() - t0) * 1000))
            self._json(200, d)
        except Unavailable as e:
            self._json(503, {'error': str(e), 'state': e.state})
        except ConnectionAbortedError:
            pass
        except TimeoutError as e:
            self._json(504, {'error': str(e)})
        except Exception as e:
            self._json(502, {'error': str(e)[:200]})
        finally:
            self.server.slots.release()

    def _stream(self):
        srv, cfg = self.server, self.server.cfg
        q = self._body()
        if q is None:
            return
        try:
            cid = q.get('id') if isinstance(q, dict) else None
            if not isinstance(cid, (str, int)) or isinstance(cid, bool):
                cid = None
            clean = sanitize(q, cfg.stream_max_visits, stream=True)
        except BadQuery as e:
            return self._json(400, {'error': str(e)[:200]})
        every = clean.pop('reportDuringSearchEvery', 0.5)
        self.nd_ok = False
        t0 = time.time()
        try:
            with srv.host.use() as kg:
                qid = kg.new_id()
                s = srv.slot.begin(cid, qid)  # preempts a search that is still running
                try:
                    self._nd_start()
                    seq, end = 0, 'finished'
                    try:
                        for d in kg.stream(clean, qid, every, cfg.stream_timeout, s['cancel'], self._gone):
                            d = dict(d)
                            d['id'] = cid
                            d['bridge'] = self.meta(round((time.time() - t0) * 1000))
                            d['bridge']['seq'] = seq
                            seq += 1
                            last = d.get('noResults') or not d.get('isDuringSearch', False)
                            if last:
                                end = s['reason'] or ('timeout' if time.time() - t0 > cfg.stream_timeout else 'finished')
                                d['done'] = True
                                d['bridge']['end'] = end
                            if not self._nd(d):
                                s['cancel'].set()  # the client is gone: the generator terminates KataGo on its next tick
                    except Exception as e:
                        self._nd({'id': cid, 'error': str(e)[:200], 'done': True})
                finally:
                    srv.slot.end(s)
                    self._nd_end()
        except Unavailable as e:
            self._json(503, {'error': str(e), 'state': e.state})

    def _switch(self):
        srv = self.server
        q = self._body(4096)
        if q is None:
            return
        if not isinstance(q, dict) or set(q) - {'model', 'config'}:
            return self._json(400, {'error': 'send {"model": id} and/or {"config": id}; nothing else is accepted'})
        mid, cid = q.get('model'), q.get('config')
        try:  # validate before anything is stopped
            if mid is not None:
                srv.allow.path('model', mid)
            if cid is not None:
                srv.allow.path('config', cid)
        except BadQuery as e:
            return self._json(400, {'error': str(e)})
        if srv.host.switch_lock.locked():
            return self._json(409, {'error': 'another switch is in progress'})
        msgs = queue.Queue()
        result = {}

        def work():
            try:
                result['ok'] = srv.host.switch(mid, cid, msgs.put, srv.slot)
            except Busy as e:
                msgs.put({'state': 'error', 'error': str(e), 'done': True})
            except Exception as e:
                msgs.put({'state': 'error', 'error': str(e)[:200], 'done': True})
            msgs.put(None)

        threading.Thread(target=work, daemon=True).start()
        self._nd_start()
        while True:  # the switch always runs to its end, even if this client disconnects (a half started engine is worse)
            try:
                m = msgs.get(timeout=1.0)
            except queue.Empty:
                self._nd({'state': srv.host.progress or 'loading', 'heartbeat': True})
                continue
            if m is None:
                break
            self._nd(m)
        self._nd_end()


def make_factory(a, al, cfg_path):
    """Returns factory(model_id, config_id) -> engine. Paths come from the operator's allowlist only."""
    def factory(model_id, config_id, switching=False):
        if a.fake:
            return FakeKataGo(label=al.label('model', model_id), load_seconds=a.fake_load_seconds if switching else 0)
        mp = al.path('model', model_id)
        cp = al.path('config', config_id) if config_id else cfg_path
        if a.engine_cmd:
            cmd = [x.replace('{model}', mp).replace('{config}', cp) for x in shlex.split(a.engine_cmd)]
        else:
            cmd = [a.katago, 'analysis', '-model', mp, '-config', cp, '-override-config', 'reportAnalysisWinratesAs=BLACK']
        return KataGo(cmd)
    return factory


def build_allowlist(a):
    al = Allowlist()
    check = not a.fake
    if a.models_file:
        load_models_file(al, a.models_file, check)
    for s in a.allow_model:
        i, p = parse_pair(s)
        al.add('model', i, p, None, check)
    for s in a.allow_config:
        i, p = parse_pair(s)
        al.add('config', i, p, None, check)
    newest = None
    for d in a.models_dir:  # every network file directly inside the directory the operator named, newest first
        files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith(('.bin.gz', '.txt.gz')) and os.path.isfile(os.path.join(d, f))]
        files.sort(key=os.path.getmtime, reverse=True)
        for p in files:
            i = slug_id(p)
            if not al.has('model', i):
                al.add('model', i, p, os.path.basename(p), False)
            newest = newest or i
    default = None
    if a.fake:
        if not al.items['model']:
            al.add('model', 'fake-small', 'fake', 'FAKE small (simulated)', False)
            al.add('model', 'fake-large', 'fake', 'FAKE large (simulated)', False)
        default = next(iter(al.items['model']))
    elif a.model:
        if not os.path.isfile(a.model) and not a.engine_cmd:
            sys.exit('Model file not found: %r (--model)' % a.model)
        default = slug_id(a.model)
        if not al.has('model', default):
            al.add('model', default, a.model, os.path.basename(a.model), False)
    elif a.engine_cmd and not al.items['model']:
        al.add('model', 'engine-cmd', 'engine-cmd', 'engine-cmd', False)
        default = 'engine-cmd'
    elif newest:
        default = newest
    elif al.items['model']:
        default = next(iter(al.items['model']))
    else:
        sys.exit('No model: give --model, --allow-model or --models-file (run with --print-setup to see what is needed)')
    return al, default


def main(argv=None):
    ap = argparse.ArgumentParser(description='KataGo analysis -> HTTP bridge (token + CORS + forwards analysis queries only)')
    ap.add_argument('--katago', default=os.environ.get('KATAGO_BIN', 'katago'))
    ap.add_argument('--model', default=os.environ.get('KATAGO_MODEL', ''))
    ap.add_argument('--config', default=os.environ.get('KATAGO_CONFIG', ''), help='analysis.cfg (generated automatically if omitted)')
    ap.add_argument('--print-setup', action='store_true', help='print what you must provide (katago binary, model, optional config, port) and exit')
    ap.add_argument('--allow-model', action='append', default=[], metavar='ID=PATH', help='a network the page may switch to (repeatable); requests name the id, never the path')
    ap.add_argument('--allow-config', action='append', default=[], metavar='ID=PATH', help='a config the page may switch to (repeatable)')
    ap.add_argument('--models-dir', action='append', default=[], metavar='DIR', help='allow every *.bin.gz / *.txt.gz network directly inside DIR (repeatable); without --model the newest one is used')
    ap.add_argument('--models-file', default='', help='JSON file with {"models":[{"id","label","path"}],"configs":[...]} (relative paths are relative to the file)')
    ap.add_argument('--engine-cmd', default='', help='(for tests) use this command instead of katago; {model} and {config} are replaced by allowlisted paths')
    ap.add_argument('--fake', action='store_true', help='do not start KataGo; return fake data labeled as simulated (only for trying the UI)')
    ap.add_argument('--fake-load-seconds', type=float, default=1.5, help='(with --fake) simulated model loading time on /switch')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8787)
    ap.add_argument('--token-file', default='', help='read the token from this file (takes precedence over the KATAGO_BRIDGE_TOKEN environment variable)')
    ap.add_argument('--allow-origin', action='append', default=[], help='allowed page origin, repeatable; default localhost:8765')
    ap.add_argument('--allow-file-origin', action='store_true', help='allow pages opened from file:// (Origin: null)')
    ap.add_argument('--max-visits', type=int, default=2000, help='cap for /analyze')
    ap.add_argument('--stream-max-visits', type=int, default=20000, help='cap for /stream (the page offers "until stopped" up to this number)')
    ap.add_argument('--stream-timeout', type=int, default=900, help='wall-clock cap in seconds for one /stream search')
    ap.add_argument('--max-inflight', type=int, default=4)
    ap.add_argument('--timeout', type=int, default=90)
    ap.add_argument('--threads', type=int, default=2)
    ap.add_argument('--search-threads', type=int, default=16)
    ap.add_argument('--batch', type=int, default=32)
    ap.add_argument('--cert', default='', help='TLS certificate (PEM); giving it together with --key enables HTTPS')
    ap.add_argument('--key', default='')
    a = ap.parse_args(argv)
    if a.print_setup:
        sys.stdout.write(SETUP_TEXT)
        return

    tok = ''
    if a.token_file:
        tok = open(a.token_file, encoding='utf-8').read().strip()
    tok = tok or os.environ.get('KATAGO_BRIDGE_TOKEN', '')
    loop = a.host in ('127.0.0.1', 'localhost', '::1')
    generated = False
    if not tok:
        if not loop:
            sys.exit('Listening on a non-loopback address requires you to supply a token (KATAGO_BRIDGE_TOKEN or --token-file)')
        tok = secrets.token_urlsafe(24)
        generated = True
    if len(tok) < 16 and not loop:
        sys.exit('Token too short (need >= 16 characters)')

    try:
        al, default_model = build_allowlist(a)
    except ValueError as e:
        sys.exit('Allowlist error: %s' % e)
    cfg_path = a.config
    if not cfg_path and not a.fake:
        d = tempfile.mkdtemp(prefix='kgbridge_')
        cfg_path = os.path.join(d, 'analysis_bridge.cfg')
        with open(cfg_path, 'w', encoding='utf-8') as f:
            f.write(GEN_CFG.format(logdir=d.replace('\\', '/'), nat=a.threads, nst=a.search_threads, bs=a.batch))
    cfg = Cfg()
    cfg.token = tok
    cfg.fake = a.fake
    cfg.max_visits = a.max_visits
    cfg.stream_max_visits = a.stream_max_visits
    cfg.stream_timeout = a.stream_timeout
    cfg.timeout = a.timeout
    cfg.origins = set(a.allow_origin) or {'http://localhost:8765', 'http://127.0.0.1:8765'}
    cfg.allow_file = a.allow_file_origin
    cfg.model_label = lambda mid: al.label('model', mid)
    cfg.backend = 'Fake' if a.fake else ('unknown' if a.engine_cmd else detect_backend(a.katago))

    host = EngineHost(make_factory(a, al, cfg_path), al, default_model)
    host.start()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    srv.cfg, srv.host, srv.allow = cfg, host, al
    srv.slots = threading.BoundedSemaphore(a.max_inflight)
    srv.slot = SearchSlot()
    scheme = 'http'
    if a.cert and a.key:
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(a.cert, a.key)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        scheme = 'https'
    snap = host.snapshot()
    print('KataGo bridge started: %s://%s:%d   (KataGo %s, backend %s%s)' % (scheme, a.host, a.port, snap['info'].get('version'), cfg.backend, ', FAKE DATA!' if a.fake else ''))
    print('Active model: %s   (switchable: %s)' % (default_model, ', '.join(al.items['model'])))
    print('Allowed origins:', ', '.join(sorted(cfg.origins)) + ('  + file://' if cfg.allow_file else ''))
    if generated:
        print('Random token for this run (shown only once; paste it into the compute settings of the page):', tok)
    if not loop and scheme == 'http':
        print('WARNING: listening on %s without TLS, so the token and game records are sent in clear text. Use SSH port forwarding (-L), --cert/--key, or an HTTPS reverse proxy in front.' % a.host, file=sys.stderr)
    sys.stdout.flush()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if host.eng is not None:
            host.eng.close()


if __name__ == '__main__':
    main()
