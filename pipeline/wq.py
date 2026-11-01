"""Helper commands for the pipeline. Nothing here starts a download, whisper or KataGo.

  python wq.py status   [--work DIR]            one line per group (tree, analysis, notes, SGF), failed videos, running analysis
  python wq.py check    NAME [--work DIR]       compare the saved tree of a group with its a2.json and kp file
  python wq.py stamp    NAME [--work DIR]       write the tree fingerprint into an a2.json / kp file made before fingerprints existed
  python wq.py validate PATH [PATH ...]         SGF checks (parentheses, AN/PL, coordinates); globs allowed; exit 1 on problems
  python wq.py fix-check [fixdict.json]         check the typo dictionary (same as mkfix.py check)

--work defaults to env WEIQI_WORK, then D:\\tmp\\work.
"""
import argparse
import glob
import os
import re
import sys

import sgfcheck
import treesync as ts
from wqutil import atomic_write_json, read_json, setup_stdio


def work(a):
    return a.work or os.environ.get('WEIQI_WORK') or r'D:\tmp\work'


def safe(name):
    return re.sub(r'[\\/:*?"<>|]', '', name)   # same rule as orch2.safe_name


def cmd_status(a):
    W = work(a)
    rows = sorted(glob.glob(os.path.join(W, 'status_*.json')))
    if not rows:
        print('no status_*.json in %s (the pipeline writes one per group after each build)' % W)
    for p in rows:
        r = read_json(p, default={})
        s, an, kp = r.get('sgf', {}), r.get('analysis', {}), r.get('key_points', {})
        print('%-34s %5s nodes | analysis %-10s | notes %-9s %3s | sgf %s AI-nodes %s notes %s | %s%s' % (
            r.get('group', os.path.basename(p)), r.get('nodes', '?'), an.get('status', '?'), kp.get('status', '?'), kp.get('notes', ''),
            'written' if s.get('written') else 'NOT WRITTEN', s.get('an', '?'), s.get('kp', '?'), r.get('time', ''),
            ' | PARTIAL, missing videos %s' % r['missing_videos'] if r.get('missing_videos') else ''))
        if s and not s.get('written'):
            print('    refused: %s' % '; '.join(s.get('reasons', [])))
    failed = read_json(os.path.join(W, 'failed_videos.json'), default={})
    for k, v in sorted(failed.items(), key=lambda kv: int(kv[0])):
        print('FAILED video %s (%s) stage %s after %s tries: %s' % (k, v.get('bvid'), v.get('stage'), v.get('attempts'), v.get('reason')))
    for p in sorted(glob.glob(os.path.join(W, 'g_*.progress.json'))):
        r = read_json(p, default={})
        print('analysis %s: %s %s/%s queries, nodes %s/%s, eta %s s (updated %s)' % (
            os.path.basename(p)[2:-len('.a2.json.progress.json')], r.get('phase'), r.get('done'), r.get('total'),
            r.get('nodes_done'), r.get('nodes_total'), r.get('eta_s'), r.get('updated')))
    return 0


def load_group(a):
    W = work(a)
    N = read_json(os.path.join(W, 'g_%s.n.json' % safe(a.name)))
    return W, N


def cmd_check(a):
    W, N = load_group(a)
    base = os.path.join(W, 'g_' + safe(a.name))
    print('tree %s: %d nodes, fingerprint %s' % (a.name, len(N), ts.tree_fingerprint(N)))
    st, msg = ts.check_analysis(N, read_json(base + '.a2.json', default=None))
    print('analysis:', st, msg)
    kp = read_json(os.path.join(W, 'kp_%s.json' % safe(a.name)), default=None)
    out, kst, kmsg, _ = ts.check_kp(N, kp)
    print('key points:', kst, kmsg, '(%d notes usable)' % len(out))
    return 0 if st in ts.USABLE and kst in ('ok', 'legacy', 'missing', 'remapped') else 1


def cmd_stamp(a):
    """Bless files that were made before fingerprints existed. Only do this when you know they belong to the saved tree."""
    W, N = load_group(a)
    p = os.path.join(W, 'g_%s.a2.json' % safe(a.name))
    A = read_json(p, default=None)
    st, msg = ts.check_analysis(N, A)
    if st == 'legacy':
        A['_meta'] = ts.make_meta(N, stamped_by='wq stamp')
        atomic_write_json(p, A)
        print('a2.json stamped')
    else:
        print('a2.json not stamped (%s %s)' % (st, msg))
    p = os.path.join(W, 'kp_%s.json' % safe(a.name))
    kp = read_json(p, default=None)
    _, kst, kmsg, _ = ts.check_kp(N, kp)
    if kst == 'legacy':
        kp['_meta'] = ts.kp_ident(N)
        atomic_write_json(p, kp, ensure_ascii=False)
        print('kp file stamped')
    else:
        print('kp file not stamped (%s %s)' % (kst, kmsg))
    return 0


def cmd_validate(a):
    files = [f for pat in a.paths for f in (glob.glob(pat, recursive=True) or [pat])]
    bad = 0
    for f in files:
        try:
            text = open(f, encoding='utf-8-sig').read()
        except OSError as e:
            print('%s: cannot read (%s)' % (f, e))
            bad += 1
            continue
        problems = sgfcheck.validate(text)
        m = sgfcheck.metrics(text)
        print('%s: %s  nodes %d, AI nodes %d, notes %d, teacher text %d' % (f, 'OK' if not problems else 'INVALID', m['nodes'], m['an'], m['kp'], m['teach']))
        for p in problems[:5]:
            print('    ' + p)
        bad += bool(problems)
    return 1 if bad else 0


def cmd_fix_check(a):
    import mkfix
    return mkfix.main(['check'] + ([a.dict] if a.dict else []))


def main(argv=None):
    setup_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name, fn in (('status', cmd_status), ('check', cmd_check), ('stamp', cmd_stamp)):
        p = sub.add_parser(name)
        if name != 'status':
            p.add_argument('name')
        p.add_argument('--work')
        p.set_defaults(fn=fn)
    p = sub.add_parser('validate')
    p.add_argument('paths', nargs='+')
    p.set_defaults(fn=cmd_validate)
    p = sub.add_parser('fix-check')
    p.add_argument('dict', nargs='?', help='fixdict.json to check (default: the one next to this script)')
    p.set_defaults(fn=cmd_fix_check)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == '__main__':
    sys.exit(main())
