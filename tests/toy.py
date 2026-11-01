"""Tiny synthetic fixtures: a toy board recording, transcript and analysis. No video, no KataGo."""
import copy

COLS, ROWS = 18, 19
L = "ABCDEFGHJKLMNOPQRST"

# point index = row * 18 + col, same as board.py
B1, W2, B4, W3, B5 = 69, 106, 52, 87, 104


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
    """Empty board, a move, two different answers (a branch), then a second move in the second answer."""
    s1 = {B1: "B"}
    s2 = {**s1, W2: "W"}
    s3 = {**s2, B4: "B"}
    s4 = {**s1, W3: "W"}
    s5 = {**s4, B5: "B"}
    return [{}, s1, s2, s3, s1, s4, s5]


def toy_transcript():
    return [
        {"s": 0.2, "e": 1.0, "t": "先看黑旗"},
        {"s": 1.4, "e": 2.4, "t": "白一般压"},
        {"s": 5.9, "e": 7.0, "t": "另一个变化白拖"},
    ]


def toy_analysis(N, persp_ok=True):
    """Fake KataGo result for the branch node(s) of N in the side-to-move perspective (what analyze2 writes).

    The first candidate is the best for the side to move; with persp_ok=False the scores are negated for
    White, which is what Black-perspective scores look like.
    """
    A = {}
    live = lambda i: [c for c in N[i]["ch"] if not N[c]["dead"]]
    for i, n in enumerate(N):
        if n["dead"] or len(live(i)) < 2:
            continue
        turn = "W" if n["mv"] and n["mv"][1] == "B" else "B"
        base = [(gtp(W2), 0.0), (gtp(W3), -1.5), (gtp(B4), -4.0), ("D4", -6.0)]
        cand = []
        for rank, (m, loss) in enumerate(base):
            s = 3.0 + loss
            cand.append({"m": m, "v": 100 - rank * 20, "s": s if (persp_ok or turn == "B") else -s,
                         "wr": 0.5, "p": 0.2, "pv": [m, "Q3"]})
        A[str(i)] = {"turn": turn, "score": 3.0, "wr": 0.5, "cand": cand}
    return copy.deepcopy(A)
