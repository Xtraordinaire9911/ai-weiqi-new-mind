#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""katago_bridge.py -- wraps the KataGo analysis engine in a very small HTTP interface for the josekiapp compute switch.

Depends only on the Python standard library. It does one thing: forward (and validate) KataGo analysis JSON queries. It offers no shell, file or proxy functionality.

Intended (compliant) use:
  A. Local machine: run KataGo on your own computer and point the page at http://127.0.0.1:8787  (loopback only, not exposed)
  B. Your own / your university's machines: LRZ / a lab server / a rented cloud GPU VM -- reach it through SSH port forwarding or a reverse proxy with TLS
  X. **Do not** expose it through ngrok, cloudflared or similar tunnels from the Colab free tier or Kaggle: the Colab free-tier FAQ explicitly prohibits
     "connecting to remote proxies / SSH / remote desktop / web services unrelated to interactive computing", and Kaggle is not designed for it either, so the account may be banned. See README.md.

Security design:
  * A token is required (Authorization: Bearer ...); if none is given, a random token is generated on a loopback address and printed once.
    Pass the token via the KATAGO_BRIDGE_TOKEN environment variable or --token-file, not on the command line (ps would show it).
  * Listens on 127.0.0.1 only by default; any other address needs an explicit --host, and a non-loopback address without TLS triggers a loud warning.
  * CORS allows only allowlisted origins (default http://localhost:8765 and http://127.0.0.1:8765; pages opened from file:// need --allow-file-origin).
  * Only analysis queries with allowlisted fields are accepted; maxVisits / number of moves / board size / body size are capped, and concurrency is limited.
  * Forces reportAnalysisWinratesAs=BLACK (via -override-config on the command line) and adds bridge.winratesAs to every response so the page can check the perspective;
    the page converts to the side to move's perspective only when it sees BLACK, and otherwise refuses to show the result (to avoid perspective errors happening again).

Examples:
  # local machine (Windows)
  set KATAGO_BRIDGE_TOKEN=pick-a-long-random-string
  python katago_bridge.py --katago D:\\...\\katago.exe --model D:\\...\\kata1-tf3-b11c768-s12752M-d6531M.bin.gz
  # try the UI without a GPU (returns fake data clearly labeled as simulated)
  python katago_bridge.py --fake
"""
import argparse, hmac, json, os, queue, re, secrets, select, shlex, socket, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BRIDGE_VERSION = 1
LOC = re.compile(r'^(?:[A-HJ-T](?:1[0-9]|[1-9])|pass)$')
POINT = re.compile(r'^[A-HJ-T](?:1[0-9]|[1-9])$')
ALLOWED_KEYS = {'id', 'initialStones', 'initialPlayer', 'moves', 'rules', 'komi', 'boardXSize', 'boardYSize',
                'analyzeTurns', 'maxVisits', 'allowMoves', 'avoidMoves'}
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


class BadQuery(ValueError):
    pass


def sanitize(q, max_visits=2000, max_moves=500):
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
        self._send({'id': qid, 'action': 'query_version'})
        try:
            d = w.get(timeout=120)  # loading the model can be slow (the first OpenCL tuning takes several minutes)
        except queue.Empty:
            raise RuntimeError('KataGo did not respond within 120 seconds (first-time OpenCL tuning, model too large, or wrong path?)')
        finally:
            self.waiters.pop(qid, None)
        if 'error' in d:
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

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


class FakeKataGo:
    """For trying the UI without a GPU: returns deterministic **fake** analysis (Black's perspective, same format as the real engine); the bridge marks the response with fake=true."""
    info = {'version': 'FAKE', 'git_hash': 'fake'}
    dead = False

    def __init__(self):
        self.n = 0
        self.lock = threading.Lock()

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


def fake_response(q, qid):
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
    free = [m for m in allow if m not in occ]
    seed = sum(ord(ch) for _, loc in mv for ch in loc) + len(mv) * 7
    sg = 1 if t == 'B' else -1
    infos = []
    for i, m in enumerate(free[:8]):
        stm_score = 2.0 - 0.7 * i + ((seed + i * 13) % 5) * 0.1
        pv = [m] + free[i + 1:i + 4]
        infos.append({'move': m, 'visits': max(3, int(q['maxVisits'] * (0.5 / (i + 1)))), 'order': i,
                      'scoreLead': round(sg * stm_score, 3), 'winrate': round(0.5 + sg * stm_score / 40, 4),
                      'prior': round(0.3 / (i + 1), 4), 'pv': pv})
    best = infos[0] if infos else {'scoreLead': 0, 'winrate': .5}
    return {'id': qid, 'turnNumber': len(mv), 'rootInfo': {'currentPlayer': t, 'scoreLead': best['scoreLead'], 'winrate': best['winrate'],
                                                         'visits': q['maxVisits']}, 'moveInfos': infos}


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
    protocol_version = 'HTTP/1.0'

    def log_message(self, fmt, *args):  # do not log request headers (they contain the token)
        sys.stderr.write('[bridge] %s %s\n' % (self.address_string(), fmt % args))

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
        self._cors()
        self.end_headers()
        self.wfile.write(b)

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

    def meta(self, ms=None):
        s = self.server
        m = {'v': BRIDGE_VERSION, 'winratesAs': 'BLACK', 'katago': s.kg.info, 'model': s.cfg.model_name, 'fake': s.cfg.fake,
             'maxVisits': s.cfg.max_visits}
        if ms is not None:
            m['ms'] = ms
        return m

    # ---- routes
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        if self.path.split('?')[0] not in ('/', '/health'):
            return self._json(404, {'error': 'not found'})
        if not self._auth():
            return
        self._json(200, {'ok': True, 'alive': self.server.kg.alive(), 'bridge': self.meta()})

    def do_POST(self):
        if self.path.split('?')[0] != '/analyze':
            return self._json(404, {'error': 'not found'})
        if not self._auth():
            return
        cfg = self.server.cfg
        try:
            n = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            n = -1
        if not 0 < n <= 256 * 1024:
            return self._json(413, {'error': 'request body is empty or larger than 256KB'})
        try:
            q = json.loads(self.rfile.read(n).decode('utf-8'))
            cid = q.get('id') if isinstance(q, dict) else None
            if not isinstance(cid, (str, int)) or isinstance(cid, bool):
                cid = None
            clean = sanitize(q, cfg.max_visits)
        except (ValueError, UnicodeDecodeError) as e:
            return self._json(400, {'error': str(e)[:200]})
        if not self.server.slots.acquire(timeout=min(30, cfg.timeout)):
            return self._json(429, {'error': 'too many requests in flight, try again later'})
        t0 = time.time()
        try:
            kg = self.server.kg
            qid = kg.new_id()
            d = kg.analyze(clean, qid, cfg.timeout, self._gone)
            d = dict(d)
            d['id'] = cid
            d['bridge'] = self.meta(round((time.time() - t0) * 1000))
            self._json(200, d)
        except ConnectionAbortedError:
            pass
        except TimeoutError as e:
            self._json(504, {'error': str(e)})
        except Exception as e:
            self._json(502, {'error': str(e)[:200]})
        finally:
            self.server.slots.release()


def build_cmd(a):
    if a.engine_cmd:
        return shlex.split(a.engine_cmd)
    if not a.model or not os.path.exists(a.model):
        sys.exit('Model file not found: %r (--model)' % a.model)
    cfg = a.config
    if not cfg:
        d = tempfile.mkdtemp(prefix='kgbridge_')
        cfg = os.path.join(d, 'analysis_bridge.cfg')
        open(cfg, 'w', encoding='utf-8').write(GEN_CFG.format(logdir=d.replace('\\', '/'), nat=a.threads, nst=a.search_threads, bs=a.batch))
    return [a.katago, 'analysis', '-model', a.model, '-config', cfg, '-override-config', 'reportAnalysisWinratesAs=BLACK']


def main(argv=None):
    ap = argparse.ArgumentParser(description='KataGo analysis -> HTTP bridge (token + CORS + forwards analysis queries only)')
    ap.add_argument('--katago', default=os.environ.get('KATAGO_BIN', 'katago'))
    ap.add_argument('--model', default=os.environ.get('KATAGO_MODEL', ''))
    ap.add_argument('--config', default='', help='analysis.cfg (generated automatically if omitted)')
    ap.add_argument('--engine-cmd', default='', help='(for tests) use this command instead of katago')
    ap.add_argument('--fake', action='store_true', help='do not start KataGo; return fake data labeled as simulated (only for trying the UI)')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=8787)
    ap.add_argument('--token-file', default='', help='read the token from this file (takes precedence over the KATAGO_BRIDGE_TOKEN environment variable)')
    ap.add_argument('--allow-origin', action='append', default=[], help='allowed page origin, repeatable; default localhost:8765')
    ap.add_argument('--allow-file-origin', action='store_true', help='allow pages opened from file:// (Origin: null)')
    ap.add_argument('--max-visits', type=int, default=2000)
    ap.add_argument('--max-inflight', type=int, default=4)
    ap.add_argument('--timeout', type=int, default=90)
    ap.add_argument('--threads', type=int, default=2)
    ap.add_argument('--search-threads', type=int, default=16)
    ap.add_argument('--batch', type=int, default=32)
    ap.add_argument('--cert', default='', help='TLS certificate (PEM); giving it together with --key enables HTTPS')
    ap.add_argument('--key', default='')
    a = ap.parse_args(argv)

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

    cfg = Cfg()
    cfg.token = tok
    cfg.fake = a.fake
    cfg.max_visits = a.max_visits
    cfg.timeout = a.timeout
    cfg.origins = set(a.allow_origin) or {'http://localhost:8765', 'http://127.0.0.1:8765'}
    cfg.allow_file = a.allow_file_origin
    cfg.model_name = 'FAKE' if a.fake else (os.path.basename(a.model) if a.model else a.engine_cmd)

    kg = FakeKataGo() if a.fake else KataGo(build_cmd(a))
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    srv.cfg = cfg
    srv.kg = kg
    srv.slots = threading.BoundedSemaphore(a.max_inflight)
    scheme = 'http'
    if a.cert and a.key:
        import ssl
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(a.cert, a.key)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        scheme = 'https'
    print('KataGo bridge started: %s://%s:%d   (KataGo %s%s)' % (scheme, a.host, a.port, kg.info.get('version'), ', FAKE DATA!' if a.fake else ''))
    print('Allowed origins:', ', '.join(sorted(cfg.origins)) + ('  + file://' if cfg.allow_file else ''))
    if generated:
        print('Random token for this run (shown only once; paste it into the compute settings of the page):', tok)
    if not loop and scheme == 'http':
        print('WARNING: listening on %s without TLS, so the token and game records are sent in clear text. Use SSH port forwarding (-L), --cert/--key, or an HTTPS reverse proxy in front.' % a.host, file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        kg.close()


if __name__ == '__main__':
    main()
