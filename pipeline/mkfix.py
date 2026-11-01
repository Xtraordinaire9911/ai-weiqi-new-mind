"""Maintenance tool for the typo dictionary fixdict.json (a list of [wrong, right] pairs).

  python mkfix.py check [dict]                 hard problems (cycles) fail, chains and single character rules are listed
  python mkfix.py normalize [dict]             sort longest key first, drop duplicates, resolve chains; writes only if the check passes
  python mkfix.py add a=b [c=d ...] [--dict f] add rules, then normalize
  python mkfix.py apply file.txt [--dict f]    show the fixed text and which rules fired (stdin if no file); never edits the file

The old mkfix.py rebuilt fixdict.json from a hard coded list of 22 pairs (the real file has 300) and patched orch2.py
in place. Running it would have destroyed the dictionary, so it is replaced by this tool.
"""
import argparse
import os
import shutil
import sys
from collections import Counter

import fixtext
from wqutil import atomic_write_json, read_json, setup_stdio

DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixdict.json')


def file_pairs(path):
    return [tuple(x) for x in read_json(path, default=[])]


def normalized(rules):
    """Pairs sorted longest key first (then by key), chains resolved to their final text, identity rules dropped
    (KEEP words are added by the loader), so the file is a canonical list that always applies the same way."""
    fx = fixtext.Fixer(rules)
    keep, builtin = set(fixtext.KEEP), dict(fixtext.BUILTIN)
    out = [(a, fx.apply(b)) for a, b in rules.items() if a and a != b and a not in keep and builtin.get(a) != b]   # built in rules live in the code
    return sorted(out, key=lambda kv: (-len(kv[0]), kv[0]))


def report(rules):
    bad = fixtext.check_rules(rules)
    for p in bad:
        print('PROBLEM', p)
    for a, b, c in fixtext.chains(rules):
        print('note: %s -> %s is rewritten again to %s; normalize writes %s -> %s' % (a, b, c, a, c))
    sh = fixtext.short_rules(rules)
    if sh:
        print('note: %d single character rules fire inside many words, review them: %s' % (len(sh), ' '.join(sh)))
    return bad


def write_if_sound(path, rules):
    bad = fixtext.check_rules(rules)
    if bad:
        print('not written: the dictionary has %d problems' % len(bad))
        return 1
    pairs = normalized(rules)
    if os.path.exists(path):
        shutil.copyfile(path, path + '.bak')   # one step back is always possible
    atomic_write_json(path, [list(p) for p in pairs], ensure_ascii=False)
    print('wrote %d rules to %s' % (len(pairs), path))
    return 0


def main(argv=None):
    setup_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['check', 'normalize', 'add', 'apply'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--dict', default=None)
    a = ap.parse_args(argv)
    path = a.dict or (a.args[0] if a.cmd in ('check', 'normalize') and a.args else DEFAULT)
    rules = fixtext.load_rules(path)
    if a.cmd == 'check':
        return 1 if report(rules) else 0
    if a.cmd == 'normalize':
        return write_if_sound(path, rules)
    if a.cmd == 'add':
        for kv in a.args:
            k, _, v = kv.partition('=')
            if not k or not v:
                print('bad rule %r, expected wrong=right' % kv)
                return 2
            rules[k] = v
        return write_if_sound(path, rules)
    text = open(a.args[0], encoding='utf-8-sig').read() if a.args else sys.stdin.read()
    fired = Counter()
    sys.stdout.write(fixtext.Fixer(rules).apply(text, fired))
    print('\n--- rules fired: %s' % (', '.join('%s x%d' % kv for kv in fired.most_common()) or 'none'), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
