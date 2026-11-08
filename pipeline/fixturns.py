"""Find and repair analysis entries of set-up positions that were analysed for the wrong side (incident 12).

  python wq.py fix-setup-turns [--work DIR] [--dry-run | --apply] [--only NAME ...] [--backup-dir DIR]

Until incident 12 was fixed, analyze2.query() sent a node without moves (a position set up from stones) to KataGo without
`initialPlayer`, and KataGo guessed Black. Where the teacher continues with White, the candidates, the ranking and the quiz
question of that node were for the wrong side. A node with a move is not affected, KataGo reads its side from the moves.

For every group that has a g_<name>.a2.json in the work folder this lists the nodes whose recorded `turn` differs from
analyze2.side_to_move(). It never starts KataGo unless --apply is given. With --apply only those nodes are asked again,
with the same functions analyze2 uses for a whole run (region, allowed points, query, Engine, convert with the detected
report_as, windowed requests, the visits of the original run, forced evaluation of the teacher's moves), and the corrected
entries replace the old ones in a2.json. The `_meta` block (tree fingerprint) and every other entry stay as they were.
Before a group is touched its a2.json is copied to the backup folder (default <work>/backup_a2_initplayer).
Run `python regen.py --only "<group>"` afterwards: it rewrites the SGF from the cache and never starts an analysis.

Exit code: 0 nothing wrong or everything repaired, 1 a group or node could not be handled (see the messages), 4 engine
failed, 5 engine missing.
"""
import filecmp
import glob
import json
import os
import shutil
import time

import analyze2 as an
import treesync as ts
from wqutil import atomic_write_json, read_json

BACKUP_DIR = 'backup_a2_initplayer'
DEFAULT_VISITS = (220, 100)     # what orch2 passes to analyze2, used when an old a2.json has no visits in its _meta


# ---------------------------------------------------------------- listing (no engine)

def best_of(a):
    """Best candidate of an entry, display only. Same rule as orch2.merge: reliable candidates (visits >= max(5, 8% of
    the top) or the teacher's moves evaluated by force), the highest side-to-move score wins."""
    c0 = a.get('cand') or []
    srch = [m for m in c0 if not m.get('f')]
    tv = max([m['v'] for m in srch] or [1])
    c = [m for m in c0 if m.get('f') or m['v'] >= max(5, .08 * tv)] or c0[:1]
    return max(c, key=lambda m: m['s']) if c else None


def teacher_moves(N, i):
    """The teacher's continuations from node i as text, e.g. 'W D17, W C16'."""
    return ', '.join('%s %s' % (N[c]['mv'][1], an.gtp(N[c]['mv'][0] % an.C, N[c]['mv'][0] // an.C))
                     for c in an.live_children(N, i) if N[c]['mv'])


def wrong_nodes(N, A):
    """[{node, keys, old, new, kids, mixed, old_best}] for the nodes of the a2 dict A that were analysed for the wrong side."""
    keys = {}
    for k in an.wrong_turns(N, A):
        keys.setdefault(int(k.split('_')[0]), []).append(k)
    rows = []
    for i in sorted(keys):
        main = A.get(str(i)) or A[keys[i][0]]       # the entry shown to the user, else whichever was flagged
        cols = [N[c]['mv'][1] for c in an.live_children(N, i) if N[c]['mv']]
        rows.append({'node': i, 'keys': keys[i], 'old': main['turn'], 'new': an.side_to_move(N, i), 'kids': teacher_moves(N, i),
                     'mixed': len(set(cols)) > 1, 'old_best': (best_of(main) or {}).get('m')})
    return rows


def group_files(work):
    """[(name, tree path, a2 path)] for every analysis in the work folder (the old Black perspective g_*.a.json is ignored)."""
    out = []
    for p in sorted(glob.glob(os.path.join(work, 'g_*.a2.json'))):
        name = os.path.basename(p)[2:-len('.a2.json')]
        out.append((name, os.path.join(work, 'g_%s.n.json' % name), p))
    return out


def plan_work(work, only=(), out=print):
    """Look at every group. Returns (plans, problems): plans = [{name, N, A, a2, rows}] for groups with wrong nodes,
    problems = messages for groups that cannot be repaired (no tree, analysis not usable)."""
    plans, problems = [], []
    for name, nj, a2 in group_files(work):
        if only and name not in only:
            continue
        N, A = read_json(nj, default=None), read_json(a2, default=None)
        if not isinstance(N, list) or not isinstance(A, dict):
            problems.append('%s: tree or analysis cannot be read (%s)' % (name, nj if not isinstance(N, list) else a2))
            continue
        st, msg = ts.check_analysis(N, A)
        rows = wrong_nodes(N, A)
        if st not in ts.USABLE:
            problems.append('%s: analysis is %s (%s), not touched%s' % (name, st, msg, ', %d entries look wrong' % len(rows) if rows else ''))
            continue
        if rows:
            plans.append({'name': name, 'N': N, 'A': A, 'a2': a2, 'rows': rows})
        else:
            out('%s: ok (%d setup nodes analysed, none for the wrong side)' % (name, sum(1 for i, n in enumerate(N) if not n['dead'] and n['mv'] is None and str(i) in A)))
    return plans, problems


def show_plan(plan, out=print):
    out('%s: %d node(s) analysed for the wrong side' % (plan['name'], len(plan['rows'])))
    for r in plan['rows']:
        out('    node %d: recorded %s, teacher plays %s -> should be %s, old best %s%s' % (
            r['node'], r['old'], r['kids'] or '(nothing)', r['new'], r['old_best'],
            '   [teacher plays both colours here, the majority decides]' if r['mixed'] else ''))


# ---------------------------------------------------------------- repair (needs the engine)

class LogProgress:
    """analyze2.Progress without files: one line per phase and one at its end."""

    def __init__(self, out):
        self.out, self.phase = out, ''

    def start(self, phase, total, already, nodes_total, nodes_done):
        self.phase = phase
        self.out('    %s: %d queries' % (phase, total))

    def tick(self, done, nodes_done, force=False):
        pass


def backup_copy(src, backup_dir):
    """Copy src into backup_dir under its own name. An earlier backup is never overwritten (the first one is the original);
    a backup that is already there with the same content (made by hand before the run) is reused."""
    os.makedirs(backup_dir, exist_ok=True)
    dst, k = os.path.join(backup_dir, os.path.basename(src)), 1
    while os.path.exists(dst):
        if filecmp.cmp(src, dst, shallow=False):
            return dst
        k += 1
        dst = os.path.join(backup_dir, '%s.%d' % (os.path.basename(src), k))
    shutil.copy2(src, dst)
    return dst


def redo_group(eng, c, report_as, plan, out):
    """Ask KataGo again about the wrong nodes of one group. Returns ({key: new entry}, [failed node ids])."""
    N, A = plan['N'], plan['A']
    meta = A.get('_meta') or {}
    R = an.region(N)
    if not meta.get('region'):
        out('    note: this a2.json has no region in its _meta, the region from the tree is used')
    elif meta['region'] != R:
        raise ValueError('the region of the saved analysis %s differs from the one the tree gives now %s, the new entries would not fit the old ones' % (meta['region'], R))
    VB, VF = meta.get('visits') or DEFAULT_VISITS
    nodes = [r['node'] for r in plan['rows']]
    done = {}
    res = an.search_nodes(eng, N, R, an.allowed(R), nodes, VB, VF, lambda d: an.convert(d, report_as), done, lambda: None, LogProgress(out), c['window'])
    new, failed = {}, []
    for i in nodes:
        mine = {k: v for k, v in res.items() if k in (str(i), '%d_0' % i)}
        ok = (str(i) in mine and mine[str(i)].get('cand')
              and all(v.get('turn') == an.side_to_move(N, i) and v.get('cand') for v in mine.values()))
        if ok:
            new.update(mine)
        else:
            failed.append(i)
            out('    node %d: the engine answer is unusable (%s), left as it was' % (
                i, json.dumps({k: v.get('turn', v.get('err')) for k, v in mine.items()}, ensure_ascii=False)))
    return new, failed


def write_group(plan, new, backup_dir, out):
    """Replace the entries in the a2.json on disk. Re-reads the file first, so a change made while the engine was working is
    never overwritten blindly. Returns True when written."""
    cur = read_json(plan['a2'], default=None)
    if not isinstance(cur, dict) or (cur.get('_meta') or {}).get('tree_fp') != (plan['A'].get('_meta') or {}).get('tree_fp'):
        out('    %s: the analysis file changed while we worked, nothing written, run again' % plan['name'])
        return False
    for k in new:
        if k in cur and cur[k] != plan['A'].get(k):
            out('    %s: entry %s changed while we worked, nothing written, run again' % (plan['name'], k))
            return False
    for r in plan['rows']:
        i = r['node']
        if str(i) not in new:
            continue                   # the engine failed for this node: left as it was
        for k in (str(i), '%d_0' % i):
            if k in new:
                cur[k] = new[k]        # same position in the dict, so the file keeps its order
            elif k in cur:
                del cur[k]             # no control run any more for this node: the old one was for the wrong side
    st, msg = ts.check_analysis(plan['N'], cur)
    if st not in ts.USABLE or an.wrong_turns(plan['N'], {k: cur[k] for k in new if k in cur}):
        out('    %s: the corrected file would not pass the checks (%s %s), nothing written' % (plan['name'], st, msg))
        return False
    backup_copy(plan['a2'], backup_dir)    # the original, before the first change (an earlier backup stays)
    atomic_write_json(plan['a2'], cur)
    return True


def show_changes(plan, new, out):
    for r in plan['rows']:
        i = str(r['node'])
        if i not in new:
            continue
        nb = best_of(new[i])
        ob = best_of(plan['A'][i]) if i in plan['A'] else None
        out('    node %d: turn %s -> %s, best move %s -> %s, score %s -> %s (side to move), %d -> %d candidates' % (
            r['node'], r['old'], new[i]['turn'], ob['m'] if ob else None, nb['m'] if nb else None,
            ob['s'] if ob else None, nb['s'] if nb else None, len(plan['A'].get(i, {}).get('cand', [])), len(new[i]['cand'])))


def apply_plans(plans, backup_dir, out):
    c = an.cfg()
    os.makedirs(backup_dir, exist_ok=True)
    errf = open(os.path.join(backup_dir, 'fix_setup_turns.katago.err'), 'ab')   # KataGo's own log
    try:
        eng = an.Engine(an.engine_cmd(c), errf, c['stall'])
    except OSError as e:
        errf.close()
        out('ERROR cannot start KataGo: %s (set WEIQI_KATAGO_DIR / WEIQI_KATAGO_MODEL)' % e)
        return 5, []
    rc, report, changed = 0, [], []
    try:
        report_as, source = an.detect_report_as(eng, c['config'], out)
        out('score perspective of the engine: %s (%s), stored as side to move' % (report_as, source))
        for plan in plans:
            out('%s: asking KataGo about %d node(s)' % (plan['name'], len(plan['rows'])))
            try:
                new, failed = redo_group(eng, c, report_as, plan, out)
            except ValueError as e:
                out('    %s: %s' % (plan['name'], e))
                rc = 1
                continue
            if failed:
                rc = 1
            if not new:
                continue
            show_changes(plan, new, out)
            if write_group(plan, new, backup_dir, out):
                changed.append(plan['name'])
                report.append({'group': plan['name'], 'nodes': [
                    {'node': r['node'], 'old_turn': r['old'], 'new_turn': new[str(r['node'])]['turn'],
                     'old_best': (best_of(plan['A'][str(r['node'])]) or {}).get('m'), 'new_best': (best_of(new[str(r['node'])]) or {}).get('m')}
                    for r in plan['rows'] if str(r['node']) in new]})
                out('    written %s (the original is in %s)' % (plan['a2'], backup_dir))
            else:
                rc = 1
    except an.EngineError as e:
        out('ERROR %s. Groups written so far: %s. Run the command again to continue with the rest.' % (e, ', '.join(changed) or 'none'))
        rc = 4
    finally:
        eng.close()
        errf.close()
    if report:   # what changed, kept next to the backups; a later run adds to it instead of replacing it
        rp = os.path.join(backup_dir, 'fix_setup_turns_report.json')
        old = read_json(rp, default={})
        atomic_write_json(rp, {'runs': (old.get('runs') or []) + [{'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'groups': report}]}, ensure_ascii=False, indent=1)
    return rc, changed


def run(work, apply=False, backup_dir=None, only=(), out=print):
    plans, problems = plan_work(work, only, out)
    for p in plans:
        show_plan(p, out)
    for m in problems:
        out('SKIPPED ' + m)
    total = sum(len(p['rows']) for p in plans)
    out('%d node(s) in %d group(s) were analysed for the wrong side%s' % (total, len(plans), '' if apply or not total else ' (nothing changed, add --apply to redo them)'))
    rc = 1 if problems else 0
    if apply and plans:
        arc, _ = apply_plans(plans, backup_dir or os.path.join(work, BACKUP_DIR), out)
        rc = arc or rc
    return rc
