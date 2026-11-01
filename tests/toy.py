"""Tiny synthetic fixtures: a toy board recording, transcript and analysis. No video, no KataGo."""
import copy
import re

COLS, ROWS = 18, 19
L = "ABCDEFGHJKLMNOPQRST"

# point index = row * 18 + col, same as board.py
B1, W2, B4, W3, B5, B6 = 69, 106, 52, 87, 104, 67


def pos_str(stones):
    """Board string as board.py writes it: 342 chars of '.', 'B', 'W'."""
    s = ["."] * (COLS * ROWS)
    for k, c in stones.items():
        s[k] = c
    return "".join(s)


def gtp(k):
    return L[k % COLS] + str(19 - k // COLS)


def frames(seq, per=8, t0=0.0):
    """[[t, board string], ...] at 6 fps, every position shown `per` frames."""
    out, i = [], 0
    for stones in seq:
        for _ in range(per):
            out.append([round(t0 + i / 6, 4), pos_str(stones)])
            i += 1
    return out


def toy_sequence():
    """Empty board, a move, two different answers (a branch), a second answer to the first answer, and more depth.

    Resulting tree: 0 root, 1 B1, 2 W2, 3 B4, 4 B6, 5 W3, 6 B5. Branch points: node 1 (W2 / W3) and node 2 (B4 / B6).
    """
    s1 = {B1: "B"}
    s2 = {**s1, W2: "W"}
    s3 = {**s2, B4: "B"}
    s6 = {**s2, B6: "B"}
    s4 = {**s1, W3: "W"}
    s5 = {**s4, B5: "B"}
    return [{}, s1, s2, s3, s2, s6, s1, s4, s5]


def toy_transcript():
    return [
        {"s": 0.2, "e": 1.0, "t": "先看黑旗"},
        {"s": 1.4, "e": 2.4, "t": "白一般压"},
        {"s": 8.9, "e": 10.0, "t": "另一个变化白拖"},
    ]


def toy_analysis(N, persp_ok=True):
    """Fake KataGo result for the branch nodes of N in the side-to-move perspective (what analyze2 writes).

    Candidates are the teacher's replies plus filler points that are empty at that node. The first candidate is the
    best for the side to move; with persp_ok=False the scores are negated for White, which is what
    Black-perspective scores look like.
    """
    A = {}
    live = lambda i: [c for c in N[i]["ch"] if not N[c]["dead"]]
    for i, n in enumerate(N):
        if n["dead"] or len(live(i)) < 2:
            continue
        turn = "W" if n["mv"] and n["mv"][1] == "B" else "B"
        occupied = {int(t[1:]) for t in re.findall(r"[BW]\d+", n["pos"])}
        moves = [gtp(N[c]["mv"][0]) for c in live(i)]
        for filler in (0, 5, 190, 200, 300):  # points far from the toy stones
            if filler not in occupied and gtp(filler) not in moves:
                moves.append(gtp(filler))
        cand = []
        for rank, m in enumerate(moves[:4]):
            s = 3.0 - [0.0, 1.5, 4.0, 6.0][rank]
            cand.append({"m": m, "v": 100 - rank * 20, "s": s if (persp_ok or turn == "B") else -s,
                         "wr": 0.5, "p": 0.2, "pv": [m, "Q3"]})
        A[str(i)] = {"turn": turn, "score": 3.0, "wr": 0.5, "cand": cand}
    return copy.deepcopy(A)
