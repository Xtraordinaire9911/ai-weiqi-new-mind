# 流水线事前复盘 / Pipeline pre-mortem

这份文档写于流水线开始长时间运行之后，针对当时出现过的故障。下面每一行回答同一个问题：它出问题时我们怎么发现，又靠什么避免造成破坏？各行按可能性乘以影响排序（L x I，各取 1 到 5）。

Written after the first long runs, with the incidents of that time in mind. The question for every row below is: when this breaks, how will we notice, and what stops it from doing damage? Rows are ordered by likelihood times impact (L x I, each 1 to 5).

标为 **done**（已完成）的内容都已在本分支的代码里，并且有测试（`tests/`）。标为 **recommended**（建议）的内容尚未做，通常因为它在 `pipeline/` 之外（`tools/`、`index.html`），或需要先做决定。

Everything marked **done** is in the code on this branch and has a test (`tests/`). Everything marked **recommended** is not done, usually because it lives outside `pipeline/` (`tools/`, `index.html`) or needs a decision.

## 1. 已知故障的根因 / Root causes of the known incidents

| 故障 / Incident | 根因 / Root cause | 现在的处理位置 / Where it is handled now |
|---|---|---|
| 1. 黑方视角的分数被当成行棋方视角 / Black scores used as side to move | 正负号翻转写在循环里，引擎的汇报视角只是对配置文件的一个假设 / The sign flip was inline in a loop and the engine's reporting mode was an assumption about a config file | 只有 `analyze2.convert` 做符号翻转；启动时用让子局面检测引擎的汇报视角并写入 `a2.json` 的 meta；`treesync.perspective_suspect` 会拒绝看起来不对的文件 / `analyze2.convert` is the only place that flips signs, the mode is detected with a handicap position at startup and stored in `a2.json` meta, `treesync.perspective_suspect` rejects files that look wrong |
| 2. 幽灵棋子颜色反了 / Ghost stone colours inverted | 颜色由查看器根据没有标明行棋方的数据推出 / Colour was derived in the viewer from data that did not say who moves | 分析结果按节点记录 `turn`，SGF 带 `PL`；`sgfcheck` 要求 `PL` 为 B 或 W。查看器一侧不在本分支范围内 / Analysis records `turn` per node and the SGF carries `PL`; `sgfcheck` requires `PL` to be B or W. The viewer side is not part of this branch |
| 3. 缓存过期，看到旧页面 / Stale caches, old pages | 没有任何信息告诉读取方文件已经变了 / Nothing told the reader that a file had changed | `serve.py` 发送 no-store；数据带有生成时间。建议给 `library.js` 加内容哈希（第 17 行） / `serve.py` sends no-store; data carries its build time. A content hash for `library.js` is recommended (row 17) |
| 4. a2 与 kp 不同步 / a2 and kp out of sync | 派生文件以节点号为键，而节点号取决于视频顺序，带有偶然性 / Derived files are keyed by node id and the ids are an accident of video order | 每个派生文件都带变化树指纹，合并前校验，自动重新分析，要点按位置对应（`treesync.py`） / Tree fingerprint in every derived file, check before merging, automatic re-analysis, notes follow their position (`treesync.py`) |
| 5. regen 用空壳覆盖了好的 SGF / Regen wrote empty shells | 路径用字符串拼接，没有检查输入是否存在，也没有和现有文件比较 / A path built with string concatenation, no check that inputs existed, no comparison with what was there | 处处使用 `os.path.join`，`regen.py` 有保护和试运行，`write_sgf` 拒绝无效或更差的文件 / `os.path.join` everywhere, `regen.py` guard and dry run, `write_sgf` refuses invalid or poorer files |
| 6. 一组 4 个视频下载失败 / Group of 4 failed to download | 一把锁在 40 次重试期间一直被占着，间隔很短，没有上限，也没有记录 / One lock held across 40 tries with a short sleep, no limit, no record | 退避重试，只在 yt-dlp 运行时持锁，放弃时写明原因，再来一轮，`failed_videos.json` / Backoff, lock only while yt-dlp runs, give up with a reason, second round, `failed_videos.json` |
| 7. Windows 的各种坑 / Windows quirks | 到处依赖平台默认值（cp936、ANSI、文本模式） / Platform defaults (cp936, ANSI, text mode) used everywhere | 显式 utf-8，读取兼容 BOM，写入统一为 LF，原子替换，并有测试在 `open()` 没写编码时失败 / Explicit utf-8, BOM tolerant reads, LF writes, atomic replace, a test that fails on an `open()` without encoding |
| 8. 辅助任务写不了文件，且没有任何提示 / Helpers could not write, silently | 文件不存在和"没有要做的事"看起来一样 / Absence of a file looked the same as "nothing to do" | 状态记录里写明需要多少条要点、找到多少条，低于 50% 时给出警告 / Status record says how many notes were wanted and found, warning below 50 percent |
| 9. 分析进度看不见 / Analysis progress invisible | 输出被捕获后丢弃，退出码被忽略 / Output captured to memory and dropped, exit code ignored | 每个分组一个日志，进度文件带预计剩余时间，退出码会被报告，并检测卡死 / Log file per group, progress file with ETA, exit code reported, stall detection |
| 10. 错别字规则把文字改坏 / Typo rules corrupted text | 依次执行 `str.replace`，短规则命中较长的正确词，一条规则的输出又被另一条规则处理 / Sequential `str.replace`, short rules inside longer correct words, the output of one rule fed to another | `fixtext.py`：最长优先，重复到稳定，保护词，规则日志 / `fixtext.py`: longest first, repeat until stable, protected words, rule log |
| 11. 写死的棋盘几何给出乱码结果 / Hard coded geometry gave garbage | 识别器无条件信任版式，看到什么就写什么 / The recogniser trusted the layout and wrote whatever it saw | 自检：尺寸、棋盘帧占比、网格对齐、棋子数量是否合理；被拒绝的视频会写明原因，也不会重试 / Self check: size, board share, grid alignment, stone sanity; rejected videos get a reason and are not retried |

共同点是：**某个阶段写出了看起来像结果的输出，却没有说明它由什么生成，也没有说明是否完整。** 修复的办法是给每个输出一个身份（指纹、meta），让"完成"真正意味着完整（原子写入、写入前校验），并让每一次拒绝都写明原因。

The common thread: **a stage wrote output that looked like a result without saying what it was made from or whether it was complete**. The fixes give each output an identity (fingerprint, meta), make "done" mean complete (atomic writes, checks before writing) and make every refusal say why.

## 2. 故障模式，按 L x I 排序 / Failure modes, ordered by L x I

| # | 故障模式 / Failure mode | 表现 / How it shows up | L x I | 对策 / Mitigation | 状态 / Status |
|---|---|---|---|---|---|
| 1 | 分组里某个视频后到或新增，变化树重建，节点号错位 / A video of a group arrives late or is added; the tree is rebuilt and node ids shift | AI 评估和要点落在错误的着法上，且没有任何报错 / AI evaluation and notes on the wrong moves, no error | 5x5 | `a2.json` 和 kp 里带指纹（`_meta`）；不匹配时旧文件改名为 `.stale` 并重新分析（设置 `NOAN` 则不带 AI 评估）；kp 要点按位置键迁移 / Fingerprint in `a2.json` and kp (`_meta`); a mismatch moves the old file to `.stale` and re-runs the analysis (or leaves AI out with `NOAN`); kp notes are carried over by position key | 已完成 / done |
| 2 | 下载被限流（HTTP 567、412、429） / Download throttled (HTTP 567, 412, 429) | 整组缺失；以前会卡半小时，且没有任何记录 / Whole group missing; before: half an hour blocked, nothing recorded | 5x4 | 60/180/540 秒退避，只在 yt-dlp 运行时持有下载锁，4 次后放弃并写明原因，`failed_videos.json`，停顿后再来一轮并重建不完整的分组 / Backoff 60/180/540 s, download lock only while yt-dlp runs, 4 tries then give up with the reason, `failed_videos.json`, a second round after a pause that rebuilds partial groups | 已完成 / done |
| 3 | 重跑、regen 或不完整的分组用更差的 SGF 覆盖了好的 SGF / Rerun, regen or a partial group overwrites a good SGF with a poorer one | 查看器里出现空的或没有 AI 评估的 SGF / Empty or AI-less SGF in the viewer | 4x5 | `sgfcheck` 校验，加上"节点、AI 节点、要点都不得减少"（老师讲解文字允许减少 20%）；被拒绝的候选文件放进 `work/rejected/`；`WEIQI_FORCE=1` 可强制覆盖；`regen.py --dry-run` 可试运行 / `sgfcheck` validation plus "never fewer nodes, AI nodes or notes" (teacher text may drop 20 percent); refused candidates go to `work/rejected/`; `WEIQI_FORCE=1` overrides; `regen.py --dry-run` | 已完成 / done |
| 4 | 写入过程中进程被杀 / Process killed during a write | 以前被截断的 json 会被永远当作已完成 / Truncated json treated as finished for ever (before) | 4x4 | 所有 json 和 sgf 都用 `atomic_write_*`（临时文件、fsync、替换，Windows 上文件被占用时重试）；残留的 `*.corrupt` 会被重做 / `atomic_write_*` for every json and sgf (temp file, fsync, replace, retry on a Windows lock); leftovers `*.corrupt` are redone | 已完成 / done |
| 5 | `sync_pipeline.ps1` 把旧的工作文件拷贝到 `pipeline/` 覆盖掉加固后的文件，而且不会拷贝新模块 / `sync_pipeline.ps1` copies the old working files over the hardened ones in `pipeline/`, and does not copy the new modules | 加固被悄悄回退，或出现 `ImportError: wqutil` / Hardening silently reverted, or `ImportError: wqutil` | 4x4 | 先把加固后的文件拷到 `D:\tmp\work`（见第 4 节）。建议：把新文件加进脚本的清单，并在拷贝前打印差异（单独的分支 `fix/sync-pipeline-script` 就是这么做的） / Copy the hardened files into `D:\tmp\work` first (section 4). Recommended: add the new files to the script's list and print a diff before copying (the separate branch `fix/sync-pipeline-script` does this) | 建议 / recommended |
| 6 | 另一种版式、分辨率或主题（其他 UP 主、回退到 1080p、棋盘不同的系列） / Another layout, resolution or theme (other uploader, 1080p fallback, series with a different board) | 变化树是乱码，分析结果无意义 / Garbage tree, nonsense analysis | 4x4 | `board.py` 检查尺寸、棋盘帧占比（至少 50%）、网格对齐（真实视频 46..91，其他版式 0..2）和棋子；被拒绝的视频生成 `b.rej.json`，不会重做 / `board.py` checks size, board share (at least 50 percent), grid alignment (real 46..91, other layouts 0..2) and stones; rejected videos get `b.rej.json` and are not redone | 已完成 / done |
| 7 | 长任务中 Whisper 或 KataGo 被杀或崩溃 / Whisper or KataGo killed or crashed during a long job | 损失 20 分钟 GPU 时间，或者卡死 / 20 minutes of GPU lost, or a hang | 4x3 | 分析每 25 个结果存一次检查点，同一棵变化树和同样设置下可断点续跑；引擎长时间无响应时，超过 `WEIQI_STALL_S` 就结束本次运行；`analyze2` 的退出码 2 到 5 各有含义 / Analysis checkpoints every 25 answers and resumes for the same tree and settings; a silent engine ends the run after `WEIQI_STALL_S`; `analyze2` exit codes 2 to 5 mean something | 已完成 / done |
| 8 | Windows 文本处理（cp936 控制台、没有 BOM 的 PowerShell、默认编码） / Windows text handling (cp936 console, PowerShell without BOM, default encodings) | 日志乱码、`UnicodeDecodeError`、脚本里的中文乱码 / Garbled logs, `UnicodeDecodeError`, garbled Chinese in scripts | 4x3 | utf-8 标准输出，子进程环境设置 `PYTHONUTF8`，显式编码（AST 测试），读取兼容 BOM。`sync_pipeline.ps1` 含中文却没有 BOM（测试里把它标为已知问题） / utf-8 stdio, child env `PYTHONUTF8`, explicit encodings (AST test), BOM tolerant reads. `sync_pipeline.ps1` has Chinese text and no BOM (the test marks it as known) | Python 部分已完成，脚本部分建议 / done for Python, recommended for the script |
| 9 | 网站改版后 yt-dlp 失效 / yt-dlp breaks when the site changes | 每个下载都因同样的提取器错误而失败 / Every download fails with the same extractor error | 3x4 | 每个视频都记录失败原因（`wq.py status`），快速失败能释放并发位。建议：原因不是 HTTP 状态码时，先升级 yt-dlp / The reason is stored per video (`wq.py status`), failing fast frees the slots. Recommended: update yt-dlp first when the reason is not an HTTP code | 建议 / recommended |
| 10 | `build.ps1` 骨架文本在 `C[...]` 里含有 `C[]`，导致 90 个占位 SGF 格式错误；`library.js` 不是原子写入 / `build.ps1` skeleton text contains `C[]` inside `C[...]`, so the 90 placeholder SGFs are malformed; `library.js` is written non-atomically | 其他 SGF 工具会拒绝这些文件；读取方可能看到写了一半的 `library.js` / Other SGF tools reject the files; a reader can see a half written `library.js` | 5x2 | 由 `sgfcheck` 发现（测试里跳过骨架文件）。建议：转义模板里的 `]`，先把 `library.js` 写到临时文件，再用 `Move-Item -Force` 替换 / Found by `sgfcheck` (the test skips skeletons). Recommended: escape `]` in the template and write `library.js` to a temp file, then `Move-Item -Force` | 建议 / recommended |
| 11 | 分数视角再次变化（引擎配置被改、KataGo 版本更新） / Score perspective changes again (engine config edited, new KataGo build) | 白棋的最佳着法算错 / Best move wrong for White | 2x5 | 启动时用让子局面实时检测，视角记录在 meta 里，每次加载都运行检测器（已校准：错误文件的首选点正确率为 13% 到 22%，正确文件为 100%）。实时检测需要引擎，目前只用模拟引擎测过 / Live handicap check at startup, mode recorded in meta, detector on every load (calibrated: wrong files 13 to 22 percent correct first candidate, right files 100 percent). The live check needs an engine and was only tested against a fake one | 已完成，实时检测未验证 / done, live check not verified |
| 12 | 写要点的辅助任务悄悄失败 / The helper that writes the key point notes fails silently | SGF 里没有要点 / SGF without notes | 3x3 | 状态里显示 `notes/wanted`，低于 50% 给出警告。建议：派发该任务的人事后运行 `wq.py status` / Status shows `notes/wanted`, warning below 50 percent. Recommended: whoever dispatches the helper runs `wq.py status` afterwards | 已完成 / done |
| 13 | 错别字词典越来越大，开始误伤 / The typo dictionary grows and starts to bite | 要点里出现奇怪的词，同一段文字在不同次运行间发生变化 / Odd words in the notes, text changes between runs | 3x3 | 最长优先，重复到稳定，保护词，`mkfix.py check` 遇到循环会失败，`fixlog_<group>.json` 列出触发过的规则。14784 条真实文本中有 24 条（三天低家之类）只有让规则互相衔接才能改对，所以才会重复到稳定为止 / Longest first, repeat until stable, protected words, `mkfix.py check` fails on cycles, `fixlog_<group>.json` lists what fired. 24 of the 14784 real texts (三天低家 and similar) only come out right because rules feed each other, which is why it repeats until stable | 已完成 / done |
| 14 | 新 UP 主的 `index.json` / `plan.json` 有误（未知编号、非法名称、季号不同） / A new uploader's `index.json` / `plan.json` is wrong (unknown id, bad name, other season) | 运行中途出现 `KeyError`，产生多余的文件夹 / `KeyError` in the middle of a run, stray folders | 4x2 | `validate_plan` 在任何工作开始前运行并列出所有问题（也检查 `index.json` 里重复的 idx 和缺少 bvid 的条目）；因 `WEIQI_MAX_IDX`（默认 49）而被跳过的分组会写进日志；UP 主和季号由 `WEIQI_SOURCE` / `WEIQI_SEASON` 指定 / `validate_plan` runs before anything starts and lists every problem (also duplicate idx values and entries without a bvid in `index.json`); groups skipped by `WEIQI_MAX_IDX` (default 49) are logged; uploader and season come from `WEIQI_SOURCE` / `WEIQI_SEASON` | 已完成 / done |
| 15 | 同时有两个 orch2 进程（误重启） / Two orch2 processes (restart by accident) | 重复下载，两个 GPU 任务，写入互相交错 / Double downloads, two GPU jobs, interleaved writes | 3x3 | 操作系统文件锁 `orch2.lock`，进程结束时自动释放；`WEIQI_NO_LOCK=1` 可跳过 / OS file lock `orch2.lock`, released when the process dies; `WEIQI_NO_LOCK=1` skips it | 已完成（锁已在 Windows 和 Linux 上测过） / done (lock tested on Windows and Linux) |
| 16 | 与机器相关的路径（ffmpeg 的 glob、`LOCALAPPDATA`、盘符） / Machine specific paths (ffmpeg glob, `LOCALAPPDATA`, drive letters) | 导入时出现 `IndexError` 或 `KeyError` / `IndexError` or `KeyError` at import | 3x3 | `find_ffmpeg`，用 `WEIQI_*` 环境变量覆盖路径且默认值与以前一致，导入 orch2 永远不会失败 / `find_ffmpeg`, `WEIQI_*` env overrides with the old defaults, importing orch2 never fails | 已完成 / done |
| 17 | 浏览器或文件缓存显示旧数据 / Browser or file cache shows old data | 用户看到的是旧页面 / The user looks at an old page | 3x2 | `serve.py` 使用 no-store。建议：在 `library.js` 的 URL 里加防缓存哈希（查看器由别人负责） / `serve.py` no-store. Recommended: a cache-busting hash in the `library.js` URL (the viewer is owned by someone else) | 建议 / recommended |
| 18 | 把被截断的下载或预览片段当成了完整视频 / Truncated download or a preview clip taken for the video | 变化树很短，内容缺失 / Short tree, missing content | 2x3 | 按 `index.json` 校验时长（低于 80% 的文件改名为 `v.mp4.short` 并重试） / Duration check against `index.json` (below 80 percent is moved to `v.mp4.short` and retried) | 已完成 / done |
| 19 | 空的或损坏的转写被当作已完成保存 / Empty or damaged transcript saved as done | 要点里没有老师讲解文字 / Notes with no teacher text | 2x3 | `tr.py` 会拒绝没有音频、没有语音、文字过少、替换字符过多的转写；零星的 U+FFFD（29 个真实文件中有 7 个）由 `fixtext` 去掉 / `tr.py` rejects no audio, no speech, far too little text, many replacement characters; stray U+FFFD (7 of 29 real files) are stripped in `fixtext` | 已完成 / done |
| 20 | 分组只用其中一部分视频生成 / A group is built from a subset of its videos | 得到不完整的 SGF，之后重建并重新分析（耗 GPU 时间） / Partial SGF, later rebuilt and re-analysed (GPU time) | 3x2 | 状态里写明 `missing_videos`；没有新内容时跳过重建；保护机制会保留内容更丰富的文件。建议：GPU 时间紧张时，等重试轮结束后再分析不完整的分组 / Status says `missing_videos`; the build is skipped if nothing changed; the guard keeps the richer file. Recommended: wait for the retry round before analysing partial groups if GPU time is tight | 部分完成 / partly |
| 21 | 磁盘已满、杀毒软件或查看器占用了文件 / Disk full, antivirus or the viewer holds a file | `PermissionError`，出现不完整的文件 / `PermissionError`, partial files | 2x3 | 原子替换最多重试 8 次；写入失败时保留旧文件，也不留下临时文件 / Atomic replace retries 8 times; a failed write leaves the old file and no temp file | 已完成 / done |
| 22 | 棋盘识别只读 19 列中的 18 列 / Board recognition reads 18 of 19 columns | 右边线上的棋子永远看不到 / Stones on the right edge line are never seen | 2x3 | 已在 `board.py` 里写明。没有改动：改了会让所有缓存里的每个点重新编号。以后可以做一次迁移，扫描全部 19 列，同时跳过水印所在的行 / Documented in `board.py`. Not changed: it would renumber every point in every cache. A later migration could scan all 19 columns while skipping the watermark rows | 建议 / recommended |
| 23 | 第一次重建时 SGF 的换行符从 CRLF 变成 LF / SGF line endings change from CRLF to LF on the first rebuild | git 差异很大，但功能没有变化 / Large git diff, no functional change | 5x1 | 现在所有写入统一为 LF；已在 PR 中说明 / Writes are LF everywhere now; mentioned in the PR | 接受 / accepted |

## 3. 在真实数据上检查了什么 / What was checked on real data

以下检查全部是只读的，对象是临时目录里的副本，或用 ffmpeg 解码出的画面。

Everything here was read only, on copies in a scratch folder or on frames decoded with ffmpeg.

* 用缓存文件的副本对四个已生成的分组运行 `stageB` 做了彩排：生成的 SGF 与已发布的完全一致，只有两点不同，零星的 U+FFFD 字符消失了，隐争/隐真这条规则链现在有两处以"引征"结尾。节点数、AI 节点数和要点数都相同。
* Dress rehearsal of the four generated groups with `stageB` on copies of the cached files: the SGFs come out identical to the shipped ones except that stray U+FFFD characters are gone and the 隐争/隐真 rule chain now ends in 引征 in two places. Node counts, AI nodes and notes are equal.
* 分数视角检测器能标出全部四个旧的黑方视角 `a.json` 文件，并接受真实的 `a2.json`。
* The score perspective detector flags all four old Black-perspective `a.json` files and accepts the real `a2.json`.
* 对 30 个已下载视频各取 2 帧做棋盘自检：网格得分 46 到 91（门槛 20）；错误版式得分 0 到 2。在 480 个真实画面上的识别结果与旧的 `b.json` 完全一致。用一段 20 秒的真实片段做了端到端运行，结果正常；重新编码成 1280x720 和灰度的版本都被正确拒绝，并给出了正确原因。
* Board self check on 2 frames from each of the 30 downloaded videos: grid score 46 to 91 (limit 20); wrong layouts 0 to 2. Recognition on 480 real frames is identical to the old `b.json`. End to end on a real 20 second clip works; a 1280x720 re-encode and a greyscale re-encode are rejected with the right reason.
* 错别字词典在 14784 条真实文本（转写和要点）上：有 7 条与旧输出不同（就是那条只改了一半的规则链），再处理一遍后 0 条变化（旧代码是 8 条）。
* Typo dictionary on 14784 real texts (transcripts and notes): 7 differ from the old output (the half done chain), 0 change on a second pass (8 did with the old code).
* `sgfcheck` 接受所有有内容的 SGF；`build.ps1` 生成的 90 个占位文件校验不通过（第 10 行）。
* `sgfcheck` accepts every SGF that has content; the 90 `build.ps1` placeholders fail (row 10).

## 4. 采用加固后的文件（建议顺序） / Adopting the hardened files (recommended order)

* 第 1 步：先让正在运行的流水线处理完当前分组（`logs/orch2.log` 或旧日志里出现 `B done` 一行），或者接受正在进行的分析丢失：旧的 `analyze2.py` 不能断点续跑。
* Step 1: Let the running pipeline finish the current group (a `B done` line in `logs/orch2.log` or the old log), or accept losing the running analysis: the old `analyze2.py` cannot resume.
* 第 2 步：备份 `D:\tmp\work\*.py`，然后把本分支 `pipeline/*.py` 全部拷进 `D:\tmp\work`（新模块：`wqutil.py treesync.py sgfcheck.py fixtext.py wq.py`，它们必须和 `orch2.py` 放在同一目录）。保留你现有的 `fixdict.json`。
* Step 2: Back up `D:\tmp\work\*.py`, then copy all of `pipeline/*.py` from this branch into `D:\tmp\work` (new modules: `wqutil.py treesync.py sgfcheck.py fixtext.py wq.py`; they must sit next to `orch2.py`). Keep your `fixdict.json`.
* 第 3 步：把 `PYTHONUTF8=1` 设为用户环境变量。
* Step 3: Set `PYTHONUTF8=1` as a user environment variable.
* 第 4 步：运行 `python wq.py fix-check D:\tmp\work\fixdict.json` 和 `python regen.py --dry-run`。试运行会逐个分组打印"会写入"还是"会拒绝"，不会写任何文件。
* Step 4: `python wq.py fix-check D:\tmp\work\fixdict.json` and `python regen.py --dry-run`. The dry run prints for every group whether it would write or refuse; nothing is written.
* 第 5 步：对现有的四个分组依次运行 `python wq.py check "<分组>"` 和 `python wq.py stamp "<分组>"`，给它们的 a2.json 和 kp 文件补上指纹。不补也能用，但会被标为"legacy"并给出警告。
* Step 5: For the four existing groups run `python wq.py check "<group>"` and then `python wq.py stamp "<group>"`, so that their a2.json and kp files get a fingerprint. Without it they still work but are marked "legacy" with a warning.
* 第 6 步：照常启动 orch2，用 `python wq.py status` 观察。
* Step 6: Start orch2 as before. Watch with `python wq.py status`.
* 第 7 步：在第 2 步完成之前，不要运行 `tools/sync_pipeline.ps1`（第 5 行）。
* Step 7: Do not run `tools/sync_pipeline.ps1` before step 2 (row 5).

## 5. 命令与设置 / Commands and settings

| 命令 / Command | 作用 / What it does |
|---|---|
| `python orch2.py` | 流水线本体（第二次启动会被锁拒绝） / The pipeline (a second start is refused by the lock) |
| `python regen.py [--dry-run] [--only NAME] [--analyze] [--force]` | 用缓存重新生成 SGF / Rebuild SGFs from the cache |
| `python wq.py status / check NAME / stamp NAME / validate PATH / fix-check` | 查看和确认，不会启动任何重任务 / Look and bless, never start heavy work |
| `python mkfix.py check / normalize / add a=b / apply file` | 错别字词典维护 / Typo dictionary maintenance |
| `docker build -t weiqi-pipeline-tests . && docker run --rm weiqi-pipeline-tests` | 全部测试，不需要 GPU、视频和 KataGo / All tests, no GPU, no video, no KataGo |

设置都是环境变量，默认值与改动前一致：`WEIQI_WORK`、`WEIQI_PROJ`、`WEIQI_SOURCE`、`WEIQI_SEASON`、`WEIQI_MAX_IDX`、`WEIQI_PY`、`FFMPEG`、`WEIQI_KATAGO_ROOT|DIR|MODEL`、`WEIQI_REPORT_AS`、`WEIQI_WINDOW`、`WEIQI_STALL_S`、`WEIQI_ANALYZE_TIMEOUT`、`WEIQI_DL_TRIES`、`WEIQI_DL_BACKOFF`、`WEIQI_DL_TIMEOUT`、`WEIQI_STAGE_TIMEOUT`、`WEIQI_RETRY_ROUNDS`、`WEIQI_RETRY_WAIT`、`WEIQI_RETRY_REJECTED`、`WEIQI_MIN_BOARD_RATIO`、`WEIQI_MIN_GRID_SCORE`、`WEIQI_STRICT`、`WEIQI_FORCE`、`WEIQI_NO_LOCK`、`NOAN`、`LIMIT`。

Settings are environment variables with the old values as defaults: `WEIQI_WORK`, `WEIQI_PROJ`, `WEIQI_SOURCE`, `WEIQI_SEASON`, `WEIQI_MAX_IDX`, `WEIQI_PY`, `FFMPEG`, `WEIQI_KATAGO_ROOT|DIR|MODEL`, `WEIQI_REPORT_AS`, `WEIQI_WINDOW`, `WEIQI_STALL_S`, `WEIQI_ANALYZE_TIMEOUT`, `WEIQI_DL_TRIES`, `WEIQI_DL_BACKOFF`, `WEIQI_DL_TIMEOUT`, `WEIQI_STAGE_TIMEOUT`, `WEIQI_RETRY_ROUNDS`, `WEIQI_RETRY_WAIT`, `WEIQI_RETRY_REJECTED`, `WEIQI_MIN_BOARD_RATIO`, `WEIQI_MIN_GRID_SCORE`, `WEIQI_STRICT`, `WEIQI_FORCE`, `WEIQI_NO_LOCK`, `NOAN`, `LIMIT`.

工作目录里新增的文件：`logs/orch2.log`、`logs/analyze_<分组>.log`、`failed_videos.json`、`status_<分组>.json`、`fixlog_<分组>.json`、`kpin_<分组>.meta.json`、`rejected/<分组>.sgf`；在 `g_<分组>.a2.json` 旁边有 `.part`、`.progress.log`、`.progress.json`、`.stale`；每个视频目录下有 `b.meta.json`、`b.rej.json`、`t.rej.json`、`v.mp4.short`、`*.corrupt`。

New files in the work dir: `logs/orch2.log`, `logs/analyze_<group>.log`, `failed_videos.json`, `status_<group>.json`, `fixlog_<group>.json`, `kpin_<group>.meta.json`, `rejected/<group>.sgf`, next to `g_<group>.a2.json`: `.part`, `.progress.log`, `.progress.json`, `.stale`; per video: `b.meta.json`, `b.rej.json`, `t.rej.json`, `v.mp4.short`, `*.corrupt`.

## 6. 尚未验证 / Not verified

* 没有真实运行过 KataGo：启动时的让子局面检测（查询里的 `initialPlayer`）、请求窗口和检查点，都只在 `tests/fake_katago.py` 上跑过。
* A real KataGo run: the startup handicap check (`initialPlayer` in the query), the request window and the checkpoints were only exercised against `tests/fake_katago.py`.
* 没有真实运行过 yt-dlp 或 whisper：重试、超时和拒绝这几条路径用的是模拟对象；`board.py` 则在真实片段上跑过。
* A real yt-dlp or whisper run: the retry, timeout and rejection paths use fakes; `board.py` was run on real clips.
* PowerShell 脚本只读过，没有运行过，本分支也没有改动它们。
* PowerShell scripts were read, not run, and not changed on this branch.
* 没有改动查看器。它只读取 SGF；`C[]` 里的 LF 换行应该没有问题，因为它用 `white-space: pre-wrap` 显示评论，但没有在浏览器里实际试过。
* The viewer was not touched. It only reads the SGFs; LF line endings in `C[]` should be fine because it shows comments with `white-space: pre-wrap`, but that was not tried in a browser.
