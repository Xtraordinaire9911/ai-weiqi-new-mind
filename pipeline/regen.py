"""Rebuild the SGFs of all groups from the cached trees, analysis and notes, e.g. after changing the typo dictionary.

  python regen.py [--dry-run] [--only NAME ...] [--analyze] [--force]

Incident: an earlier regen replaced good SGFs with empty shells (a path that lost its backslashes, no check that the
inputs existed, and it looked for the old a.json instead of a2.json). Now a group is only rebuilt from videos whose cache
files exist, the write goes through the same guard as the pipeline (valid SGF, never poorer than the file that is there),
analysis is not started unless --analyze, and --dry-run shows what would happen without writing anything at all.
"""
import argparse
import os
import sys
import traceback

import orch2 as o
from wqutil import setup_stdio


def main(argv=None):
    setup_stdio()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true', help='decide and report, write nothing')
    ap.add_argument('--only', nargs='*', default=[], help='group names to rebuild (default: all)')
    ap.add_argument('--analyze', action='store_true', help='run KataGo for groups whose analysis is missing or stale')
    ap.add_argument('--force', action='store_true', help='overwrite even when the new SGF is poorer')
    a = ap.parse_args(argv)
    if not a.analyze:
        os.environ['NOAN'] = '1'   # regen means "from the cache", never a surprise GPU job
    rc = 0
    for name, idxs in o.groups():
        if a.only and name not in a.only:
            continue
        have = [i for i in idxs if all(os.path.exists(os.path.join(o.D(i), f)) for f in ('b.json', 't.json'))]
        if not have:
            o.log('regen skip', name, ': no cached board/transcript data for any of its videos', idxs)
            continue
        if len(have) < len(idxs):
            o.log('regen WARN', name, 'built from', have, 'only, no cache for', [i for i in idxs if i not in have])
        try:
            o.stageB(name, have, planned=idxs, force=a.force, dry=a.dry_run)
        except Exception:
            rc = 1
            o.log('regen FAIL', name, traceback.format_exc()[-300:])
    return rc


if __name__ == '__main__':
    sys.exit(main())
