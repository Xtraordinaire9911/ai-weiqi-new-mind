# ai-weiqi-new-mind

围棋定式、套路和避雷的“AI + 老师讲解”学习库。把围棋老师的视频讲解整理成 **SGF 变化树**，每一手配上：

A study library of Go joseki, trick openings and trap avoidance, built from a teacher's video lessons plus KataGo analysis. Each lesson becomes an **SGF variation tree**, and every move carries:

- **老师讲解**：视频语音的转写，按时间点可以跳回视频。

  **Teacher's commentary**: the speech of the video, transcribed, with timestamps that jump back to the video.

- **要点与考量**：从口述里提炼出的取舍理由、周边条件和避雷要点。

  **Key points and reasoning**: the trade-offs, surrounding conditions and traps, distilled from the spoken explanation.

- **AI 局部评估**：KataGo 只在该定式涉及的区域内搜索，给出每个候选点比局部最优差几目；老师走的每一手都会单独评估。

  **Local AI evaluation**: KataGo searches only inside the area the joseki involves and reports how many points each candidate is worse than the local best. Every move the teacher plays is evaluated separately.

- **周边子力影响**：去掉区域外的子力之后，结论是否会变化。

  **Influence of surrounding stones**: whether the conclusion changes once the stones outside the area are removed.

它要解决的痛点是：KataGo 只会看全局胜率，想只研究局部定式、又想知道周边子力或征子如何影响选择，并不方便。

The problem it tries to solve: KataGo only shows the whole-board winrate, which is awkward when you want to study one local joseki and still see how the surrounding stones or a ladder (征子) change the choice.

> 当前版本 **v0.1**（见 [CHANGELOG.md](CHANGELOG.md)）。这是第一个快照，内容仍在持续生成。
>
> Current version **v0.1** (see [CHANGELOG.md](CHANGELOG.md)). This is the first snapshot, and content is still being generated.

## v0.1 现状 / Status at v0.1

下表描述的是 v0.1 快照时仓库的状态。系列名和分组名沿用视频里的中文名称，不做翻译。

The table describes the repository at the v0.1 snapshot. Series and group names are the Chinese names used in the videos, so they are kept as they are.

| 项目 / Item | 状态 / State |
|---|---|
| 陈林涛《定式大全》（B 站 1500387） / 陈林涛 (Chen Lintao) 《定式大全》 (Bilibili 1500387) | 已生成 4 个 SGF：星位-点三三、星位-小飞挂-小飞守角与托角连扳、星位-小飞挂-一间低夹、小目-小飞挂-二间高夹；该系列其余 27 个分组仍是空壳，后台流水线继续生成 / 4 SGFs are filled: 星位-点三三, 星位-小飞挂-小飞守角与托角连扳, 星位-小飞挂-一间低夹, 小目-小飞挂-二间高夹. The other 27 groups of the series are empty placeholders, and the background pipeline keeps generating them |
| AI 局部评估 / Local AI evaluation | 只有 小目-小飞挂-二间高夹 带有新版评估；其余 3 个暂时没有（旧结果因分数视角错误已撤下，正在重新分析） / Only 小目-小飞挂-二间高夹 has the new evaluation. The other 3 have none for now: the old results were withdrawn because of a score perspective error, and re-analysis is in progress |
| 套路研究、避雷两个系列，高目，江维杰《AI围棋定式大全》 / The 套路研究 and 避雷 series, 高目, and 江维杰 《AI围棋定式大全》 | 尚未开始；前两个系列目前只有空的占位文件 / Not done yet; the first two series only have empty placeholder files |
| 语音转写错字 / Typos in the speech transcripts | 已用词典批量修正（`pipeline/fixdict.json`），仍有残留 / Fixed in bulk with a dictionary (`pipeline/fixdict.json`), some remain |

## 即将到来 / Upcoming

有两处查看器改动和一个工具目录还在各自的 PR 里等待合并，它们还不在 `develop` 中，下文描述的查看器也还没有这些功能。第一个是在棋盘上悬停老师变化分支的圈时预览该分支；第二个是可选的算力开关，默认使用缓存数据，也可以连接你自己运行的 KataGo 做实时分析；第三个是 `remote/`，一组用来在显卡更强的机器上批量运行 KataGo 分析的脚本。合并之前，请把这三项都当作计划。

Two viewer changes and one tool folder are waiting in separate open pull requests. They are not in `develop` yet, and the viewer described below does not have them. The first is a preview of a teacher's branch when you hover its circle on the board. The second is an optional compute switch that stays on the cached data by default and can connect to a KataGo that you run yourself for live analysis. The third is `remote/`, a set of scripts for running the KataGo batch analysis on a machine with a better GPU. Until they are merged, treat all three as plans.

## 使用 / Usage

双击 `index.html` 即可使用（离线，数据在 `data/library.js`）。如果浏览器限制了 `file://`，可以运行 `python pipeline/serve.py`，它是一个不带缓存的本地服务，端口 8765。它所服务的目录写死在脚本开头，换机器时需要修改。

Double-click `index.html` (offline, the data is in `data/library.js`). If your browser restricts `file://`, run `python pipeline/serve.py`, a local server without caching on port 8765. The folder it serves is hard-coded at the top of the script, so edit it for your machine.

方向键 ←→ 步进，↑↓ 选择变化。棋盘上，**半透明棋子是 AI 候选点**（颜色为行棋方），**圈的颜色和数字表示这一手比局部最优差几目**，**蓝色虚线圈加序号是老师在视频里走的变化**。悬停在候选点上可以查看 AI 的变化图，点击则固定。页面左上角显示界面版本和数据时间。

Use ←→ to step and ↑↓ to choose a variation. On the board, a **translucent stone is an AI candidate** (its color is the side to move), the **ring color and number show how many points worse than the local best** the move is, and a **blue dashed ring with a number is a variation the teacher played in the video**. Hover a candidate to see the AI variation, click to pin it. The top left of the page shows the interface version and the data time.

## 目录 / Layout

| 路径 / Path | 说明 / What it is |
|---|---|
| `index.html` | 单文件查看器 / Single-file viewer |
| `data/sgf/…` | 生成的 SGF，标准 SGF 格式，可用 Lizzie、KataGo GUI、Sabaki 打开（`PL`、`AN` 属性按本项目自己的约定使用） / Generated SGF files, standard SGF that opens in Lizzie, KataGo GUI and Sabaki (`PL` and `AN` are used in a project-specific way) |
| `data/sources/…` | 视频清单与合并计划，`plan.json` 决定哪些视频合成一个 SGF / Video lists and merge plans; `plan.json` decides which videos are merged into one SGF |
| `data/library.js` | 打包文件，由 `tools/build.ps1` 生成 / Bundle generated by `tools/build.ps1` |
| `tools/` | `build.ps1` 打包数据，`fetch_playlists.ps1` 抓取播放列表，`sync_pipeline.ps1` 同步流水线脚本，`local_analyze.ps1` 在限定的矩形区域内运行 KataGo 搜索 / `build.ps1` bundles the data, `fetch_playlists.ps1` fetches the playlists, `sync_pipeline.ps1` syncs the pipeline scripts, `local_analyze.ps1` runs a KataGo search restricted to a rectangle |
| `pipeline/` | 无人值守的流水线：下载、转写、识谱、变化树、KataGo、SGF / The unattended pipeline: download, transcription, board recognition, variation tree, KataGo, SGF |
| `engine-config/` | KataGo 配置（不含程序和权重） / KataGo configuration (no binaries, no weights) |
| `docs/usage.md` | 命名规则、SGF 约定、如何新增 UP 主 / Naming rules, SGF conventions, how to add a new uploader |
| `CHANGELOG.md`, `VERSION` | 版本记录与当前版本号 / Release notes and the current version number |

## 流水线（`pipeline/`） / Pipeline (`pipeline/`)

`orch2.py` 全自动运行：yt-dlp 下载，然后依次是 `tr.py`（faster-whisper）、`board.py`（OpenCV 识谱）、变化树、`analyze2.py`（KataGo 分析），最后合成 SGF。`regen.py` 用缓存重新生成 SGF，改完错字词典后使用，设置 `NOAN=1` 可以跳过分析。脚本里的路径是写死的 Windows 路径（`D:\tmp\work` 等），换机器需要修改。

`orch2.py` runs everything unattended: yt-dlp download, then `tr.py` (faster-whisper), then `board.py` (OpenCV board recognition), then the variation tree, then `analyze2.py` (KataGo analysis), then the SGF. `regen.py` regenerates the SGF files from the cache; use it after editing the typo dictionary, and set `NOAN=1` to skip the analysis. The paths in the scripts are hard-coded Windows paths (`D:\tmp\work` and so on), so they need editing on another machine.

要点摘要 `kp_*.json`（节点号对应要点）由大模型根据口述提炼。

The key point summaries `kp_*.json` (node number to key point) are written by a large language model from the spoken explanation.

### 关键正确性约定（踩过的坑，见 CHANGELOG） / Correctness rules (learned the hard way, see CHANGELOG)

- KataGo 配置了 `reportAnalysisWinratesAs=BLACK`，所有分数都是黑方视角，排序前**必须换算成行棋方视角**。

  KataGo runs with `reportAnalysisWinratesAs=BLACK`, so every score is from Black's perspective and **must be converted to the side to move's perspective** before sorting.

- 只搜局部区域时，不展示全盘胜率，只展示比局部最优差几目。

  When only a local area is searched, do not show the whole-board winrate. Show only how many points worse than the local best.

- 行棋方由 SGF 的 `PL[]` 属性给出；变化预览里的棋子颜色从行棋方开始交替。

  The side to move comes from the SGF `PL[]` property, and the stone colors of a variation preview alternate starting from the side to move.

- 老师走的着法不一定在 KataGo 的前几选里，必须单独评估，并在棋盘上标出。

  The teacher's move is not always among KataGo's top choices, so it has to be evaluated separately and marked on the board.

## 内容来源与版权 / Content sources and copyright

- 老师讲解文字来自 B 站 UP 主 **陈林涛** 公开视频语音的自动转写与整理。视频和讲解内容的版权归原作者所有，讲解文字不在本仓库任何许可证的覆盖范围内；本项目仅用于个人学习研究。**如原作者或权利人提出要求，将立即移除相关内容。**

  The teacher's commentary text is an automatic transcription and cleanup of the speech in the public videos of the Bilibili uploader **陈林涛** (Chen Lintao). The copyright of the videos and of the commentary belongs to the original author. The commentary text is not covered by any license of this repository, and the project is for personal study and research only. **If the original author or rights holder asks, the content will be removed right away.**

- 不包含视频文件、KataGo 程序和神经网络权重，请自行从官方渠道获取，例如 KataGo 官方发布页。

  No video files, KataGo program or neural network weights are included. Please get them from the official sources, for example the KataGo releases page.

## 许可证 / License

代码采用 PolyForm Strict License 1.0.0 许可。为本项目编写的数据和文档采用 CC BY-NC-ND 4.0 许可。老师的讲解文字不在这两份许可的范围内：它不受任何一份许可覆盖，仍归原作者所有，之后会迁移到私有仓库。详情见 [NOTICE.md](NOTICE.md)。

The code is licensed under the PolyForm Strict License 1.0.0. The data and documents written for this project are licensed under CC BY-NC-ND 4.0. The teacher's commentary text is excluded from both: it is not covered by either license, it stays with its original author, and it will be moved to a private repository. See [NOTICE.md](NOTICE.md) for the details.

## 版本策略 / Version policy

在 `v0.x` 阶段，只有一大批新视频处理完毕并入库之后才会升版本号，所以不会频繁发版。等陈林涛的全部视频都处理完、查看器和 SGF 也打磨好之后，再考虑 `v1.x`。

While the project is on `v0.x`, the version is bumped only when a big batch of new videos has been processed and added, so releases are rare. `v1.x` is considered after all of 陈林涛's videos are finished and the viewer and the SGF files are polished.
