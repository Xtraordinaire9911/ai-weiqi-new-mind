#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-test that needs no GPU and no KataGo: uses a "fake engine" (Black's-perspective output, matching reportAnalysisWinratesAs=BLACK) to verify
  1) analyze_remote.py: perspective conversion (side to move), region / branch points / forced evaluation / resume logic;
  2) optional: byte-for-byte comparison of the output with the local analyze2.py (--ref D:\\tmp\\work\\analyze2.py), proving the port is identical;
  3) katago_bridge.py: query validation, token / CORS / HTTP handling (opens no port; connections are simulated with in-memory streams).
Run:  python selftest.py [--ref path/to/analyze2.py]
Note: the fake engine's numbers are made up and only exercise the pipeline logic; they say nothing about Go.
"""
import io, json, os, subprocess, sys, tempfile, argparse, runpy, threading
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
L = 'ABCDEFGHJKLMNOPQRST'


# ----------------------------------------------------------------------------- fake engine (KataGo analysis protocol, Black's perspective)
def respond(q):
    occ = {loc for _, loc in q.get('initialStones', [])} | {loc for _, loc in q['moves'] if loc != 'pass'}
    t = ('W' if q['moves'][-1][0] == 'B' else 'B') if q['moves'] else q.get('initialPlayer', 'B')
    allow = next((a['moves'] for a in q.get('allowMoves', []) if a['player'] == t), None)
    free = [m for m in allow if m not in occ][:6]
    vis = [150, 60, 30, 12, 6, 3]
    infos = []
    for i, m in enumerate(free):  # Black's perspective: Black leads by about 3 points whoever is to move (so with W to move the side-to-move score must be negative)
        infos.append({'move': m, 'visits': vis[i], 'order': i, 'scoreLead': 3.0 + 0.1 * i, 'winrate': 0.6 - 0.01 * i,
                      'prior': 0.3 / (i + 1), 'pv': [m] + free[i + 1:i + 4]})
    return {'id': q['id'], 'turnNumber': len(q['moves']),
            'rootInfo': {'currentPlayer': t, 'scoreLead': 3.0, 'winrate': 0.6, 'visits': q['maxVisits']}, 'moveInfos': infos}


def fake_engine():
    for line in sys.stdin:
        q = json.loads(line)
        if q.get('action') == 'query_version':
            print(json.dumps({'id': q['id'], 'version': 'SELFTEST-FAKE', 'git_hash': '-'}), flush=True)
        elif q.get('action') == 'terminate':
            continue
        else:
            print(json.dumps(respond(q)), flush=True)


# ----------------------------------------------------------------------------- synthetic n.json
def synth_tree():
    k = lambda c, r: r * 18 + c
    pos = []
    for c in range(0, 5):
        for r in range(9, 18):
            if len(pos) < 40:
                pos.append(('B' if (c + r) % 2 else 'W') + str(k(c, r)))
    pos.append('B' + str(k(16, 2)))  # one far-away stone outside the region -> triggers the "_0" control query
    mk = lambda mv, par, ch, dead=False, setup=False, p='': {'dead': dead, 'mv': mv, 'par': par, 'ch': ch, 'setup': setup, 'pos': p}
    return [
        mk(None, 0, [1, 2, 3], setup=True, p=' '.join(pos)),
        mk([k(5, 12), 'B'], 0, [4, 5]),
        mk([k(6, 13), 'B'], 0, []),
        mk([k(7, 14), 'B'], 0, [], dead=True),
        mk([k(6, 12), 'W'], 1, []),
        mk([k(5, 13), 'W'], 1, [6, 7]),
        mk([k(6, 14), 'B'], 5, []),
        mk([k(7, 13), 'B'], 5, []),
    ]


def check(cond, msg):
    print(('  OK   ' if cond else '  FAIL ') + msg)
    if not cond:
        check.bad += 1


check.bad = 0


def test_pipeline(ref):
    print('[1] analyze_remote.py (fake engine)')
    d = tempfile.mkdtemp(prefix='kgtest_')
    ind, outd = os.path.join(d, 'in'), os.path.join(d, 'out')
    os.makedirs(ind)
    # Non-ASCII group name on purpose (the real group names are Chinese): "g_" + "test-fake-data" in Chinese, written as escapes
    nfile = os.path.join(ind, 'g_\u6d4b\u8bd5-\u5047\u6570\u636e.n.json')
    json.dump(synth_tree(), open(nfile, 'w'))
    eng = '"%s" "%s" --fake-engine' % (sys.executable.replace('\\', '/'), os.path.abspath(__file__).replace('\\', '/'))
    cmd = [sys.executable, os.path.join(HERE, 'analyze_remote.py'), '--in', ind, '--out', outd, '--engine-cmd', eng]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    check(r.returncode == 0, 'analyze_remote exit code 0' + ('' if r.returncode == 0 else '\n' + r.stdout[-600:] + r.stderr[-600:]))
    outp = os.path.join(outd, 'g_\u6d4b\u8bd5-\u5047\u6570\u636e.a2.json')
    res = json.load(open(outp))
    check(set(res) >= {'0', '1', '5', '0_0', '1_0', '5_0'}, 'contains the 3 branch points and the out-of-region control queries: ' + ','.join(sorted(res)))
    check(all(a.get('turn') in ('B', 'W') for a in res.values()), 'every result has a turn')
    ok = all((a['score'] > 0) == (a['turn'] == 'B') and all((c['s'] > 0) == (a['turn'] == 'B') for c in a['cand']) for a in res.values())
    check(ok, "Black's perspective -> side to move: score is negative when W is to move and positive when B is")
    forced = [c for a in res.values() for c in a['cand'] if c.get('f')]
    check(len(forced) > 0 and all(c['p'] == -1 and c['v'] == 100 for c in forced), "the teacher's moves were evaluated by force (%d entries, f=1,p=-1,v=100)" % len(forced))
    check(all(len(c['pv']) <= 8 for a in res.values() for c in a['cand']), 'pv has at most 8 moves')
    check(os.path.exists(outp[:-5] + '.meta.json'), 'wrote the .a2.meta.json side file')
    r2 = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    check('skip (exists)' in r2.stdout, 'a second run skips finished groups automatically (resume)')
    if ref:
        print('[1b] comparison with analyze2.py (%s)' % ref)
        out_ref = os.path.join(d, 'ref.a2.json')
        script = ("import subprocess,sys,runpy\n"
                  "_P=subprocess.Popen\n"
                  "def _fake(args,**kw):return _P([sys.executable,%r,'--fake-engine'],**kw)\n"
                  "subprocess.Popen=_fake\n"
                  "sys.argv=[%r,%r,%r,'220','100']\n"
                  "runpy.run_path(%r,run_name='__main__')\n") % (os.path.abspath(__file__), ref, nfile, out_ref, ref)
        rr = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, encoding='utf-8')
        check(rr.returncode == 0 and os.path.exists(out_ref), 'analyze2.py runs fine on the fake engine' + ('' if rr.returncode == 0 else '\n' + rr.stderr[-500:]))
        if os.path.exists(out_ref):
            check(open(out_ref, 'rb').read() == open(outp, 'rb').read(), 'output is **byte-for-byte identical** to analyze2.py')


def test_bridge():
    print('[2] katago_bridge.py')
    import katago_bridge as kb
    q = {'id': 1, 'initialStones': [['B', 'D4']], 'moves': [['W', 'Q16'], ['B', 'pass']], 'maxVisits': 50, 'analyzeTurns': [2],
         'allowMoves': [{'player': 'B', 'moves': ['C3', 'D3'], 'untilDepth': 40}]}
    c = kb.sanitize(q)
    check(c['maxVisits'] == 50 and 'id' not in c and c['komi'] == 6.5 and c['rules'] == 'japanese', 'sanitize accepts a valid query and fills in defaults')
    bad = [dict(q, hack=1), dict(q, maxVisits=99999), dict(q, moves=[['B', 'Z99']]), dict(q, boardXSize=25),
           dict(q, analyzeTurns=[5]), dict(q, overrideSettings={'a': 1}), dict(q, rules='x; rm -rf')]
    check(all(_raises(kb, b) for b in bad), 'sanitize rejects 7 kinds of invalid query (unknown field / huge visits / coordinate / board / turn / overrideSettings / rules)')

    cfg = kb.Cfg()
    cfg.token, cfg.fake, cfg.max_visits, cfg.timeout = 'T' * 24, False, 2000, 20
    cfg.origins, cfg.allow_file, cfg.model_name = {'http://localhost:8765'}, False, 'selftest-model'
    kg = kb.KataGo([sys.executable, os.path.abspath(__file__), '--fake-engine'])
    check(kg.info.get('version') == 'SELFTEST-FAKE', 'KataGo subprocess handshake (query_version)')

    class Srv: pass
    srv = Srv(); srv.cfg, srv.kg, srv.slots = cfg, kg, threading.BoundedSemaphore(2)

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
    s, _, _ = http('GET', '/health', ok_o)
    check(s == 401, 'no token -> 401')
    s, _, _ = http('GET', '/health', dict(ok_o, Authorization='Bearer wrong'))
    check(s == 401, 'wrong token -> 401')
    s, _, b = http('GET', '/health', auth)
    check(s == 200 and b['bridge']['winratesAs'] == 'BLACK' and b['alive'], '/health with token -> 200, declares winratesAs=BLACK')
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
    kg.close()


class _Conn:
    def __init__(self, data):
        self.inb, self.out = io.BytesIO(data), io.BytesIO()

    def makefile(self, mode, bufsize=-1):
        return self.inb if 'r' in mode else self.out

    def sendall(self, b):
        self.out.write(b)

    def settimeout(self, t):
        pass


def _raises(kb, q):
    try:
        kb.sanitize(q)
    except kb.BadQuery:
        return True
    return False


if __name__ == '__main__':
    if '--fake-engine' in sys.argv:
        fake_engine()
        sys.exit(0)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('--ref', default='', help='path of the local analyze2.py, used for the byte-for-byte comparison')
    a = ap.parse_args()
    test_pipeline(a.ref)
    test_bridge()
    print('\nAll passed' if not check.bad else '\n%d check(s) failed' % check.bad)
    sys.exit(1 if check.bad else 0)
