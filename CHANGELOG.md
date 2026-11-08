# 更新日志 / Changelog

本项目所有值得记录的改动都写在这里。格式遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),版本号遵循[语义化版本 2.0.0](https://semver.org/lang/zh-CN/)。0.x 阶段何时升版本号,见 [docs/WORKFLOW.md](docs/WORKFLOW.md) 第 7 节。

All notable changes to this project are recorded here. The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the version numbers follow [Semantic Versioning 2.0.0](https://semver.org/). When to bump the version during the 0.x phase is described in section 7 of [docs/WORKFLOW.md](docs/WORKFLOW.md).

## 未发布 / [Unreleased]

### 新增 / Added

- 分支模型:`main` 放已发布的版本,`develop` 做集成,另有 `feature/<topic>`、`fix/<topic>`、`data/<batch>`、`release/<version>` 和 `hotfix/<topic>`。步骤和命令见 `docs/WORKFLOW.md`。

  Branching model: `main` for released versions, `develop` for integration, `feature/<topic>`, `fix/<topic>`, `data/<batch>`, `release/<version>` and `hotfix/<topic>`. Steps and commands are in `docs/WORKFLOW.md`.

- `CONTRIBUTING.md`:提交信息的写法(Conventional Commits,简短、像人写的)、贡献条款(DCO 签署加一句重新授权的说明),以及 `.gitmessage` 模板。

  `CONTRIBUTING.md` with the commit message style (Conventional Commits, kept short and human), the contribution terms (DCO sign off plus a relicensing sentence), and a `.gitmessage` template.

- 一份简短的 PR 模板和三个 issue 表单(bug 报告、内容问题、视频建议)。

  A short pull request template and three issue forms (bug report, content issue, video suggestion).

- `tools/check_repo.py`:只需要 Python 3 的本地检查,涵盖 `index.html` 的引用、JSON 文件、`data/library.js` 与 SGF 文件是否一致、SGF 语法、Python 语法、不该提交的文件,以及一个粗略的令牌扫描。

  `tools/check_repo.py`, a local check that needs only Python 3: references in `index.html`, JSON files, `data/library.js` against the SGF files, SGF syntax, Python syntax, files that should not be committed, and a rough token scan.

- `docs/LICENSE-ADVICE.md`:许可证的决定(代码用 PolyForm Noncommercial,我们自己的数据和文档用 CC BY-NC-SA,要求署名,老师的讲解文字除外;更严的 PolyForm Strict 和 CC BY-NC-ND 考虑过但没有采用)以及背后的对比分析;`docs/COMPUTE-PLATFORMS.md`:云 GPU 方案清单,附 LRZ 说明。LICENSE 文件本身放在单独的 PR 里。

  `docs/LICENSE-ADVICE.md`, the license decision (PolyForm Noncommercial for the code, CC BY-NC-SA for our own data and docs, credit required, the teacher's commentary excluded; the stricter PolyForm Strict and CC BY-NC-ND were considered and not chosen) with the comparison behind it, and `docs/COMPUTE-PLATFORMS.md`, a list of cloud GPU options with notes on LRZ. The LICENSE files themselves come in a separate pull request.

- 文档采用双语形式:一段中文,紧跟对应的英文。

  The docs are bilingual, a Chinese paragraph followed by its English counterpart.

### 变更 / Changed

- `.gitignore` 现在还涵盖视频、音频、网络权重和凭据文件。新增的 `.gitattributes` 让 SGF 文件和 `data/library.js` 保持 LF 换行。

  `.gitignore` now also covers video, audio, network weights and credential files. New `.gitattributes` keeps SGF files and `data/library.js` on LF line endings.

- 查看器的视野改为完全由用户控制:去掉了「视角:自动」(它会在讲解提到征子、外势等词时自己切到全盘)。现在有「聚焦 / 扩大 / 全盘」三档,用棋盘下方的「－」「＋」逐档缩放,选择会记在浏览器里,换手、换棋谱集合都不变。聚焦范围仍按每个棋谱集合的棋子算一次。讲解提到的外围子如果在当前范围之外,提示条会写出来并带「显示全盘」按钮,由你决定要不要看。

  The viewer's zoom is now controlled by the user only. The "视角:自动" mode is gone: it switched to the full board by itself when the commentary mentioned things like 征子 or 外势. There are three steps (聚焦 focus / 扩大 wider / 全盘 full board), changed with the "－" and "＋" buttons under the board, remembered in the browser and unchanged when you step or switch collection. The focus crop is still computed once per collection from its stones. If outer stones mentioned in the commentary are outside the current view, the hint line says so and offers a "显示全盘" button, so you decide whether to look.

- 控制栏改成固定几何:每个按钮宽度固定,按钮位置不随手数、缩放、讲解或棋谱集合变化(「演示征子」不再隐藏,只是变灰),缩放按钮和步进按钮之间有空档和分隔线,说明条和手顺栏的空间是预留的,棋盘列在出现滚动条时也不会变窄。手机和平板上是 6 列 2 行的网格。

  The control bar now has a fixed geometry. Every button has a fixed width and keeps its place whatever the move, zoom, commentary or collection is (the ladder demo button is dimmed instead of hidden), the zoom buttons are set apart from the step buttons by a gap and a rule, the caption strip and the path bar have reserved space, and the board column keeps its width when a scrollbar appears. On phones and tablets the bar is a grid of 6 columns and 2 rows.

- 新增快进和快退:⏪ 后退 5 手,⏩ 前进 5 手(沿右侧列表选中的变化走,到终点为止),键盘用 PageUp、PageDown 或 Shift+左右方向键。「上一手」不再走到根节点之前的空棋盘上。

  Added fast rewind and fast forward: ⏪ back 5 moves, ⏩ forward 5 moves (along the variation selected in the right-hand list, up to the end of the line), with PageUp, PageDown or Shift with the left and right arrows on the keyboard. The previous button no longer steps past the first node onto an empty board.

### 修复 / Fixed

- `tools/build.ps1` 写出的占位 SGF 文件,文字里带有未转义的 `]`(就是 "C[]" 这几个字),所以不是合法的 SGF。现在改了文字,并且对分组名、来源名和视频标题做了转义。仓库里已有的 90 个占位文件没有动,等对应分组填充内容时会被替换,`tools/check_repo.py` 把它们汇总成一条警告。

  The placeholder SGF files written by `tools/build.ps1` contained an unescaped `]` in their text (the words "C[]"), so they were not valid SGF. The text is changed and group names, source names and video titles are now escaped. The 90 placeholders already in the repo are untouched, they get replaced when a group is filled in, and `tools/check_repo.py` reports them as one warning.

## [0.1] - 2026-11-01

第一个快照。之前的改动没有版本记录,无法重建,所以把当时的状态称为 v0.1(按语义化版本视为 0.1.0;已有的标签 `v0.1` 保持不变,之后的版本使用三段式,例如 `v0.2.0`)。

First snapshot. Earlier changes were not versioned and cannot be rebuilt, so the state at this point is called v0.1 (read as 0.1.0 under SemVer; the existing tag `v0.1` stays as it is and later versions use three numbers, such as `v0.2.0`).

### 新增 / Added

- 查看器 `index.html`:浏览 SGF 变化树;老师讲解、要点、引擎评估和周边子力的卡片;候选点悬停预览、点击固定;老师的着法用蓝色虚线圈加序号标出;视频时间点链接;局部聚焦和全盘两种视角,并带征子演示;版本号和数据时间戳。

  Viewer `index.html`: browse the SGF variation tree; cards for the teacher's commentary, key points, engine evaluation and nearby stones; hover preview and click to pin for candidate moves; the teacher's moves as dashed blue circles with sequence numbers; links to video time stamps; focused and whole board views with a ladder demo; version and data time stamps.

- 数据:陈林涛《定式大全》的四个分组已做成 SGF(其中一个带有新版引擎评估);视频清单和合并计划;约 300 条的错别字词典。

  Data: four groups of Chen Lintao's "Joseki Encyclopedia" as SGF (one of them with the new engine evaluation); the video list and merge plan; a typo dictionary of about 300 entries.

- 流水线:下载、Whisper 转写、OpenCV 识别棋盘、构建变化树、KataGo 局部分析(只分析分叉点,老师的着法一定会评估)、输出 SGF。

  Pipeline: download, Whisper transcription, OpenCV board recognition, variation tree, KataGo local analysis (branch points only, the teacher's moves always evaluated), SGF output.

### 修复 / Fixed

- 沿途发现并修复的严重错误:(1) KataGo 的目差是从黑方视角给出的,没有换算成行棋方视角,导致"最优"点选错;(2) 变化预览里的棋子颜色反了;(3) 没有显示老师的着法;(4) 缓存导致页面是旧的;(5) 局部搜索下的全盘胜率没有意义,已经去掉。

  Serious mistakes found along the way: (1) KataGo scores are from Black's point of view and were not converted, so the "best" move was wrong; (2) stone colors in variation previews were swapped; (3) the teacher's moves were not shown; (4) caching served an old page; (5) the whole board winrate is meaningless under a local search and was removed.

[Unreleased]: https://github.com/Xtraordinaire9911/ai-weiqi-new-mind/compare/v0.1...develop
[0.1]: https://github.com/Xtraordinaire9911/ai-weiqi-new-mind/releases/tag/v0.1
