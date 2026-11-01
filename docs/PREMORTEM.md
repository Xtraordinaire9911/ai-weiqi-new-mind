# Pipeline pre-mortem

Written after the first long runs, with the incidents of that time in mind. The question for every row below is: when this
breaks, how will we notice, and what stops it from doing damage? Rows are ordered by likelihood times impact (L x I, each 1 to 5).

Everything marked **done** is in the code on this branch and has a test (`tests/`). Everything marked **recommended** is not
done, usually because it lives outside `pipeline/` (`tools/`, `index.html`) or needs a decision.

## 1. Root causes of the known incidents

| Incident | Root cause | Where it is handled now |
|---|---|---|
| 1. Black scores used as side to move | The sign flip was inline in a loop and the engine's reporting mode was an assumption about a config file | `analyze2.convert` is the only place that flips signs, the mode is detected with a handicap position at startup and stored in `a2.json` meta, `treesync.perspective_suspect` rejects files that look wrong |
| 2. Ghost stone colours inverted | Colour was derived in the viewer from data that did not say who moves | Analysis records `turn` per node and the SGF carries `PL`; `sgfcheck` requires `PL` to be B or W. The viewer side is not part of this branch |
| 3. Stale caches, old pages | Nothing told the reader that a file had changed | `serve.py` sends no-store; data carries its build time. Content hash for `library.js` is recommended (row 17) |
| 4. a2 and kp out of sync | Derived files are keyed by node id and the ids are an accident of video order | Tree fingerprint in every derived file, check before merging, automatic re-analysis, notes follow their position (`treesync.py`) |
| 5. Regen wrote empty shells | A path built with string concatenation, no check that inputs existed, no comparison with what was there | `os.path.join` everywhere, `regen.py` guard and dry run, `write_sgf` refuses invalid or poorer files |
| 6. Group of 4 failed to download | One lock held across 40 tries with a short sleep, no limit, no record | Backoff, lock only while yt-dlp runs, give up with a reason, second round, `failed_videos.json` |
| 7. Windows quirks | Platform defaults (cp936, ANSI, text mode) used everywhere | Explicit utf-8, BOM tolerant reads, LF writes, atomic replace, test that fails on an `open()` without encoding |
| 8. Helpers could not write, silently | Absence of a file looked the same as "nothing to do" | Status record says how many notes were wanted and found, warning below 50 percent |
| 9. Analysis progress invisible | Output captured to memory and dropped, exit code ignored | Log file per group, progress file with ETA, exit code reported, stall detection |
| 10. Typo rules corrupted text | Sequential `str.replace`, short rules inside longer correct words, output of a rule fed to another | `fixtext.py`: longest first, repeat until stable, protected words, rule log |
| 11. Hard coded geometry gave garbage | Recogniser trusted the layout and wrote whatever it saw | Self check: size, board share, grid alignment, stone sanity; rejected videos get a reason and are not retried |

The common thread: **a stage wrote output that looked like a result without saying what it was made from or whether it was
complete**. The fixes give each output an identity (fingerprint, meta), make "done" mean complete (atomic writes, checks
before writing) and make every refusal say why.

## 2. Failure modes, ordered by L x I

| # | Failure mode | How it shows up | L x I | Mitigation | Status |
|---|---|---|---|---|---|
| 1 | A video of a group arrives late or is added; the tree is rebuilt and node ids shift | AI evaluation and notes on the wrong moves, no error | 5x5 | Fingerprint in `a2.json` and kp (`_meta`), mismatch moves the old file to `.stale` and re-runs the analysis (or leaves AI out with `NOAN`); kp notes are carried over by position key | done |
| 2 | Download throttled (HTTP 567, 412, 429) | Whole group missing; before: half an hour blocked, nothing recorded | 5x4 | Backoff 60/180/540 s, download lock only while yt-dlp runs, 4 tries then give up with the reason, `failed_videos.json`, second round after a pause that rebuilds partial groups | done |
| 3 | Rerun, regen or a partial group overwrites a good SGF with a poorer one | Empty or AI-less SGF in the viewer | 4x5 | `sgfcheck` validation plus "never fewer nodes, AI nodes or notes" (teacher text may drop 20 percent); refused candidates go to `work/rejected/`; `WEIQI_FORCE=1` overrides; `regen.py --dry-run` | done |
| 4 | Process killed during a write | Truncated json treated as finished for ever (before) | 4x4 | `atomic_write_*` for every json and sgf (temp, fsync, replace, retry on Windows lock); leftovers `*.corrupt` are redone | done |
| 5 | `sync_pipeline.ps1` copies the old working files over the hardened ones in `pipeline/`, and does not copy the new modules | Hardening silently reverted, or `ImportError: wqutil` | 4x4 | Copy the hardened files into `D:\tmp\work` first (section 4). Recommended: add the new files to the script's list and print a diff before copying | recommended |
| 6 | Another layout, resolution or theme (other uploader, 1080p fallback, series with a different board) | Garbage tree, nonsense analysis | 4x4 | `board.py` checks size, board share (>= 50 percent), grid alignment (real 46..91, other layouts 0..2) and stones; rejected videos get `b.rej.json` and are not redone | done |
| 7 | Whisper or KataGo killed or crashed during a long job | 20 minutes of GPU lost, or a hang | 4x3 | Analysis checkpoints every 25 answers and resumes for the same tree and settings; a silent engine ends the run after `WEIQI_STALL_S`; `analyze2` exit codes 2 to 5 mean something | done |
| 8 | Windows text handling (cp936 console, PowerShell without BOM, default encodings) | Garbled logs, `UnicodeDecodeError`, garbled Chinese in scripts | 4x3 | utf-8 stdio, child env `PYTHONUTF8`, explicit encodings (AST test), BOM tolerant reads. `sync_pipeline.ps1` has Chinese text and no BOM (test marks it as known) | done for Python, recommended for the script |
| 9 | yt-dlp breaks when the site changes | Every download fails with the same extractor error | 3x4 | The reason is stored per video (`wq.py status`), failing fast frees the slots. Recommended: update yt-dlp first when the reason is not an HTTP code | recommended |
| 10 | `build.ps1` skeleton text contains `C[]` inside `C[...]`, so the 90 placeholder SGFs are malformed; `library.js` is written non-atomically | Other SGF tools reject the files; a reader can see a half written `library.js` | 5x2 | Found by `sgfcheck` (the test skips skeletons). Recommended: escape `]` in the template and write `library.js` to a temp file, then `Move-Item -Force` | recommended |
| 11 | Score perspective changes again (engine config edited, new KataGo build) | Best move wrong for White | 2x5 | Live handicap check at startup, mode recorded in meta, detector on every load (calibrated: wrong files 13 to 22 percent correct first candidate, right files 100 percent). The live check needs an engine and was only tested against a fake one | done, live check not verified |
| 12 | Helper that writes the key point notes fails silently | SGF without notes | 3x3 | Status shows `notes/wanted`, warning below 50 percent. Recommended: whoever dispatches the helper runs `wq.py status` afterwards | done |
| 13 | Typo dictionary grows and starts to bite | Odd words in the notes, text changes between runs | 3x3 | Longest first, repeat until stable, protected words, `mkfix.py check` fails on cycles, `fixlog_<group>.json` lists what fired. 24 of the 14784 real texts (三天低家 and similar) only come out right because rules feed each other, which is why it repeats until stable | done |
| 14 | A new uploader's `index.json` / `plan.json` is wrong (unknown id, bad name, other season) | `KeyError` in the middle of a run, stray folders | 4x2 | `validate_plan` runs before anything starts and lists every problem (also duplicate idx values and entries without a bvid in `index.json`); groups skipped by `WEIQI_MAX_IDX` (default 49) are logged; uploader and season come from `WEIQI_SOURCE` / `WEIQI_SEASON` | done |
| 15 | Two orch2 processes (restart by accident) | Double downloads, two GPU jobs, interleaved writes | 3x3 | OS file lock `orch2.lock`, released when the process dies; `WEIQI_NO_LOCK=1` skips | done (lock tested on Windows and Linux) |
| 16 | Machine specific paths (ffmpeg glob, `LOCALAPPDATA`, drive letters) | `IndexError` or `KeyError` at import | 3x3 | `find_ffmpeg`, `WEIQI_*` env overrides with the old defaults, importing orch2 never fails | done |
| 17 | Browser or file cache shows old data | User looks at an old page | 3x2 | `serve.py` no-store. Recommended: cache-busting hash in the `library.js` URL (viewer is owned by someone else) | recommended |
| 18 | Truncated download or a preview clip taken for the video | Short tree, missing content | 2x3 | Duration check against `index.json` (< 80 percent is moved to `v.mp4.short` and retried) | done |
| 19 | Empty or damaged transcript saved as done | Notes with no teacher text | 2x3 | `tr.py` rejects no audio, no speech, far too little text, many replacement characters; stray U+FFFD (7 of 29 real files) are stripped in `fixtext` | done |
| 20 | A group is built from a subset of its videos | Partial SGF, later rebuilt and re-analysed (GPU time) | 3x2 | Status says `missing_videos`; `build` skips if nothing changed; guard keeps the richer file. Recommended: wait for the retry round before analysing partial groups if GPU time is tight | partly |
| 21 | Disk full, antivirus or the viewer holds a file | `PermissionError`, partial files | 2x3 | Atomic replace retries 8 times; a failed write leaves the old file and no temp file | done |
| 22 | Board recognition reads 18 of 19 columns | Stones on the right edge line are never seen | 2x3 | Documented in `board.py`. Not changed: it would renumber every point in every cache. A later migration could scan all 19 columns while skipping the watermark rows | recommended |
| 23 | SGF line endings change from CRLF to LF on the first rebuild | Large git diff, no functional change | 5x1 | Writes are LF everywhere now; mention in the PR | accepted |

## 3. What was checked on real data (read only, copies in a scratch folder)

* Dress rehearsal of the four generated groups with `stageB` on copies of the cached files: the SGFs come out identical to
  the shipped ones except that stray U+FFFD characters are gone and the 隐争/隐真 rule chain now ends in 引征 in two places.
  Node counts, AI nodes and notes are equal.
* The score perspective detector flags all four old Black-perspective `a.json` files and accepts the real `a2.json`.
* Board self check on 2 frames from each of the 30 downloaded videos: grid score 46 to 91 (limit 20); wrong layouts 0 to 2.
  Recognition on 480 real frames is identical to the old `b.json`. End to end on a real 20 second clip works; a 1280x720
  re-encode and a greyscale re-encode are rejected with the right reason.
* Typo dictionary on 14784 real texts (transcripts and notes): 7 differ from the old output (the half done chain), 0 change on a second pass (8 did with the old code).
* `sgfcheck` accepts every SGF that has content; the 90 `build.ps1` placeholders fail (row 10).

## 4. Adopting the hardened files (recommended order)

1. Let the running pipeline finish the current group (a `B done` line in `logs/orch2.log` or the old log), or accept losing the
   running analysis: the old `analyze2.py` cannot resume.
2. Back up `D:\tmp\work\*.py`, then copy all of `pipeline/*.py` from this branch into `D:\tmp\work` (new modules:
   `wqutil.py treesync.py sgfcheck.py fixtext.py wq.py`; they must sit next to `orch2.py`). Keep your `fixdict.json`.
3. Set `PYTHONUTF8=1` as a user environment variable.
4. `python wq.py fix-check D:\tmp\work\fixdict.json` and `python regen.py --dry-run`. The dry run prints for every group whether
   it would write or refuse; nothing is written.
5. For the four existing groups run `python wq.py check "<group>"` and then `python wq.py stamp "<group>"`, so that their
   a2.json and kp files get a fingerprint. Without it they still work but are marked "legacy" with a warning.
6. Start orch2 as before. Watch with `python wq.py status`.
7. Do not run `tools/sync_pipeline.ps1` before step 2 (row 5).

## 5. Commands and settings

| Command | What it does |
|---|---|
| `python orch2.py` | The pipeline (second start is refused by the lock) |
| `python regen.py [--dry-run] [--only NAME] [--analyze] [--force]` | Rebuild SGFs from the cache |
| `python wq.py status / check NAME / stamp NAME / validate PATH / fix-check` | Look and bless, never start heavy work |
| `python mkfix.py check / normalize / add a=b / apply file` | Typo dictionary maintenance |
| `docker build -t weiqi-pipeline-tests . && docker run --rm weiqi-pipeline-tests` | All tests, no GPU, no video, no KataGo |

Settings are environment variables with the old values as defaults: `WEIQI_WORK`, `WEIQI_PROJ`, `WEIQI_SOURCE`,
`WEIQI_SEASON`, `WEIQI_MAX_IDX`, `WEIQI_PY`, `FFMPEG`, `WEIQI_KATAGO_ROOT|DIR|MODEL`, `WEIQI_REPORT_AS`, `WEIQI_WINDOW`,
`WEIQI_STALL_S`, `WEIQI_ANALYZE_TIMEOUT`, `WEIQI_DL_TRIES`, `WEIQI_DL_BACKOFF`, `WEIQI_DL_TIMEOUT`, `WEIQI_STAGE_TIMEOUT`,
`WEIQI_RETRY_ROUNDS`, `WEIQI_RETRY_WAIT`, `WEIQI_RETRY_REJECTED`, `WEIQI_MIN_BOARD_RATIO`, `WEIQI_MIN_GRID_SCORE`,
`WEIQI_STRICT`, `WEIQI_FORCE`, `WEIQI_NO_LOCK`, `NOAN`, `LIMIT`.

New files in the work dir: `logs/orch2.log`, `logs/analyze_<group>.log`, `failed_videos.json`, `status_<group>.json`,
`fixlog_<group>.json`, `kpin_<group>.meta.json`, `rejected/<group>.sgf`, next to `g_<group>.a2.json`: `.part`, `.progress.log`,
`.progress.json`, `.stale`; per video: `b.meta.json`, `b.rej.json`, `t.rej.json`, `v.mp4.short`, `*.corrupt`.

## 6. Not verified

* A real KataGo run: the startup handicap check (`initialPlayer` in the query), the request window and the checkpoints were
  only exercised against `tests/fake_katago.py`.
* A real yt-dlp or whisper run: the retry, timeout and rejection paths use fakes; `board.py` was run on real clips.
* PowerShell scripts were read, not run, and not changed.
* The viewer was not touched. It only reads the SGFs; LF line endings in `C[]` should be fine because it shows comments with `white-space: pre-wrap`, but that was not tried in a browser.
