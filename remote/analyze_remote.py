#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch offline AI local evaluation (remote GPU version) -- a line-by-line port of the local pipeline's D:\\tmp\\work\\analyze2.py.

Input : g_<name>.n.json  (output of build_tree in the local pipeline; format as in analyze2.py)
Output: g_<name>.a2.json (exactly the same format as analyze2.py: {node id: {turn,score,wr,cand:[{m,v,s,wr,p,pv,(f)}]}};
                          score/winrate are already converted to the side to move's perspective, so the file can be put
                          straight back into D:\\tmp\\work for merge/regen)
        g_<name>.a2.meta.json (side note: model / KataGo version / visits / timing; does not affect the a2.json format)

What must stay identical to analyze2.py (do not change it, or old and new results are no longer comparable):
  * KataGo config has reportAnalysisWinratesAs=BLACK (also forced once with -override-config on the command line), so all
    score/winrate values are from Black's perspective; they are converted to the side to move (sg=+1 for B, -1 for W)
    before sorting and before computing losses;
  * region = 3%~97% percentile of all stone coordinates in the group + 2 lines of margin, snapped to the edge when close;
    allowMoves is restricted to the region;
  * only "branch points" (>=2 live children) and setup roots (with exactly 1 child) are analyzed;
  * phase 1: main search VB (default 220 visits); when there are stones outside the region, one more control search
    without the outside stones (min(VB,200));
  * phase 2: every move the teacher played that the main search gave no reliable visit count (<max(10, 10% of max visits))
    is evaluated separately and forced (VF, default 100); the result is negated (opponent's perspective -> side to move)
    and marked f=1, p=-1;
  * rules=japanese, komi=6.5, 19x19, untilDepth=40.

Usage:
  python analyze_remote.py --in ./in --out ./out --katago ./katago --model ./model.bin.gz
  (an existing a2.json is skipped automatically => after a disconnect/timeout just run again to resume; --force recomputes)
"""
import argparse, glob, json, os, re, shlex, subprocess, sys, time

L = 'ABCDEFGHJKLMNOPQRST'


def g(c, r):
    return L[c] + str(19 - r)


# --------------------------------------------------------------------------- query construction for one group
class Group:
    """Mirrors the module-level functions/variables of analyze2.py, wrapped in an object so several groups can be looped over."""

    def __init__(self, N):
        self.N = N
        self.R = self.region()
        R = self.R
        self.allow = [g(c, r) for c in range(R['x0'], R['x1'] + 1) for r in range(R['y0'], R['y1'] + 1)]

    @staticmethod
    def parse(pos):
        d = {}
        for t in re.findall(r'[BW]\d+', pos):
            k = int(t[1:])
            d[(k % 18, k // 18)] = t[0]
        return d

    def region(self):  # identical to analyze2.region, line by line
        N = self.N
        cs = set()
        for n in N:
            if n['dead']:
                continue
            if n['mv'] is not None:
                cs.add((n['mv'][0] % 18, n['mv'][0] // 18))
            elif n['par'] == 0:
                for t in re.findall(r'[BW]\d+', n['pos']):
                    k = int(t[1:])
                    cs.add((k % 18, k // 18))
        xs = sorted(c for c, _ in cs)
        ys = sorted(r for _, r in cs)
        pc = lambda a, p: a[min(len(a) - 1, int(len(a) * p))]
        x0 = max(0, pc(xs, .03) - 2)
        x1 = min(17, pc(xs, .97) + 2)
        y0 = max(0, pc(ys, .03) - 2)
        y1 = min(18, pc(ys, .97) + 2)
        if x0 <= 3: x0 = 0
        if y1 >= 15: y1 = 18
        if x1 >= 14: x1 = 17
        if y0 <= 3: y0 = 0
        return dict(x0=x0, x1=x1, y0=y0, y1=y1)

    def inreg(self, c, r):
        R = self.R
        return R['x0'] <= c <= R['x1'] and R['y0'] <= r <= R['y1']

    def path(self, i):
        N = self.N
        p = []
        while N[i]['mv'] is not None:
            p.append(i)
            i = N[i]['par']
        return i, p[::-1]

    def stones(self, i):  # all stones on the board at this node (start position + moves), used to detect stones outside the region
        N = self.N
        ri, p = self.path(i)
        d = dict(self.parse(N[ri]['pos']))
        for j in p:
            d[(N[j]['mv'][0] % 18, N[j]['mv'][0] // 18)] = N[j]['mv'][1]
        return d

    def q(self, i, ctx, qid, visits):
        N = self.N
        ri, p = self.path(i)
        ini = [[v, g(*k)] for k, v in self.parse(N[ri]['pos']).items() if ctx or self.inreg(*k)]
        mv = [[N[j]['mv'][1], g(N[j]['mv'][0] % 18, N[j]['mv'][0] // 18)] for j in p
              if (ctx or self.inreg(N[j]['mv'][0] % 18, N[j]['mv'][0] // 18))]
        allow = self.allow
        return {'id': qid, 'initialStones': ini, 'moves': mv, 'rules': 'japanese', 'komi': 6.5,
                'boardXSize': 19, 'boardYSize': 19, 'analyzeTurns': [len(mv)], 'maxVisits': visits,
                'allowMoves': [{'player': 'B', 'moves': allow, 'untilDepth': 40},
                               {'player': 'W', 'moves': allow, 'untilDepth': 40}]}

    def live(self, i):
        N = self.N
        return [c for c in N[i]['ch'] if not N[c]['dead']]

    def todo(self, limit=0):
        N = self.N
        todo = [i for i in range(len(N)) if not N[i]['dead'] and len(self.live(i)) >= 2]  # branch points only
        rootkids = [i for i in range(len(N)) if not N[i]['dead'] and N[i]['setup'] and len(self.live(i)) == 1 and N[i]['par'] == 0]
        todo = sorted(set(todo + rootkids))
        if limit:
            todo = todo[:limit]
        return todo


# --------------------------------------------------------------------------- KataGo process
class Engine:
    def __init__(self, cmd, err_path):
        self.cmd = cmd
        self.err = open(err_path, 'a', encoding='utf-8')
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.err,
                                  text=True, encoding='utf-8')
        self.t0 = time.time()
        self.info = {}

    def _readline(self):
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError('The KataGo process has exited (stdout closed). Check the end of katago_stderr.log; common causes: missing CUDA/cuDNN libraries, out of GPU memory, wrong model file path.')
        return line

    def query_version(self):
        self.p.stdin.write(json.dumps({'id': '__ver', 'action': 'query_version'}) + '\n')
        self.p.stdin.flush()
        d = json.loads(self._readline())
        self.info = {k: d.get(k) for k in ('version', 'git_hash')}
        return self.info

    def run(self, reqs, tag=''):
        """Same as analyze2.run: write all requests at once, collect the responses by id, and convert Black's perspective to the side to move's."""
        for r in reqs:
            self.p.stdin.write(json.dumps(r) + '\n')
        self.p.stdin.flush()
        res = {}
        t0 = time.time()
        for _ in reqs:
            d = json.loads(self._readline())
            if 'moveInfos' not in d:
                res[d['id']] = {'err': str(d)[:120]}
                continue
            t = d['rootInfo']['currentPlayer']
            sg = 1 if t == 'B' else -1
            mi = sorted(d['moveInfos'], key=lambda m: m['order'])
            res[d['id']] = {'turn': t, 'score': round(sg * d['rootInfo']['scoreLead'], 1),
                            'wr': round(d['rootInfo']['winrate'] if t == 'B' else 1 - d['rootInfo']['winrate'], 3),
                            'cand': [{'m': m['move'], 'v': m['visits'], 's': round(sg * m['scoreLead'], 1),
                                      'wr': round(m['winrate'] if t == 'B' else 1 - m['winrate'], 3),
                                      'p': round(m['prior'], 3), 'pv': m['pv'][:8]} for m in mi[:14]]}
            n = len(res)
            if n == len(reqs) or n % 5 == 0:
                print('  %s %d/%d  %.0fs' % (tag, n, len(reqs), time.time() - t0), flush=True)
        return res

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=20)
        except Exception:
            self.p.kill()


# --------------------------------------------------------------------------- full flow for one group (phase 1 + phase 2)
def analyze_group(N, eng, VB=220, VF=100, limit=0):
    G = Group(N)
    todo = G.todo(limit)
    print('  region', G.R, ' branch points', len(todo), flush=True)
    res = {}
    # Phase 1: main search at the branch points (when there are stones outside the region, one more control search without them)
    reqs = []
    for i in todo:
        reqs.append(G.q(i, True, '%d' % i, VB))
        st = G.stones(i)
        if any(not G.inreg(*k) for k in st):
            reqs.append(G.q(i, False, '%d_0' % i, min(VB, 200)))
    res.update(eng.run(reqs, 'phase 1'))
    # Phase 2: for each teacher move the AI search gave no reliable visit count, evaluate it separately and forced
    # (the position after that move, negated because it is the opponent's perspective)
    reqs = []
    need = []
    for i in todo:
        a = res.get('%d' % i)
        if not a or 'cand' not in a:
            continue
        tv = max(m['v'] for m in a['cand'])
        for c in G.live(i):
            if N[c]['mv'] is None:
                continue
            m = g(N[c]['mv'][0] % 18, N[c]['mv'][0] // 18)
            cm = next((x for x in a['cand'] if x['m'] == m), None)
            if cm and cm['v'] >= max(10, .1 * tv):
                continue
            if m not in G.allow:
                continue  # move outside the region (tenuki etc.): not evaluated
            reqs.append(G.q(c, True, 'f%d' % c, VF))
            need.append((i, c, m))
    fr = eng.run(reqs, 'phase 2') if reqs else {}
    for i, c, m in need:
        f = fr.get('f%d' % c)
        a = res['%d' % i]
        if not f or 'cand' not in f or not f['cand']:
            continue
        t = f['cand'][0]
        a['cand'].append({'m': m, 'v': VF, 's': round(-f['score'], 1), 'wr': round(1 - f['wr'], 3), 'p': -1,
                          'pv': [m] + t['pv'][:7], 'f': 1})
    return res, dict(region=G.R, branch_nodes=len(todo), queries=len(res) + len(fr), forced=len(need))


CFG = """# Generated by analyze_remote.py; the search parameters match the local analysis.cfg, only the log directory differs
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


def main():
    ap = argparse.ArgumentParser(description='Remote GPU batch version of analyze2.py')
    ap.add_argument('--in', dest='inp', required=True, help='directory containing g_*.n.json, or a single n.json file')
    ap.add_argument('--out', required=True, help='output directory (g_*.a2.json is written here)')
    ap.add_argument('--katago', default=os.environ.get('KATAGO_BIN', './katago'))
    ap.add_argument('--model', default=os.environ.get('KATAGO_MODEL', ''))
    ap.add_argument('--cfg', default='', help='your own analysis.cfg; generated automatically if omitted (must have reportAnalysisWinratesAs=BLACK)')
    ap.add_argument('--engine-cmd', default='', help='(for tests) use this command instead of katago, e.g. "python fake_katago.py"')
    ap.add_argument('--visits', type=int, default=220, help='main search visits (local baseline 220)')
    ap.add_argument('--forced', type=int, default=100, help='forced evaluation visits (local baseline 100)')
    ap.add_argument('--threads', type=int, default=2, help='numAnalysisThreads (can be raised to 3~4 on a strong GPU)')
    ap.add_argument('--search-threads', type=int, default=16)
    ap.add_argument('--batch', type=int, default=64, help='nnMaxBatchSize')
    ap.add_argument('--limit', type=int, default=int(os.environ.get('LIMIT', '0')), help='analyze only the first N branch points per group (trial run)')
    ap.add_argument('--force', action='store_true', help='recompute even if an a2.json already exists')
    ap.add_argument('--only', default='', help='only process groups whose file name contains this substring')
    a = ap.parse_args()

    files = [a.inp] if os.path.isfile(a.inp) else sorted(glob.glob(os.path.join(a.inp, 'g_*.n.json')))
    if a.only:
        files = [f for f in files if a.only in os.path.basename(f)]
    if not files:
        sys.exit('No g_*.n.json found in %s' % a.inp)
    os.makedirs(a.out, exist_ok=True)
    todo_files = []
    for f in files:
        name = os.path.basename(f)[:-len('.n.json')]
        outp = os.path.join(a.out, name + '.a2.json')
        if os.path.exists(outp) and os.path.getsize(outp) > 2 and not a.force:
            print('skip (exists)', outp)
            continue
        todo_files.append((f, name, outp))
    print('%d of %d groups to process' % (len(todo_files), len(files)), flush=True)
    if not todo_files:
        return

    if a.engine_cmd:
        cmd = shlex.split(a.engine_cmd)
    else:
        cfg = a.cfg
        if not cfg:
            cfg = os.path.join(a.out, 'analysis_remote.cfg')
            open(cfg, 'w', encoding='utf-8').write(CFG.format(logdir=os.path.join(a.out, 'katago_logs').replace('\\', '/'),
                                                                nat=a.threads, nst=a.search_threads, bs=a.batch))
        else:
            txt = open(cfg, encoding='utf-8', errors='replace').read()
            if not re.search(r'^\s*reportAnalysisWinratesAs\s*=\s*BLACK\b', txt, re.M):
                print('warning: the supplied cfg has no reportAnalysisWinratesAs = BLACK; it is forced with -override-config.', file=sys.stderr)
        if not a.model or not os.path.exists(a.model):
            sys.exit('Model file not found: %r (pass the .bin.gz with --model)' % a.model)
        cmd = [a.katago, 'analysis', '-model', a.model, '-config', cfg, '-override-config', 'reportAnalysisWinratesAs=BLACK']
    eng = Engine(cmd, os.path.join(a.out, 'katago_stderr.log'))
    try:
        ver = eng.query_version()
        print('KataGo', ver, flush=True)
        T0 = time.time()
        for k, (f, name, outp) in enumerate(todo_files, 1):
            print('[%d/%d] %s' % (k, len(todo_files), name), flush=True)
            N = json.load(open(f, encoding='utf-8'))
            t0 = time.time()
            res, stat = analyze_group(N, eng, a.visits, a.forced, a.limit)
            tmp = outp + '.tmp'
            json.dump(res, open(tmp, 'w'))  # same json.dump defaults as analyze2.py => same format
            os.replace(tmp, outp)
            dt = time.time() - t0
            meta = dict(stat, group=name, seconds=round(dt), visits=a.visits, forced_visits=a.forced, katago=ver,
                        model=os.path.basename(a.model) if a.model else a.engine_cmd, finished=time.strftime('%Y-%m-%d %H:%M:%S'),
                        note='generated by analyze_remote.py (a port of analyze2.py)')
            json.dump(meta, open(outp[:-len('.json')] + '.meta.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('  done %s  took %ds  total %ds' % (name, dt, time.time() - T0), flush=True)
    finally:
        eng.close()
    print('all done ->', os.path.abspath(a.out))


if __name__ == '__main__':
    main()
