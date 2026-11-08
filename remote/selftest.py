#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-test that needs no GPU and no KataGo: uses a "fake engine" (Black's-perspective output, matching reportAnalysisWinratesAs=BLACK) to verify
  1) analyze_remote.py: it runs pipeline/analyze2.py, so the output must pass treesync.check_analysis as it is (tree fingerprint, side-to-move
     perspective, complete flag); region / branch points / forced evaluation and the skip of finished groups;
  2) katago_bridge.py: query validation, token / CORS / HTTP handling on in-memory streams;
  3) katago_bridge.py on a real loopback socket (127.0.0.1, random port, closed when the test ends): the NDJSON stream over a chunked response, terminate,
     preemption, client disconnect, the operator's model allowlist, /switch with progress and rollback, /health, log hygiene.
The deeper tests of the cloud batch path (resume after a kill, notebook cells, packing) are in tests/test_remote_batch.py (Docker, see tests/README.md).
Run:  python selftest.py
Note: the fake engine's numbers are made up and only exercise the pipeline logic; they say nothing about Go.
"""
import io, json, os, subprocess, sys, tempfile, argparse, threading, time, http.client
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
L = 'ABCDEFGHJKLMNOPQRST'
TOKEN = 'T' * 24


# ----------------------------------------------------------------------------- fake engine (KataGo analysis protocol, Black's perspective)
def respond(q):
    occ = {loc for _, loc in q.get('initialStones', [])} | {loc for _, loc in q['moves'] if loc != 'pass'}
    t = ('W' if q['moves'][-1][0] == 'B' else 'B') if q['moves'] else q.get('initialPlayer', 'B')
    allow = next((a['moves'] for a in q.get('allowMoves', []) if a['player'] == t), None)
    if allow is None:   # the perspective self test of analyze2 has no allowMoves: every point of the board is allowed
        allow = [L[c] + str(r) for c in range(19) for r in range(1, 20)]
    free = [m for m in allow if m not in occ][:6]
    vis = [150, 60, 30, 12, 6, 3]
    infos = []
    for i, m in enumerate(free):  # Black's perspective: Black leads by about 3 points whoever is to move (so with W to move the side-to-move score must be negative)
        infos.append({'move': m, 'visits': vis[i], 'order': i, 'scoreLead': 3.0 + 0.1 * i, 'winrate': 0.6 - 0.01 * i,
                      'prior': 0.3 / (i + 1), 'pv': [m] + free[i + 1:i + 4]})
    sel = q['id'] == 'selftest'   # handicap position with White to move: a real engine says Black is far ahead
    return {'id': q['id'], 'turnNumber': len(q['moves']),
            'rootInfo': {'currentPlayer': t, 'scoreLead': 30.0 if sel else 3.0, 'winrate': 0.97 if sel else 0.6, 'visits': q['maxVisits']}, 'moveInfos': infos}


def fake_engine():
    """Speaks the KataGo analysis protocol on stdin/stdout: query_version, queries (with reportDuringSearchEvery streaming) and terminate."""
    out_lock, stops = threading.Lock(), {}
    log = os.environ.get('KGTEST_LOG')
    model = ''
    for flag in ('--model', '-model'):
        if flag in sys.argv:
            model = os.path.basename(sys.argv[sys.argv.index(flag) + 1])
    if 'bad' in model:  # a network that cannot be loaded (exercises the rollback of /switch)
        sys.stderr.write('cannot load model\n')
        sys.exit(3)

    def emit(o):
        with out_lock:
            print(json.dumps(o), flush=True)

    def note(s):
        if log:
            with open(log, 'a') as f:
                f.write(s + '\n')

    def search(q):
        ev = stops[q['id']] = threading.Event()
        every, total = q.get('reportDuringSearchEvery'), q['maxVisits']
        if not every:
            emit(respond(q))
            return
        visits = 0
        while True:
            ev.wait(every)
            stopped = ev.is_set()
            visits = min(total, visits + max(1, total // 10))
            fin = visits >= total or stopped
            d = respond(q)
            d['isDuringSearch'] = not fin
            d['rootInfo']['visits'] = visits
            emit(d)
            if fin:
                note('end %s visits=%d stopped=%s' % (q['id'], visits, stopped))
                return

    for line in sys.stdin:
        q = json.loads(line)
        a = q.get('action')
        if a == 'query_version':
            emit({'id': q['id'], 'version': 'SELFTEST-FAKE:' + model, 'git_hash': '-'})
        elif a == 'terminate':
            note('terminate %s' % q['terminateId'])
            if q['terminateId'] in stops:
                stops[q['terminateId']].set()
            emit(q)
        else:
            threading.Thread(target=search, args=(q,), daemon=True).start()


# ----------------------------------------------------------------------------- synthetic n.json
def synth_tree():
    k = lambda c, r: r * 18 + c
    pos = []
    for c in range(0, 5):
        for r in range(9, 18):
            if len(pos) < 40:
                pos.append(('B' if (c + r) % 2 else 'W') + str(k(c, r)))
    pos.append('B' + str(k(16, 2)))  # one far-away stone outside the region -> triggers the "_0" control query
    mk = lambda mv, par, ch, dead=False, setup=False, p='': {'dead': dead, 'mv': mv, 'par': par, 'ch': ch, 'setup': setup, 'pos': p, 'v': [], 'n': 0}
    tree = [
        mk(None, 0, [1, 2, 3], setup=True, p=' '.join(pos)),
        mk([k(5, 12), 'B'], 0, [4, 5]),
        mk([k(6, 13), 'B'], 0, []),
        mk([k(7, 14), 'B'], 0, [], dead=True),
        mk([k(6, 12), 'W'], 1, []),
        mk([k(5, 13), 'W'], 1, [6, 7]),
        mk([k(6, 14), 'B'], 5, []),
        mk([k(7, 13), 'B'], 5, []),
    ]
    for i, n in enumerate(tree):
        n['id'] = i   # the pipeline's tree fingerprint and analyze2 index the list by id
    return tree


def check(cond, msg):
    print(('  OK   ' if cond else '  FAIL ') + msg)
    if not cond:
        check.bad += 1


check.bad = 0


def test_pipeline():
    print('[1] analyze_remote.py (fake engine) around pipeline/analyze2.py')
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'pipeline'))
    import treesync
    d = tempfile.mkdtemp(prefix='kgtest_')
    ind, outd = os.path.join(d, 'in'), os.path.join(d, 'out')
    os.makedirs(ind)
    # Non-ASCII group name on purpose (the real group names are Chinese): "g_" + "test-fake-data" in Chinese, written as escapes
    nfile = os.path.join(ind, 'g_测试-假数据.n.json')
    tree = synth_tree()
    json.dump(tree, open(nfile, 'w'))
    eng = '"%s" "%s" --fake-engine' % (sys.executable.replace('\\', '/'), os.path.abspath(__file__).replace('\\', '/'))
    cmd = [sys.executable, os.path.join(HERE, 'analyze_remote.py'), '--in', ind, '--out', outd, '--engine-cmd', eng, '--window', '2']
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    check(r.returncode == 0, 'analyze_remote exit code 0' + ('' if r.returncode == 0 else '\n' + r.stdout[-600:] + r.stderr[-600:]))
    outp = os.path.join(outd, 'g_测试-假数据.a2.json')
    res = json.load(open(outp))
    meta = res.pop('_meta')
    check(treesync.check_analysis(tree, dict(res, _meta=meta)) == ('ok', ''), 'the output passes treesync.check_analysis as it is (fingerprint, schema, perspective, complete): no wq.py stamp needed')
    check(meta['persp'] == 'stm' and meta['report_as'] == 'BLACK' and meta['report_as_source'] == 'selftest', 'meta says side to move, and the live self test found that the engine reports Black')
    check(set(res) >= {'0', '1', '5', '0_0', '1_0', '5_0'}, 'contains the 3 branch points and the out-of-region control queries: ' + ','.join(sorted(res)))
    check(all(a.get('turn') in ('B', 'W') for a in res.values()), 'every result has a turn')
    ok = all((a['score'] > 0) == (a['turn'] == 'B') and all((c['s'] > 0) == (a['turn'] == 'B') for c in a['cand']) for a in res.values())
    check(ok, "Black's perspective -> side to move: score is negative when W is to move and positive when B is")
    forced = [c for a in res.values() for c in a['cand'] if c.get('f')]
    check(len(forced) > 0 and all(c['p'] == -1 and c['v'] == 100 for c in forced), "the teacher's moves were evaluated by force (%d entries, f=1,p=-1,v=100)" % len(forced))
    check(all(len(c['pv']) <= 8 for a in res.values() for c in a['cand']), 'pv has at most 8 moves')
    check(os.path.exists(outp[:-5] + '.meta.json'), 'wrote the .a2.meta.json side file')
    r2 = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    check('skip (exists, valid)' in r2.stdout, 'a second run skips finished groups automatically (resume)')


# ----------------------------------------------------------------------------- bridge: helpers
class _Conn:
    def __init__(self, data):
        self.inb, self.out = io.BytesIO(data), io.BytesIO()

    def makefile(self, mode, bufsize=-1):
        return self.inb if 'r' in mode else self.out

    def sendall(self, b):
        self.out.write(b)

    def settimeout(self, t):
        pass


def _raises(kb, q, **kw):
    try:
        kb.sanitize(q, **kw)
    except kb.BadQuery:
        return True
    return False


def make_cfg(kb, **over):
    cfg = kb.Cfg()
    cfg.token, cfg.fake, cfg.max_visits, cfg.timeout = TOKEN, False, 2000, 20
    cfg.stream_max_visits, cfg.stream_timeout, cfg.backend = 20000, 60, 'Eigen'
    cfg.origins, cfg.allow_file = {'http://localhost:8765'}, False
    cfg.__dict__.update(over)
    return cfg


def make_server(kb, workdir, fake=False, real_socket=False, stream_timeout=60):
    """Builds the same object graph as main(): allowlist (two good networks, one that cannot load), EngineHost, SearchSlot."""
    al = kb.Allowlist()
    for i in ('alpha', 'beta', 'bad-net'):
        p = os.path.join(workdir, i + '.bin.gz')
        open(p, 'wb').write(b'x' * (1000 if i == 'alpha' else 2000))
        al.add('model', i, p, 'Net ' + i)
    cfg = make_cfg(kb, fake=fake, stream_timeout=stream_timeout)
    cfg.model_label = lambda mid: al.label('model', mid)
    log = os.path.join(workdir, 'engine.log')
    os.environ['KGTEST_LOG'] = log
    if fake:
        factory = lambda m, c, sw=False: kb.FakeKataGo(label=m, rate=2000)
    else:
        cmdt = [sys.executable, os.path.abspath(__file__), '--fake-engine', '--model', '{model}']
        def factory(m, c, sw=False):
            if sw:
                time.sleep(0.6)  # a switch takes a moment, so the "second switch while one runs" case is not a race
            return kb.KataGo([x.replace('{model}', al.path('model', m)) for x in cmdt])
    host = kb.EngineHost(factory, al, 'alpha')
    host.start()

    class Srv:
        pass

    srv = Srv()
    srv.cfg, srv.host, srv.allow, srv.slots, srv.slot = cfg, host, al, threading.BoundedSemaphore(2), kb.SearchSlot()
    if not real_socket:
        return srv, None, log
    srv = kb.ThreadingHTTPServer(('127.0.0.1', 0), kb.Handler)
    srv.daemon_threads = True
    srv.cfg, srv.host, srv.allow, srv.slots, srv.slot = cfg, host, al, threading.BoundedSemaphore(2), kb.SearchSlot()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1], log


def wait_for(fn, secs=6.0, step=0.05):
    t0 = time.time()
    while time.time() - t0 < secs:
        v = fn()
        if v:
            return v
        time.sleep(step)
    return fn()


class Client:
    """Tiny http.client wrapper for the real-socket tests."""

    def __init__(self, port, token=TOKEN, origin='http://localhost:8765'):
        self.port, self.token, self.origin = port, token, origin

    def open(self, method, path, body=None, token=None, raw=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        h = {'Origin': self.origin}
        tk = self.token if token is None else token
        if tk:
            h['Authorization'] = 'Bearer ' + tk
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if data is not None or method == 'POST':
            h['Content-Type'] = 'application/json'
        c.request(method, path, body=data, headers=h)
        return c, c.getresponse()

    def json(self, method, path, body=None, **kw):
        c, r = self.open(method, path, body, **kw)
        raw = r.read()
        c.close()
        return r.status, (json.loads(raw) if raw else None), raw

    def stream(self, path, body, **kw):
        c, r = self.open('POST', path, body, **kw)
        return c, r

    @staticmethod
    def lines(r):
        while True:
            ln = r.readline()
            if not ln:
                return
            yield json.loads(ln)


def q_body(visits=3000, every=0.3, cid='s1'):
    return {'id': cid, 'initialStones': [['B', 'D4']], 'moves': [['W', 'Q16']], 'maxVisits': visits, 'analyzeTurns': [1], 'reportDuringSearchEvery': every,
            'allowMoves': [{'player': 'B', 'moves': ['C3', 'D3', 'E3', 'F3', 'G3'], 'untilDepth': 40}]}


# ----------------------------------------------------------------------------- bridge: tests
def test_bridge():
    print('[2] katago_bridge.py (in-memory HTTP, fake engine subprocess)')
    import katago_bridge as kb
    q = {'id': 1, 'initialStones': [['B', 'D4']], 'moves': [['W', 'Q16'], ['B', 'pass']], 'maxVisits': 50, 'analyzeTurns': [2],
         'allowMoves': [{'player': 'B', 'moves': ['C3', 'D3'], 'untilDepth': 40}]}
    c = kb.sanitize(q)
    check(c['maxVisits'] == 50 and 'id' not in c and c['komi'] == 6.5 and c['rules'] == 'japanese', 'sanitize accepts a valid query and fills in defaults')
    bad = [dict(q, hack=1), dict(q, maxVisits=99999), dict(q, moves=[['B', 'Z99']]), dict(q, boardXSize=25),
           dict(q, analyzeTurns=[5]), dict(q, overrideSettings={'a': 1}), dict(q, rules='x; rm -rf')]
    check(all(_raises(kb, b) for b in bad), 'sanitize rejects 7 kinds of invalid query (unknown field / huge visits / coordinate / board / turn / overrideSettings / rules)')
    check(_raises(kb, dict(q, reportDuringSearchEvery=0.5)), 'reportDuringSearchEvery is rejected on /analyze')
    ok_stream = kb.sanitize(dict(q, reportDuringSearchEvery=0.5, maxVisits=9000), 20000, stream=True)
    check(ok_stream['reportDuringSearchEvery'] == 0.5 and ok_stream['maxVisits'] == 9000, 'reportDuringSearchEvery and a larger maxVisits are accepted on /stream')
    check(all(_raises(kb, dict(q, reportDuringSearchEvery=v), stream=True) for v in (0, 0.01, 99, 'x', True)), 'reportDuringSearchEvery outside 0.1..5 seconds is rejected')
    check(_raises(kb, dict(q, model='/etc/passwd'), stream=True) and _raises(kb, dict(q, config='x'), stream=True), 'a query cannot carry a model or config field')

    work = tempfile.mkdtemp(prefix='kgbridge_t_')
    srv, _, log = make_server(kb, work)
    cfg = srv.cfg
    check(srv.host.snapshot()['info'].get('version') == 'SELFTEST-FAKE:alpha.bin.gz', 'KataGo subprocess handshake (query_version)')

    def http(method, path, headers=None, body=None):
        h = {'Host': 'x'}
        h.update(headers or {})
        raw = body if isinstance(body, bytes) else (json.dumps(body).encode() if body is not None else b'')
        if raw:
            h['Content-Length'] = str(len(raw))
        data = ('%s %s HTTP/1.0\r\n' % (method, path) + ''.join('%s: %s\r\n' % kv for kv in h.items()) + '\r\n').encode() + raw
        req = _Conn(data)
        kb.Handler(req, ('127.0.0.1', 1), srv)
        head, _, b = req.out.getvalue().partition(b'\r\n\r\n')
        lines = head.decode().split('\r\n')
        hd = {x.split(': ', 1)[0].lower(): x.split(': ', 1)[1] for x in lines[1:] if ': ' in x}
        return int(lines[0].split()[1]), hd, (json.loads(b) if b else None)

    ok_o = {'Origin': 'http://localhost:8765'}
    auth = dict(ok_o, Authorization='Bearer ' + cfg.token)
    s, h, _ = http('OPTIONS', '/analyze', dict(ok_o, **{'Access-Control-Request-Private-Network': 'true'}))
    check(s == 204 and h.get('access-control-allow-origin') == 'http://localhost:8765' and h.get('access-control-allow-private-network') == 'true', 'CORS preflight (including Private-Network)')
    s, h, _ = http('OPTIONS', '/analyze', {'Origin': 'http://evil.example'})
    check(s == 204 and 'access-control-allow-origin' not in h, 'preflight from an unknown origin gets no Allow-Origin')
    for p in ('/health', '/models'):
        s, _, _ = http('GET', p, ok_o)
        check(s == 401, 'no token -> 401 on GET ' + p)
    s, _, _ = http('GET', '/health', dict(ok_o, Authorization='Bearer wrong'))
    check(s == 401, 'wrong token -> 401')
    s, _, b = http('GET', '/health', auth)
    br = b['bridge']
    check(s == 200 and br['winratesAs'] == 'BLACK' and b['alive'], '/health with token -> 200, declares winratesAs=BLACK')
    check(br['backend'] == 'Eigen' and br['modelId'] == 'alpha' and br['katago']['version'].startswith('SELFTEST-FAKE') and br['state'] == 'ready',
          '/health reports backend, model id, KataGo version and state')
    check(set(br['features']) >= {'stream', 'terminate', 'models', 'switch'} and br['limits']['streamMaxVisits'] == 20000, '/health lists features and limits')
    s, _, _ = http('GET', '/health', dict(auth, Origin='http://evil.example'))
    check(s == 403, 'correct token but origin not in the allowlist -> 403')
    body = {'id': 'x1', 'initialStones': [['B', 'D4']], 'moves': [['W', 'Q16']], 'maxVisits': 30, 'analyzeTurns': [1],
            'allowMoves': [{'player': 'B', 'moves': ['C3', 'D3', 'E3'], 'untilDepth': 40}]}
    s, _, b = http('POST', '/analyze', dict(auth, **{'Content-Type': 'application/json'}), body)
    check(s == 200 and b['id'] == 'x1' and b['rootInfo']['currentPlayer'] == 'B' and b['moveInfos'] and b['bridge']['ms'] >= 0, '/analyze with a valid query -> 200, echoes the id, includes bridge metadata')
    s, _, _ = http('POST', '/analyze', auth, dict(body, maxVisits=10 ** 6))
    check(s == 400, 'visits above the cap -> 400')
    s, _, _ = http('POST', '/analyze', auth, b'{not json')
    check(s == 400, 'malformed JSON -> 400')
    s, _, _ = http('POST', '/analyze', auth, dict(body, extra='x'))
    check(s == 400, 'unknown field -> 400')
    s, _, b = http('GET', '/models', auth)
    raw = json.dumps(b)
    check(s == 200 and [m['id'] for m in b['models']] == ['alpha', 'beta', 'bad-net'] and b['models'][0]['active'] and not b['models'][1]['active'],
          '/models lists the allowlisted networks and marks the active one')
    check(work not in raw and '.bin.gz' not in raw and 'path' not in raw, '/models never reveals a file path')
    for pth in ('/switch', '/stream', '/terminate'):
        s, _, _ = http('POST', pth, ok_o, {})
        check(s == 401, 'no token -> 401 on POST ' + pth)
    srv.host.eng.close()

    # ---- helper functions
    print('[2b] allowlist, backend detection, setup text')
    check(kb.slug_id('kata1-b18c384nbt-s9996604416-d4316597426.bin.gz') == 'kata1-b18c384nbt-s9996604416-d4316597426' and kb.slug_id('/x/a b$c.txt.gz') == 'a-b-c',
          'slug_id makes safe ids from file names')
    al = kb.Allowlist()
    for bad_id in ('', '../x', 'a b', 'x' * 49, None, 5):
        try:
            al.add('model', bad_id, 'p', None, False)
            check(False, 'bad id accepted: %r' % (bad_id,))
        except ValueError:
            pass
    check(not al.items['model'], 'ids with path separators, spaces, empty or too long are refused')
    try:
        al.add('model', 'missing', os.path.join(work, 'nope.bin.gz'))
        check(False, 'a missing file was accepted')
    except ValueError:
        check(True, 'an allowlisted file that does not exist is refused at startup')
    mf = os.path.join(work, 'models.json')
    json.dump({'models': [{'id': 'm1', 'label': 'One', 'path': 'alpha.bin.gz'}], 'configs': [{'id': 'c1', 'path': 'alpha.bin.gz'}]}, open(mf, 'w'))
    al2 = kb.Allowlist()
    kb.load_models_file(al2, mf)
    check(al2.path('model', 'm1') == os.path.join(work, 'alpha.bin.gz') and al2.has('config', 'c1'), 'models file: relative paths are relative to the JSON file; models and configs both load')
    try:
        al2.path('model', '../../etc/passwd')
        check(False, 'a path was accepted as a model id')
    except kb.BadQuery:
        check(True, 'a path as an id is refused (only allowlisted ids resolve)')
    d3, t3 = tempfile.mkdtemp(prefix='kgmd_'), time.time()
    for i, n in enumerate(('old.bin.gz', 'new.bin.gz', 'notes.txt')):
        pth = os.path.join(d3, n)
        open(pth, 'wb').write(b'x')
        os.utime(pth, (t3 + i * 10, t3 + i * 10))
    os.utime(os.path.join(d3, 'old.bin.gz'), (t3 - 100, t3 - 100))
    ns = argparse.Namespace(fake=False, models_file='', allow_model=[], allow_config=[], models_dir=[d3], model='', engine_cmd='')
    al3, dflt = kb.build_allowlist(ns)
    check(sorted(al3.items['model']) == ['new', 'old'] and dflt == 'new', '--models-dir allows only the network files directly inside the directory; without --model the newest one is the default')
    cases = {'KataGo v1.18.2\nUsing OpenCL backend\n': 'OpenCL', 'Using CUDA backend\nCompiled with CUDA version 12.1': 'CUDA', 'Using TensorRT backend': 'TensorRT',
             'Using Eigen(CPU) backend': 'Eigen', 'Using Metal backend': 'Metal', 'Using ROCm backend': 'ROCm', 'Using dummy backend': 'unknown', 'garbage': 'unknown', '': 'unknown'}
    check(all(kb.backend_from_text(k) == v for k, v in cases.items()), 'backend_from_text understands the `katago version` lines (OpenCL, CUDA, TensorRT, Eigen, Metal, ROCm; otherwise unknown)')

    class R:
        stdout = 'KataGo v1\nUsing OpenCL backend\n'

    check(kb.detect_backend('katago', run=lambda *a, **k: R()) == 'OpenCL', 'detect_backend runs only `katago version`')
    seen = []
    kb.detect_backend('katago', run=lambda cmd, **k: seen.append(cmd) or R())
    check(seen == [['katago', 'version']], 'detect_backend does not load a network (command is exactly `katago version`)')

    def boom(*a, **k):
        raise OSError('no such file')

    check(kb.detect_backend('nope', run=boom) == 'unknown', 'detect_backend returns unknown when the binary cannot be run')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'katago_bridge.py'), '--print-setup'], capture_output=True, text=True)
    lines = [x for x in r.stdout.splitlines() if x.strip()]
    check(r.returncode == 0 and r.stdout == kb.SETUP_TEXT and len(lines) == 5 and all(w in r.stdout for w in ('katago', 'model', 'config', 'port')),
          '--print-setup prints exactly the four items (katago binary, model, optional config, port) and nothing else')
    src = open(os.path.join(HERE, 'katago_bridge.py'), encoding='utf-8').read()
    check('hmac.compare_digest' in src and "self.headers.get('Authorization'" in src and 'parse_qs' not in src and 'urlparse' not in src,
          'the token is compared with hmac.compare_digest and is read from the Authorization header only (the URL is never parsed for it)')


def test_sockets():
    print('[3] katago_bridge.py on a real loopback socket (NDJSON stream, terminate, switch)')
    import katago_bridge as kb
    work = tempfile.mkdtemp(prefix='kgbridge_s_')
    srv, port, log = make_server(kb, work, real_socket=True)
    cl = Client(port)
    host, slot = srv.host, srv.slot

    # ---- streaming
    c, r = cl.stream('/stream', q_body(visits=600, every=0.1))
    msgs = list(Client.lines(r))
    c.close()
    ct, te = r.getheader('Content-Type'), r.getheader('Transfer-Encoding')
    check(r.status == 200 and te == 'chunked' and ct.startswith('application/x-ndjson'), '/stream answers 200 with Transfer-Encoding: chunked and application/x-ndjson')
    vis = [m['rootInfo']['visits'] for m in msgs]
    check(len(msgs) >= 4 and vis == sorted(vis) and vis[-1] == 600, 'one line per update, visits never decrease (%d updates, last %d visits)' % (len(msgs), vis[-1]))
    check(all(m['isDuringSearch'] for m in msgs[:-1]) and msgs[-1]['isDuringSearch'] is False and msgs[-1].get('done') is True and not any(m.get('done') for m in msgs[:-1]),
          'only the final line has done=true (and isDuringSearch=false)')
    check(all(m['bridge']['winratesAs'] == 'BLACK' and m['id'] == 's1' for m in msgs) and msgs[-1]['bridge']['end'] == 'finished', 'every line declares winratesAs=BLACK and echoes the id; the last says end=finished')
    check(r.getheader('Connection') == 'close' and r.getheader('Access-Control-Allow-Origin') == 'http://localhost:8765', 'the stream is CORS-enabled and not kept alive')
    s, b, _ = cl.json('POST', '/stream', dict(q_body(), maxVisits=10 ** 6))
    check(s == 400, '/stream: visits above the stream cap -> 400 (a normal JSON error, not a stream)')
    s, b, _ = cl.json('POST', '/stream', dict(q_body(), model='alpha'))
    check(s == 400, '/stream: a model field in the query -> 400')
    s, _, _ = cl.json('POST', '/stream', q_body(), token='nope')
    check(s == 401, '/stream: wrong token -> 401')
    s, b, _ = cl.json('GET', '/health')
    check(b['bridge']['searching'] is False, '/health says no search is running after a finished stream')

    # ---- terminate
    got = []
    c, r = cl.stream('/stream', q_body(visits=20000, every=0.3, cid='t1'))
    it = Client.lines(r)
    got.append(next(it))
    check(wait_for(lambda: cl.json('GET', '/health')[1]['bridge']['searching']), '/health says a search is running while the stream is open')
    s, b, _ = cl.json('POST', '/terminate', {'id': 'other'})
    check(s == 200 and b['terminated'] is False, '/terminate with another id does not stop the search')
    s, b, _ = cl.json('POST', '/terminate', {'id': 't1'})
    check(s == 200 and b['terminated'] is True, '/terminate with the search id stops it')
    rest = list(it)
    c.close()
    check(rest and rest[-1].get('done') is True and rest[-1]['bridge']['end'] == 'terminated' and rest[-1]['isDuringSearch'] is False,
          'the stream ends with a final partial result marked end=terminated')
    check(wait_for(lambda: 'terminate br' in open(log).read()), 'KataGo received a terminate action (the GPU search really stops)')
    s, b, _ = cl.json('POST', '/terminate')
    check(s == 200 and b['terminated'] is False, '/terminate with nothing running is harmless (terminated=false, empty body accepted)')

    # ---- client disconnect
    open(log, 'w').close()
    c, r = cl.stream('/stream', q_body(visits=20000, every=0.3, cid='d1'))
    next(Client.lines(r))
    r.close()  # hang up without reading the rest
    c.close()
    check(wait_for(lambda: not cl.json('GET', '/health')[1]['bridge']['searching'], 6), 'after the client disconnects the search slot is free again')
    check(wait_for(lambda: 'terminate br' in open(log).read(), 6), 'after the client disconnects KataGo is told to terminate the search')

    # ---- one active search: a new one preempts the old one
    c1, r1 = cl.stream('/stream', q_body(visits=20000, every=0.3, cid='A'))
    it1 = Client.lines(r1)
    next(it1)
    c2, r2 = cl.stream('/stream', q_body(visits=20000, every=0.3, cid='B'))
    it2 = Client.lines(r2)
    first2 = next(it2)
    tail1 = list(it1)
    c1.close()
    check(tail1 and tail1[-1].get('done') and tail1[-1]['bridge']['end'] == 'preempted', 'a second stream preempts the first (one active search per token): first ends with end=preempted')
    check(first2['id'] == 'B' and not first2.get('done'), 'the second stream keeps running')
    cl.json('POST', '/terminate', {'id': 'B'})
    list(it2)
    c2.close()

    # ---- time cap
    srv.cfg.stream_timeout = 1
    c, r = cl.stream('/stream', q_body(visits=20000, every=0.4, cid='tc'))
    last = list(Client.lines(r))[-1]
    c.close()
    srv.cfg.stream_timeout = 60
    check(last.get('done') and last['bridge']['end'] == 'timeout', 'a search is ended by the wall-clock cap (end=timeout)')

    # ---- models and switch
    s, b, raw = cl.json('GET', '/models')
    check(s == 200 and b['active']['model'] == 'alpha' and work.encode() not in raw, '/models over the socket: active=alpha, no path in the body')
    for bad in ({'model': '../../etc/passwd'}, {'model': 'nope'}, {'model': 5}, {'model': 'alpha', 'path': '/etc/passwd'}, {'config': 'x'}, ['alpha']):
        s, b, _ = cl.json('POST', '/switch', bad)
        check(s == 400, '/switch refuses %r (400, nothing is restarted)' % (bad,))
    s, b, _ = cl.json('GET', '/health')
    check(b['bridge']['modelId'] == 'alpha' and b['bridge']['state'] == 'ready', 'a refused switch leaves the engine untouched')

    c, r = cl.stream('/stream', q_body(visits=20000, every=0.3, cid='sw'))
    it = Client.lines(r)
    next(it)
    sc, sr = cl.open('POST', '/switch', {'model': 'beta'})
    states = [m['state'] for m in Client.lines(sr)]
    sc.close()
    tail = list(it)
    c.close()
    check(sr.status == 200 and states[0] == 'stopping' and 'loading' in states and states[-1] == 'ready', '/switch streams progress: %s' % ' > '.join(states))
    check(tail and tail[-1].get('done') and tail[-1]['bridge']['end'] == 'switch', 'a running search is ended by /switch (end=switch)')
    s, b, _ = cl.json('GET', '/health')
    check(b['bridge']['modelId'] == 'beta' and b['bridge']['katago']['version'].endswith('beta.bin.gz') and b['bridge']['state'] == 'ready', '/health shows the new model id and a restarted KataGo')
    s, b, _ = cl.json('GET', '/models')
    check([m['id'] for m in b['models'] if m['active']] == ['beta'], '/models marks beta as active')
    s, b, _ = cl.json('POST', '/analyze', {'id': 1, 'moves': [['W', 'Q16']], 'maxVisits': 20, 'allowMoves': [{'player': 'B', 'moves': ['C3', 'D3'], 'untilDepth': 40}]})
    check(s == 200 and b['bridge']['modelId'] == 'beta', '/analyze works on the new engine')

    sc, sr = cl.open('POST', '/switch', {'model': 'bad-net'})
    states = [m for m in Client.lines(sr)]
    sc.close()
    check(states[-1]['state'] == 'failed' and 'rollback' in [m['state'] for m in states] and states[-1].get('error'), 'a network that cannot load is reported (rollback, failed)')
    s, b, _ = cl.json('GET', '/health')
    check(b['bridge']['modelId'] == 'beta' and b['bridge']['state'] == 'ready' and b['alive'], 'after the failed switch the previous network is running again')
    s, b, _ = cl.json('POST', '/analyze', {'id': 2, 'moves': [['W', 'Q16']], 'maxVisits': 20, 'allowMoves': [{'player': 'B', 'moves': ['C3'], 'untilDepth': 40}]})
    check(s == 200, '/analyze works after the rollback')

    # two switches at once: the second is refused while the first runs
    res = []
    t = threading.Thread(target=lambda: res.append(list(Client.lines(cl.open('POST', '/switch', {'model': 'alpha'})[1]))))
    t.start()
    wait_for(lambda: host.switch_lock.locked(), 3)
    s, b, _ = cl.json('POST', '/switch', {'model': 'beta'})
    t.join()
    check(s == 409, 'a switch while another one runs is refused (409)')
    s, b, _ = cl.json('GET', '/health')
    check(b['bridge']['modelId'] == 'alpha' and b['bridge']['state'] == 'ready', 'the first switch finished normally')

    # ---- log hygiene: no token, no query string
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        cl.json('GET', '/health?token=' + TOKEN)
        cl.json('GET', '/health', token='wrong-secret-xyz')
        time.sleep(0.2)
    logtxt = buf.getvalue()
    check(logtxt.strip() != '' and TOKEN not in logtxt and 'wrong-secret-xyz' not in logtxt and 'token=' not in logtxt, 'the request log shows method, path and status only (no token, no query string)')
    host.eng.close()
    srv.shutdown()

    print('[3b] --fake engine streaming')
    work2 = tempfile.mkdtemp(prefix='kgbridge_f_')
    srv2, port2, _ = make_server(kb, work2, fake=True, real_socket=True)
    cl2 = Client(port2)
    c, r = cl2.stream('/stream', q_body(visits=2000, every=0.1, cid='f1'))
    msgs = list(Client.lines(r))
    c.close()
    vis = [m['rootInfo']['visits'] for m in msgs]
    check(len(msgs) >= 3 and vis == sorted(vis) and msgs[-1].get('done') and msgs[-1]['bridge']['fake'] is True, 'fake engine: growing visits, final done=true, labeled fake (%d updates)' % len(msgs))
    check(all(m['moveInfos'] and m['moveInfos'][0]['order'] == 0 for m in msgs), 'fake engine: moveInfos are ordered best first like KataGo')
    s, b, _ = cl2.json('GET', '/health')
    check(b['bridge']['fake'] is True and b['bridge']['katago']['version'] == 'FAKE', 'fake engine: /health says fake')
    srv2.shutdown()


def test_launcher():
    print('[4] start_bridge.sh in a temporary HOME with a pretend KataGo (a shell wrapper around the fake engine)')
    import shutil, socket, stat
    if os.name != 'posix' or not shutil.which('bash'):
        print('  skip (needs bash)')
        return
    sh = os.path.join(HERE, 'start_bridge.sh')
    empty = tempfile.mkdtemp(prefix='kghome_e_')
    env0 = dict(os.environ, HOME=empty, KATAGO_BRIDGE_TOKEN=TOKEN)
    for k in ('KATAGO_BIN', 'KATAGO_MODEL', 'KATAGO_CONFIG', 'KATAGO_MODELS_DIR'):
        env0.pop(k, None)
    r = subprocess.run(['bash', sh, '--print-setup'], capture_output=True, text=True, env=env0)
    import katago_bridge as kb
    check(r.returncode == 0 and r.stdout == kb.SETUP_TEXT, 'start_bridge.sh --print-setup prints the same four items')
    r = subprocess.run(['bash', sh], capture_output=True, text=True, env=env0)
    check(r.returncode == 2 and 'KataGo executable not found' in r.stderr and 'Network file' in r.stderr and 'You provide exactly these' in r.stderr,
          'nothing found -> exit code 2, says what is missing and prints the four items')
    home = tempfile.mkdtemp(prefix='kghome_')
    kd = os.path.join(home, 'katago')
    os.makedirs(kd)
    wrapper = os.path.join(kd, 'katago')
    open(wrapper, 'w').write('#!/bin/sh\nif [ "$1" = version ]; then printf "KataGo v9.9.9\\nUsing OpenCL backend\\n"; exit 0; fi\n'
                             'm=; while [ $# -gt 0 ]; do [ "$1" = -model ] && m="$2"; shift; done\nexec "%s" "%s" --fake-engine --model "$m"\n' % (sys.executable, os.path.abspath(__file__)))
    os.chmod(wrapper, os.stat(wrapper).st_mode | stat.S_IXUSR)
    now = time.time()
    for i, n in enumerate(('kata1-test-a.bin.gz', 'kata1-test-b.bin.gz')):
        p = os.path.join(kd, n)
        open(p, 'wb').write(b'x' * 10)
        os.utime(p, (now + i * 10, now + i * 10))
    s0 = socket.socket()
    s0.bind(('127.0.0.1', 0))
    port = s0.getsockname()[1]
    s0.close()
    env = dict(env0, HOME=home, PYTHONUNBUFFERED='1')
    p = subprocess.Popen(['bash', sh, '--port', str(port), '--', '--allow-origin', 'http://localhost:8765'], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        cl = Client(port)

        def up():
            try:
                return cl.json('GET', '/health')[1]
            except OSError:
                return None
        b = wait_for(up, 20)
        br = (b or {}).get('bridge', {})
        check(bool(b) and br.get('backend') == 'OpenCL', 'the launcher found the binary and started the bridge; backend detected from `katago version`: %s' % br.get('backend'))
        check(br.get('modelId') == 'kata1-test-b' and br.get('katago', {}).get('version', '').startswith('SELFTEST-FAKE:kata1-test-b'), 'it picked the newest network as the active one')
        s, m, _ = cl.json('GET', '/models')
        check(sorted(x['id'] for x in m['models']) == ['kata1-test-a', 'kata1-test-b'], 'the other network in the same folder is switchable (ids from the folder, no paths)')
        sc, sr = cl.open('POST', '/switch', {'model': 'kata1-test-a'})
        states = [x['state'] for x in Client.lines(sr)]
        sc.close()
        s, b2, _ = cl.json('GET', '/health')
        check(states[-1] == 'ready' and b2['bridge']['modelId'] == 'kata1-test-a', 'switching through the launcher-started bridge works with the real subprocess code path')
    finally:
        p.terminate()
        try:
            out = p.communicate(timeout=10)[0]
        except subprocess.TimeoutExpired:
            p.kill()
            out = ''
    check('KataGo : ' in out and 'Network: ' in out and TOKEN not in out, 'the launcher prints what it found and never prints the token it was given')


if __name__ == '__main__':
    if '--fake-engine' in sys.argv:
        fake_engine()
        sys.exit(0)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    test_pipeline()
    test_bridge()
    test_sockets()
    test_launcher()
    print('\nAll passed' if not check.bad else '\n%d check(s) failed' % check.bad)
    sys.exit(1 if check.bad else 0)
