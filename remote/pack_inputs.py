#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pack variation trees (g_<name>.n.json) for the cloud batch. Read only: nothing in the work folder is changed.

  python pack_inputs.py --work D:\\tmp\\work --list-missing
  python pack_inputs.py --work D:\\tmp\\work --out n_json_20261108.zip NAME [NAME ...]

The groups are processed by analyze_remote.py in the order given here, so give the groups the local pipeline reaches LAST
first: the cloud then works from the end of the list towards the front while the local run works from the front.

What goes into the zip: the .n.json files byte for byte plus manifest.json (order, node counts, tree fingerprints; the cloud
run refuses a tree whose fingerprint differs). Before packing, every file is checked to hold nothing but the variation tree:
only the known node fields, stones as colour letter plus point number, moves, ids, and video time stamps. There is no
field that could carry the teacher's commentary, and a file with an unknown field or a free text value is refused.
"""
import argparse
import glob
import json
import os
import re
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze_remote as ar  # noqa: E402  (puts the pipeline folder on sys.path)

an, ts = ar.an, ar.ts
from wqutil import read_json, setup_stdio  # noqa: E402

NODE_FIELDS = {'id', 'par', 'mv', 'v', 'ch', 'dead', 'setup', 'n', 'pos'}
POS_RE = re.compile(r'(?:[BW]\d{1,3})*')


def safe(name):
    return re.sub(r'[\\/:*?"<>|]', '', name)   # same rule as orch2.safe_name


def check_pure_tree(N):
    """Raise ValueError unless N is only structure: no field or value that could hold teacher text."""
    ar.validate_tree(N)
    for k, n in enumerate(N):
        extra = set(n) - NODE_FIELDS
        if extra:
            raise ValueError('node %d has the unknown field(s) %s' % (k, ', '.join(sorted(extra))))
        if not all(isinstance(n[f], int) and not isinstance(n[f], bool) for f in ('id', 'n')) or not isinstance(n['par'], (int, type(None))):
            raise ValueError('node %d: id, n and par must be integers' % k)
        if not isinstance(n['dead'], bool) or not isinstance(n['setup'], bool):
            raise ValueError('node %d: dead and setup must be booleans' % k)
        if not isinstance(n['pos'], str) or not POS_RE.fullmatch(n['pos']):
            raise ValueError('node %d: pos is not a list of stones (%.30r)' % (k, n['pos']))
        mv = n['mv']
        if mv is not None and not (isinstance(mv, list) and len(mv) == 2 and isinstance(mv[0], int) and mv[1] in ('B', 'W')):
            raise ValueError('node %d: mv is not [point, colour]' % k)
        if not isinstance(n['ch'], list) or not all(isinstance(c, int) for c in n['ch']):
            raise ValueError('node %d: ch is not a list of ids' % k)
        if not isinstance(n['v'], list) or not all(isinstance(s, list) and len(s) == 3 and all(isinstance(x, (int, float)) for x in s) for s in n['v']):
            raise ValueError('node %d: v is not a list of [from, to, video] time spans' % k)


def describe(N):
    """Counts the way analyze2 makes them: live nodes, branch points, and the queries of phase 1 (phase 2 depends on the answers)."""
    todo = an.branch_nodes(N)
    R = an.region(N)
    ctl = sum(1 for i in todo if R and any(not an.inreg(R, *k) for k in an.stones_at(N, i)))
    return {'nodes': sum(1 for n in N if not n['dead']), 'branch_nodes': len(todo), 'queries_main': len(todo) + ctl,
            'tree_fp': ts.tree_fingerprint(N)}


def load(work, name):
    path = os.path.join(work, 'g_%s.n.json' % safe(name))
    N = read_json(path)
    check_pure_tree(N)
    return path, N


def missing_groups(work):
    """Names of the groups that have a tree but no usable analysis for it (valid, or legacy that the pipeline still accepts)."""
    out = []
    for p in sorted(glob.glob(os.path.join(work, 'g_*.n.json'))):
        name = os.path.basename(p)[2:-len('.n.json')]
        try:
            N = read_json(p)
            st, _ = ts.check_analysis(N, read_json(p[:-len('.n.json')] + '.a2.json', default=None))
        except ValueError as e:
            print('skip %s: %s' % (name, e), file=sys.stderr)
            continue
        if st not in ts.USABLE:
            out.append((name, N, st))
    return out


def pack(work, names, out, skip_valid=False):
    entries, order = {}, []
    for name in names:
        path, N = load(work, name)
        if skip_valid:
            st, _ = ts.check_analysis(N, read_json(path[:-len('.n.json')] + '.a2.json', default=None))
            if st in ts.USABLE:
                print('skip %s: a usable analysis exists (%s)' % (name, st))
                continue
        d = describe(N)
        d.update(file=os.path.basename(path), bytes=os.path.getsize(path), path=path)
        entries[name] = d
        order.append(name)
    if not order:
        raise ValueError('nothing to pack')
    manifest = {'schema': 1, 'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'order': order,
                'note': 'variation trees only (no commentary); analyze_remote.py works through them in this order',
                'groups': {n: {k: v for k, v in e.items() if k != 'path'} for n, e in entries.items()}}
    tmp = out + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=1))
        for n in order:
            z.write(entries[n]['path'], entries[n]['file'])
    os.replace(tmp, out)
    return manifest


def main(argv=None):
    setup_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--work', default=os.environ.get('WEIQI_WORK', r'D:\tmp\work'), help='folder with the g_<name>.n.json files')
    ap.add_argument('--out', help='zip file to write')
    ap.add_argument('--list-missing', action='store_true', help='list the groups that have no usable analysis and exit')
    ap.add_argument('--skip-valid', action='store_true', help='leave out groups that already have a usable a2.json')
    ap.add_argument('names', nargs='*', help='group names, the one the cloud should do first first')
    a = ap.parse_args(argv)
    if a.list_missing:
        for name, N, st in missing_groups(a.work):
            d = describe(N)
            print('%-34s analysis %-10s nodes %5d branch points %4d main queries %4d' % (name, st, d['nodes'], d['branch_nodes'], d['queries_main']))
        return 0
    if not a.out or not a.names:
        ap.error('give --out and at least one group name (or --list-missing)')
    try:
        m = pack(a.work, a.names, a.out, a.skip_valid)
    except (ValueError, OSError) as e:
        print('ERROR: %s' % e, file=sys.stderr)
        return 2
    for n in m['order']:
        g = m['groups'][n]
        print('%-34s nodes %5d branch points %4d main queries %4d fp %s' % (n, g['nodes'], g['branch_nodes'], g['queries_main'], g['tree_fp']))
    print('wrote %s (%d bytes, %d groups)' % (a.out, os.path.getsize(a.out), len(m['order'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
