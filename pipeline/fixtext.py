"""Typo dictionary for the whisper transcripts and the key point notes.

Incident: replacements applied one after the other corrupted text. A short rule matched inside a longer correct word
('黑棋力' -> '黑棋立' turned '黑棋力量' into '黑棋立量'), and the output of one rule was changed again by another rule
('隐争' -> '隐征' -> '引征'), so applying the dictionary to already fixed text (key point notes are written from fixed
text and fixed again) gave a different result.

How this module prevents that:
  * Longest first. All keys of a pass go into one regex, longest key first, so at every position the longest rule wins and
    the order of the file does not matter.
  * Repeat until stable. The dictionary relies on rules feeding each other ('三天低' -> '三间低', then '低家' -> '低夹' turns
    三天低家 into 三间低夹), so passes repeat until the text no longer changes. The result is a fixed point, which makes
    "apply twice == apply once" true by construction (the old one-shot loop could not promise that).
    check_rules() reports rule sets that never settle (cycles).
  * Protected words. A correct word that contains a shorter rule's key is listed as an identity rule (word -> word,
    see KEEP): the longest match wins, so the short rule never reaches it.
  * Log. apply() counts which rules fired, so a surprising rule is visible instead of silently rewriting text.
"""
import os
import re
from collections import Counter

from wqutil import read_json

# Built in rules (formerly the FIX list in orch2.py); fixdict.json is added on top and wins on the same key.
BUILTIN = [('黑旗', '黑棋'), ('白旗', '白棋'), ('黑鸡', '黑棋'), ('白鸡', '白棋'), ('拖鲜', '脱先'), ('脱鲜', '脱先'), ('拖先', '脱先'),
           ('争子', '征子'), ('正子', '征子'), ('结材', '劫材'), ('新位', '星位'), ('小木', '小目'), ('一肩', '一间'), ('拖角', '托角'),
           ('拖脚', '托角'), ('煎顶', '尖顶'), ('二肩', '二间'), ('小煎', '小尖'), ('煎冲', '尖冲'), ('加击', '夹击'), ('高加', '高夹'),
           ('低加', '低夹'), ('斑', '扳'), ('棋型', '棋形'),
           ('拖', '托')]   # was a special case after the loop; 拖延 is protected by KEEP

# Correct words that contain a shorter rule's key ('拖延' has 拖, '黑棋力量' has the key of 黑棋力).
KEEP = ['拖延', '黑棋力量', '白棋力量']

MAX_PASSES = 8   # a sane dictionary settles in 2 or 3 passes
REPLACEMENT_CHAR = '�'   # whisper emits it for a character it could not decode; there is nothing to restore, so it is dropped


def load_rules(path=None):
    """Rules as {key: replacement}: built in, then the json file (a list of [wrong, right] pairs), then KEEP identities."""
    rules = dict(BUILTIN)
    if path and os.path.exists(path):
        for a, b in read_json(path):   # a damaged dictionary raises: silently dropping 300 rules would change every text
            rules[a] = b
    for w in KEEP:
        rules.setdefault(w, w)
    return rules


class Fixer:
    def __init__(self, rules):
        self.rules = dict(rules)
        keys = sorted((k for k in self.rules if k), key=lambda k: (-len(k), k))
        self.rx = re.compile('|'.join(re.escape(k) for k in keys)) if keys else None

    def apply(self, text, fired=None):
        """Fixed text. `fired` (a Counter) gets one count per rule that really changed something."""
        if REPLACEMENT_CHAR in text:
            if fired is not None:
                fired['<U+FFFD removed>'] += text.count(REPLACEMENT_CHAR)
            text = text.replace(REPLACEMENT_CHAR, '')
        if self.rx is None:
            return text

        def sub(m):
            k = m.group(0)
            if fired is not None and self.rules[k] != k:
                fired['%s->%s' % (k, self.rules[k])] += 1
            return self.rules[k]
        for _ in range(MAX_PASSES):
            new = self.rx.sub(sub, text)
            if new == text:
                return text
            text = new
        if fired is not None:
            fired['<did not settle>'] += 1   # a cycle in the dictionary; check_rules() names it
        return text


def check_rules(rules):
    """Hard problems (empty list = the dictionary is sound): empty keys and rules whose text never settles (cycles)."""
    fx = Fixer(rules)
    out = []
    for a, b in sorted(rules.items()):
        if not a:
            out.append('empty key')
            continue
        for text in {a, b}:
            f = fired = Counter()
            fx.apply(text, f)
            if fired['<did not settle>']:
                out.append('rule %s->%s runs in a cycle: %s never settles' % (a, b, text))
                break
    return out


def chains(rules):
    """Rules whose output is rewritten again by other rules: [(key, written, final)]. Fine, but better written as key -> final."""
    fx = Fixer(rules)
    return [(a, b, fx.apply(b)) for a, b in sorted(rules.items()) if a and a != b and fx.apply(b) != b]


def short_rules(rules):
    """Single character rules fire inside many correct words; worth a look when they surprise you."""
    return sorted(k for k, v in rules.items() if len(k) == 1 and k != v)


_cache = {}


def fixer_for(path):
    """Fixer for a dictionary file, reloaded when the file changes (the old code re-read it for every single node)."""
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = None
    hit = _cache.get(path)
    if hit and hit[0] == stamp:
        return hit[1]
    fx = Fixer(load_rules(path if stamp else None))
    _cache[path] = (stamp, fx)
    return fx


def top(fired, n=5):
    return ', '.join('%s x%d' % kv for kv in Counter(fired).most_common(n))
