"""A stand-in for `katago analysis`: reads one json request per line on stdin, answers one json line each.

No GPU, no network. Behaviour is steered with env vars so the tests can reproduce engine problems:
  FAKE_REPORT_AS=BLACK|SIDETOMOVE   how scores are reported (like reportAnalysisWinratesAs)
  FAKE_CRASH_AFTER=n                exit abruptly after n answers
  FAKE_STALL_AFTER=n                keep reading but stop answering after n answers
  FAKE_QUERY_LOG=path               append every received query id to this file
"""
import json
import os
import sys
import time

L = "ABCDEFGHJKLMNOPQRST"
REPORT_AS = os.environ.get("FAKE_REPORT_AS", "BLACK")
CRASH_AFTER = int(os.environ.get("FAKE_CRASH_AFTER", "0"))
STALL_AFTER = int(os.environ.get("FAKE_STALL_AFTER", "0"))
QUERY_LOG = os.environ.get("FAKE_QUERY_LOG")


def answer(req):
    stones = {p: c for c, p in req.get("initialStones", [])}
    stones.update({p: c for c, p in req.get("moves", [])})
    moves = req.get("moves", [])
    turn = ("W" if moves[-1][0] == "B" else "B") if moves else req.get("initialPlayer", "B")
    allow = req["allowMoves"][0]["moves"] if "allowMoves" in req else [L[c] + str(r) for c in range(19) for r in range(1, 20)]
    free = [m for m in allow if m not in stones][:6]
    selftest = req["id"] == "selftest"
    infos = []
    for j, m in enumerate(free):
        lead_stm = (-30.0 if selftest else 5.0) - j          # best candidate first, as for the real engine
        wr_stm = 0.03 if selftest else 0.55 - 0.02 * j
        if REPORT_AS == "BLACK" and turn == "W":
            lead, wr = -lead_stm, 1 - wr_stm                   # reported from Black's point of view
        else:
            lead, wr = lead_stm, wr_stm
        infos.append({"move": m, "visits": 100 - 10 * j, "scoreLead": lead, "winrate": wr, "prior": 0.3 - 0.04 * j,
                      "order": j, "pv": [m, "Q16"]})
    root = dict(infos[0]) if infos else {"scoreLead": 0, "winrate": 0.5}
    return {"id": req["id"], "isDuringSearch": False, "turnNumber": len(moves), "moveInfos": infos,
            "rootInfo": {"currentPlayer": turn, "scoreLead": root["scoreLead"], "winrate": root["winrate"], "visits": 100}}


def main():
    answered = 0
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        if QUERY_LOG:
            with open(QUERY_LOG, "a", encoding="utf-8") as f:
                f.write(req["id"] + "\n")
        if STALL_AFTER and answered >= STALL_AFTER:
            continue                                          # silent engine
        sys.stdout.write(json.dumps(answer(req)) + "\n")
        sys.stdout.flush()
        answered += 1
        if CRASH_AFTER and answered >= CRASH_AFTER:
            os._exit(3)


if __name__ == "__main__":
    main()
