"""Sanity checks for the SGF text this pipeline writes, and a "is the new file poorer" comparison.

Incident: a regen run replaced good SGFs (teacher notes, AI evaluation) with empty shells. Every
SGF now has to pass validate() before it is written, and write_sgf in orch2 refuses to replace a
file by one with fewer nodes or less AI / note data (see worse()).

The parser is deliberately small: it knows nodes (;), variations ((...)), properties and
escaped values, which is all this project emits.
"""
import re

PT = re.compile(r'[a-s]{2}')                       # SGF point on a 19x19 board
GTP = re.compile(r'[A-HJ-T](?:[1-9]|1[0-9])')      # GTP move A1..T19 (no I)
NODE_START = re.compile(r'\s*;')
AN_ENTRY = re.compile(r'([a-s]{2}):(-?\d+(?:\.\d+)?):(-?\d+(?:\.\d+)?):(\d{1,3}):(\d+):(.+)')


def parse(text):
    """Split SGF text into nodes. Returns (nodes, problems); each node is {property: [raw values]}."""
    problems, nodes = [], []
    n, i, depth, cur = len(text), 0, 0, None
    while i < n:
        c = text[i]
        if c == '(':
            depth += 1
            if not NODE_START.match(text, i + 1):
                problems.append('"(" at %d is not followed by a node' % i)
            i += 1
        elif c == ')':
            depth -= 1
            if depth < 0:
                problems.append('")" at %d without a matching "("' % i)
                depth = 0
            i += 1
        elif c == ';':
            cur = {}
            nodes.append(cur)
            i += 1
        elif c.isspace():
            i += 1
        elif 'A' <= c <= 'Z':
            j = i
            while j < n and 'A' <= text[j] <= 'Z':
                j += 1
            ident, vals = text[i:j], []
            if cur is None:
                problems.append('property %s before the first node' % ident)
            while True:
                k = j
                while k < n and text[k].isspace():
                    k += 1
                if k >= n or text[k] != '[':
                    break
                k += 1
                buf = []
                while k < n and text[k] != ']':
                    if text[k] == '\\':
                        k += 1  # escaped character: take it literally
                    if k < n:
                        buf.append(text[k])
                    k += 1
                if k >= n:
                    problems.append('unterminated value of %s' % ident)
                    j = n
                    break
                vals.append(''.join(buf))
                j = k + 1
            if not vals:
                problems.append('property %s has no value' % ident)
            if cur is not None:
                if ident in cur:
                    problems.append('property %s twice in one node' % ident)
                cur.setdefault(ident, []).extend(vals)
            i = j
        else:
            problems.append('unexpected %r at %d' % (c, i))
            i += 1
    if depth > 0:
        problems.append('unbalanced parentheses: %d "(" never closed' % depth)
    return nodes, problems


def check_an(value):
    """Problems of one AN value: entries 'xy:loss:prior:winrate:visits:pv', joined by ';'."""
    out = []
    entries = [e for e in value.split(';') if e]
    if not entries:
        return ['AN is empty']
    for e in entries:
        m = AN_ENTRY.fullmatch(e)
        if not m:
            out.append('AN entry not well formed: %r' % e[:40])
            continue
        loss, prior, wr = float(m.group(2)), float(m.group(3)), int(m.group(4))
        if loss > 0.05:
            out.append('AN loss is positive (best move must be 0): %r' % e[:40])
        if not -1.0 <= prior <= 1.0:
            out.append('AN prior outside -1..1: %r' % e[:40])
        if wr > 100:
            out.append('AN winrate above 100: %r' % e[:40])
        bad = [x for x in m.group(6).split() if not GTP.fullmatch(x)]
        if bad:
            out.append('AN variation has invalid moves %s' % bad[:3])
    return out


def validate(text):
    """All problems found in an SGF text (empty list = fine)."""
    nodes, problems = parse(text)
    if not text.lstrip().startswith('(;'):
        problems.append('does not start with "(;"')
    if not nodes:
        problems.append('no nodes')
    for k, node in enumerate(nodes):
        for p in ('B', 'W'):
            for v in node.get(p, []):
                if not PT.fullmatch(v):
                    problems.append('node %d: %s[%s] is not a point on the board' % (k, p, v))
        for p in ('AB', 'AW'):
            for v in node.get(p, []):
                if not PT.fullmatch(v):
                    problems.append('node %d: %s[%s] is not a point on the board' % (k, p, v))
        for v in node.get('PL', []):
            if v not in ('B', 'W'):
                problems.append('node %d: PL[%s] must be B or W' % (k, v))
        for v in node.get('SZ', []):
            if v != '19':
                problems.append('node %d: SZ[%s], the pipeline writes 19' % (k, v))
        for v in node.get('AN', []):
            problems += ['node %d: %s' % (k, x) for x in check_an(v)]
    return problems[:50]


def metrics(text):
    """How much content an SGF holds. Used to tell whether a new file is poorer than the old one."""
    nodes, _ = parse(text)
    return {'nodes': len(nodes),
            'an': sum(1 for n in nodes if 'AN' in n),               # nodes with AI candidates
            'kp': text.count('【要点与考量】'),                        # key point notes
            'teach': text.count('【老师讲解')}                         # nodes with teacher text


def worse(new, old, teach_tolerance=0.2):
    """Reasons why `new` metrics are poorer than `old` ones (empty list = not worse).

    Nodes, AI nodes and key point notes may never go down. Teacher text may fluctuate a little when
    the transcript is cut differently, so it only counts when it drops by more than the tolerance.
    """
    why = []
    for k, label in (('nodes', 'nodes'), ('an', 'nodes with AI evaluation'), ('kp', 'key point notes')):
        if new[k] < old[k]:
            why.append('%s %d -> %d' % (label, old[k], new[k]))
    if new['teach'] < old['teach'] * (1 - teach_tolerance):
        why.append('teacher text %d -> %d' % (old['teach'], new['teach']))
    return why
