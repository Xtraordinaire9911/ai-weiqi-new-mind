"""Keep derived files tied to the variation tree they were made from.

Incident: a2.json (KataGo analysis) and kp_*.json (key point notes) are keyed by
node id. When another video of a group finished downloading, build_tree produced a
different tree, the ids shifted, and the old files were silently merged into the
wrong nodes. Now every derived file carries a fingerprint of the tree it belongs to
(inside a "_meta" key, so old readers that look up node ids are not affected) and
the loaders compare it before anything is merged.
"""
import hashlib
import json
import re
import time

SCHEMA = 2
PERSP = 'stm'          # a2.json scores and winrates are from the side to move (never Black)
USABLE = ('ok', 'legacy')   # analysis statuses that may be merged into an SGF
L = 'ABCDEFGHJKLMNOPQRST'
COLS = 18              # the recognised board is 18 columns wide, see board.py


def tree_fingerprint(N):
    """Hash of the tree structure: ids, parents, moves, children, flags and positions.

    Video time spans (the 'v' field) are left out on purpose: a timing shift cannot make
    an analysis wrong, and including them would force a GPU re-run for nothing. Any change
    of node ids, moves or positions does change the fingerprint.
    """
    canon = [[n['id'], n['par'], n['mv'], n['ch'], bool(n['dead']), bool(n['setup']), n['pos']] for n in N]
    return hashlib.sha1(json.dumps(canon, separators=(',', ':')).encode('ascii')).hexdigest()[:16]


def pos_key(n):
    """Identity of a node that survives a rebuild of the tree: the position plus who moved last."""
    return hashlib.sha1(('%s|%s' % (n['pos'], n['mv'][1] if n['mv'] else '')).encode('ascii')).hexdigest()[:12]


def pos_keys(N):
    """{node id as str: position key} for all live nodes."""
    return {str(n['id']): pos_key(n) for n in N if not n['dead']}


# ---------------------------------------------------------------- analysis (a2.json)

def make_meta(N, **extra):
    """The _meta block stored in a2.json. persp records that scores are side-to-move."""
    m = {'schema': SCHEMA, 'persp': PERSP, 'tree_fp': tree_fingerprint(N), 'n_nodes': len(N),
         'complete': True, 'created': time.strftime('%Y-%m-%d %H:%M:%S')}
    m.update(extra)
    return m


def _entries(A):
    """(key, entry) for real analysis entries; skips _meta and error stubs."""
    for k, a in A.items():
        if k != '_meta' and isinstance(a, dict) and 'cand' in a:
            yield k, a


def _idx(m):
    """GTP move text ('D4') to the pipeline's point index (row * 18 + col), or None if not on the 18x19 board."""
    mt = re.fullmatch(r'([A-HJ-T])(\d{1,2})', m or '')
    if not mt or L.index(mt.group(1)) >= COLS or not 1 <= int(mt.group(2)) <= 19:
        return None
    return (19 - int(mt.group(2))) * COLS + L.index(mt.group(1))


def perspective_suspect(A, min_nodes=5):
    """Detect scores that are not side-to-move (incident 1: Black perspective used as if it were stm).

    KataGo orders candidates by how good they are for the side to move. With correct
    side-to-move scores the first candidate has (nearly) the best score for both colours.
    With Black-perspective scores that holds only for Black; for White the first candidate has
    the WORST score. Calibrated on real data: correct files give ~100% for White nodes, the old
    Black-perspective files gave 13% to 22%. Returns (suspect, {turn: (ok, total)}).
    """
    seen = {'B': [0, 0], 'W': [0, 0]}
    for k, a in _entries(A):
        if not re.fullmatch(r'\d+(_\d+)?', k) or a.get('turn') not in seen:   # node ids, also the context-free '<id>_0' queries
            continue
        c = [m for m in a['cand'] if not m.get('f')]   # forced evaluations of teacher moves are not ordered
        if len(c) < 3:
            continue
        seen[a['turn']][1] += 1
        seen[a['turn']][0] += c[0]['s'] >= max(m['s'] for m in c) - 1.0
    bad = [t for t, (ok, n) in seen.items() if n >= min_nodes and ok < 0.5 * n]
    return bool(bad), {t: tuple(v) for t, v in seen.items()}


def consistent_with_tree(N, A):
    """Cheap structural check for analysis files that carry no fingerprint (made before this existed).

    Real analysis of this tree: every id exists and is alive, the side to move is the opposite of the
    last mover, and no candidate sits on an occupied point. A file for another tree breaks these quickly.
    Returns (ok, reason).
    """
    n_chk = bad_id = bad_turn = bad_occ = 0
    for k, a in _entries(A):
        m = re.fullmatch(r'(\d+)(_0)?', k)
        if not m:
            continue
        n_chk += 1
        i = int(m.group(1))
        if i >= len(N) or N[i]['dead']:
            bad_id += 1
            continue
        if not m.group(2) and N[i]['mv'] and a.get('turn') == N[i]['mv'][1]:
            bad_turn += 1   # (the _0 entries drop outside moves, so their turn can differ legitimately)
        occ = {int(t[1:]) for t in re.findall(r'[BW]\d+', N[i]['pos'])}
        if any(_idx(c['m']) in occ for c in a['cand']):
            bad_occ += 1
    if not n_chk:
        return False, 'no analysis entries'
    if bad_id > 0.02 * n_chk or bad_turn > 0.05 * n_chk or bad_occ > 0.02 * n_chk:
        return False, 'entries do not fit this tree (unknown ids %d, wrong side to move %d, candidate on a stone %d, of %d)' % (
            bad_id, bad_turn, bad_occ, n_chk)
    return True, ''


def check_analysis(N, A):
    """Decide whether analysis A may be merged for tree N. Returns (status, message).

    ok          fingerprint matches
    legacy      no fingerprint, but it passes the structural check (use wq.py stamp to bless it)
    stale       made for another tree: must be redone
    incomplete  a LIMITed or aborted run
    bad_persp   scores look like they are not side to move
    missing     nothing to merge
    """
    if not isinstance(A, dict) or not any(True for _ in _entries(A)):
        return 'missing', 'no analysis data'
    meta = A.get('_meta')
    sus, stats = perspective_suspect(A)
    if isinstance(meta, dict):
        if meta.get('persp') != PERSP:
            return 'bad_persp', 'a2 meta says perspective %r, expected %r' % (meta.get('persp'), PERSP)
        if meta.get('complete') is False:
            return 'incomplete', 'analysis run was limited or aborted'
        if meta.get('tree_fp') != tree_fingerprint(N):
            return 'stale', 'tree changed since the analysis (a2 was made for %s nodes, tree has %d)' % (meta.get('n_nodes', '?'), len(N))
        if sus:
            return 'bad_persp', 'scores look like Black perspective, first candidate is not the best one: %s' % stats
        return 'ok', ''
    if sus:
        return 'bad_persp', 'no meta and scores look like Black perspective: %s' % stats
    ok, why = consistent_with_tree(N, A)
    if not ok:
        return 'stale', 'no meta and ' + why
    return 'legacy', 'no fingerprint in a2.json (run wq.py stamp to record it)'


# ---------------------------------------------------------------- key point notes (kp_*.json)

def kp_ident(N):
    """Identity block stored in kp files and in the kpin sidecar."""
    return {'tree_fp': tree_fingerprint(N), 'keys': pos_keys(N)}


def check_kp(N, KP, ident=None, strict=False):
    """Pick the notes of KP that belong to tree N. Returns (notes {id: text}, status, message, stamp).

    The notes are written by a separate helper that only saw one version of the tree, and a kp file
    is keyed by node id, so a changed tree must not be merged blindly.

    ident  identity to assume when the file has no _meta (taken from the kpin dump the notes were made from)
    stamp  identity the caller should write into the file as _meta, or None
    status ok / remapped (carried over by position) / legacy (unverified) / stale / missing
    """
    if not isinstance(KP, dict) or not KP:
        return {}, 'missing', 'no kp data', None
    notes = {k: v for k, v in KP.items() if k != '_meta' and isinstance(v, str) and v.strip()}
    meta = KP.get('_meta') if isinstance(KP.get('_meta'), dict) else None
    stamp = None
    if meta is None and ident:
        meta = stamp = ident
    fp = tree_fingerprint(N)
    if meta is None:
        alive = {k: v for k, v in notes.items() if k.isdigit() and int(k) < len(N) and not N[int(k)]['dead']}
        if strict or len(alive) < 0.8 * len(notes):
            return {}, 'stale', 'kp has no fingerprint and %d of %d ids do not fit the tree' % (len(notes) - len(alive), len(notes)), None
        return alive, 'legacy', 'kp has no fingerprint, %d notes applied unverified (run wq.py stamp)' % len(alive), None
    if meta.get('tree_fp') == fp:
        return notes, 'ok', '', stamp
    keys = meta.get('keys')
    if isinstance(keys, dict) and keys:
        now = {pk: k for k, pk in pos_keys(N).items()}
        out = {now[keys[k]]: v for k, v in notes.items() if keys.get(k) in now}
        if out:
            return out, 'remapped', 'tree changed: %d of %d notes carried over by position, the rest need new notes' % (len(out), len(notes)), stamp
    return {}, 'stale', 'tree changed and no note could be matched by position', stamp
