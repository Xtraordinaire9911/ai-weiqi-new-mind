# 私有数据与讲解文字 / Private data and the teacher commentary

本文说明老师口述讲解的文字放在哪里、公开仓库发布什么、日常怎么同步,以及还没有决定的事项。本文只是方案和操作说明:这个分支没有改动任何公开数据,没有改写历史,也没有执行流水线切换。

This document says where the teacher's spoken commentary lives, what the public repository publishes, how the daily sync works, and what is still undecided. It is a plan and a set of instructions only: this branch does not change any public data, does not rewrite history and does not perform the pipeline cutover.

## 背景 / Background

SGF 注释里以 `【老师讲解` 开头的段落,是陈林涛老师视频讲解的转写。这些文字的版权属于原作者,不属于本项目(见 `NOTICE.md`)。要点笔记、AI 评估、时间链接和视频链接是本项目自己的产出,可以公开。

The paragraphs that start with `【老师讲解` in the SGF comments are transcripts of the spoken commentary in the videos of 陈林涛. The copyright of that text belongs to the original author, not to this project (see `NOTICE.md`). The key point notes, the AI evaluation, the time links and the video links are this project's own output and can be public.

因此决定把完整数据放进一个私有仓库 `Xtraordinaire9911/ai-weiqi-new-mind-data`。公开仓库以后只发布去掉讲解文字的版本。

So the full data goes into a private repository, `Xtraordinaire9911/ai-weiqi-new-mind-data`. From now on the public repository only ships a version with the commentary text removed.

目前的实际情况:`main` 和 `develop` 上仍有 5 个 SGF 文件含有 `【老师讲解 @` 的讲解文字,公开历史里也有包含这些文字的提交。这个分支没有处理它们,是否清理历史要由你决定(见下面的待决事项)。

The current situation: `main` and `develop` still hold 5 SGF files that contain teacher text under `【老师讲解 @`, and the public history has commits that contain that text. This branch does not touch them. Whether to clean the history is your decision (see the open decisions below).

## 目标流程 / Intended flow

完整数据只在私有仓库里保存。流水线产出的 SGF、`library.js` 和要点笔记先进入私有克隆,在那里提交。公开仓库每次发布前,用 `tools/strip_commentary.py` 从私有数据生成去掉讲解文字的副本,再把副本放进公开仓库的 `data/`。

The full data is kept in the private repository only. The SGF files, `library.js` and key point notes produced by the pipeline go into the private clone and are committed there. Before each public release, `tools/strip_commentary.py` makes a copy without the commentary text from the private data, and that copy is what goes into `data/` of the public repository.

在切换流水线输出位置之前(现在的状态),流水线仍然写进工作克隆,用 `tools/sync_private_data.ps1` 把数据复制到私有克隆:

Until the pipeline output is moved (the state today) the pipeline still writes into the working clone, and `tools/sync_private_data.ps1` copies the data into the private clone:

```
powershell -NoProfile -ExecutionPolicy Bypass -File tools\sync_private_data.ps1 -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File tools\sync_private_data.ps1
git -C D:\workspace\fun\Weiqi\ai-weiqi-new-mind-data push
```

同步脚本只读工作克隆,只往私有克隆里复制和提交,不推送,从不删除私有克隆里的文件,也不会复制空文件或写到一半的文件(写入中的文件会重读最多 3 次,仍在变化就跳过并列出)。目标的远程地址必须以 `-data` 结尾,否则拒绝运行,以免把完整数据复制进公开仓库。

The sync script only reads the working clone and only copies into and commits in the private clone. It does not push, never deletes a file in the private clone and never copies an empty or half written file (a file that is being written is read again up to 3 times, and skipped and listed if it keeps changing). The remote of the destination must end in `-data`, otherwise the script refuses to run, so the full data cannot be copied into the public repository by mistake.

生成公开副本(输入文件夹只读,输出必须是另一个文件夹):

To make the public copy (the input folder is read only, the output must be a different folder):

```
python tools/strip_commentary.py D:\workspace\fun\Weiqi\ai-weiqi-new-mind-data D:\tmp\public_data --check
```

脚本复用 `tools/make_site.py --strip-commentary` 的逻辑:讲解段落的标题和时间链接保留,正文换成一句提示,查看器仍会显示「老师讲解」卡片并能跳到视频的对应时刻。`--check` 会重新读取输出,确认没有讲解文字残留,并且 `library.js` 与各个 SGF 一致。

The script reuses the logic of `tools/make_site.py --strip-commentary`: the header and the time link of a teacher section stay, the body is replaced by a short note, so the viewer still shows the teacher card and can jump to that moment in the video. `--check` re-reads the output and confirms that no commentary text is left and that `library.js` matches the SGF files.

## 待你决定的事项 / Decisions that are yours

1. 是否清理公开历史。清理需要改写 `main` 和 `develop` 的历史并强制推送,所有克隆和已有的 PR 都会受影响,所以这里只列出选项:不清理(历史里留着讲解文字,风险由你承担),或者清理(用 `git filter-repo` 之类的工具重写,之后所有人重新克隆)。在你决定之前,没有任何历史被改动。

   Whether to clean the public history. Cleaning means rewriting the history of `main` and `develop` and force pushing, which affects every clone and open PR, so only the options are listed here: do not clean (the commentary stays in the history and the risk is yours), or clean (rewrite with a tool such as `git filter-repo`, after which everybody clones again). No history has been changed until you decide.

2. 切换后流水线把输出写在哪里。建议直接写进私有克隆(见下面的切换说明),这样完整数据从产生起就不进入公开工作区。代价是查看器和 `serve.py` 默认读的是公开克隆的 `data/`。

   Where the pipeline writes its output after the cutover. The suggestion is to write straight into the private clone (see the cutover notes below), so the full data never enters the public working folder. The cost is that the viewer and `serve.py` read `data/` of the public clone by default.

3. 本地查看器怎样找到私有数据。选项有:把公开克隆的 `data` 做成指向私有克隆 `data` 的目录联接(`mklink /J`,同时要在 `.git/info/exclude` 里排除,避免被当成改动);或者在私有克隆旁边另放一份查看器文件,让 `WEIQI_PROJ` 指向它;或者只在需要时跑 `strip_commentary.py` 生成公开副本再查看。第一种最省事,但要小心不要把联接后的 `data/` 提交进公开仓库。

   How the local viewer finds the private data. Options: make `data` of the public clone a directory junction to `data` of the private clone (`mklink /J`, and exclude it in `.git/info/exclude` so it does not show as a change); or keep a copy of the viewer files next to the private clone and point `WEIQI_PROJ` at it; or run `strip_commentary.py` when needed and view the public copy. The first is the least work, but take care never to commit the junctioned `data/` into the public repository.

## 流水线切换说明(只准备,没有执行) / Pipeline cutover notes (prepared, not performed)

加固后的 `pipeline/orch2.py` 用环境变量 `WEIQI_PROJ` 决定项目根目录,默认是 `D:\workspace\fun\Weiqi\Weiqi_AI\josekiapp`。它从 `WEIQI_PROJ\data\sources\<来源>` 读取 `plan.json` 和 `index.json`,把 SGF 写到 `WEIQI_PROJ\data\sgf\<来源>\<系列>\<组名>.sgf`,并读取 `WEIQI_PROJ\VERSION` 写进 SGF 的 AP 属性(读不到就用 `unknown`)。缓存、分析结果和 `kp_*.json` 在 `WEIQI_WORK`(默认 `D:\tmp\work`),不受 `WEIQI_PROJ` 影响。`D:\tmp\work\serve.py` 同样用 `WEIQI_PROJ` 决定提供哪个文件夹。

The hardened `pipeline/orch2.py` takes its project root from the environment variable `WEIQI_PROJ`, default `D:\workspace\fun\Weiqi\Weiqi_AI\josekiapp`. It reads `plan.json` and `index.json` from `WEIQI_PROJ\data\sources\<source>`, writes the SGF files to `WEIQI_PROJ\data\sgf\<source>\<series>\<group>.sgf` and reads `WEIQI_PROJ\VERSION` for the AP property of the SGF (it uses `unknown` when it cannot read it). The caches, the analysis results and `kp_*.json` live in `WEIQI_WORK` (default `D:\tmp\work`) and do not depend on `WEIQI_PROJ`. `D:\tmp\work\serve.py` also uses `WEIQI_PROJ` to decide which folder it serves.

要让流水线写进私有克隆,只需要在启动 `orch2.py` 的那个 shell 里设置 `WEIQI_PROJ=D:\workspace\fun\Weiqi\ai-weiqi-new-mind-data`,其余设置不变。切换步骤如下,每一步都要先做完再做下一步:

To make the pipeline write into the private clone, set `WEIQI_PROJ=D:\workspace\fun\Weiqi\ai-weiqi-new-mind-data` in the shell that starts `orch2.py`; nothing else changes. The steps, each done before the next:

1. 在 `D:\tmp\work\orch3.log` 里等到一行 `B done ...`(刚写完一组),这时没有写入即将发生。用 `python D:\tmp\work\wq.py status` 确认。

   Wait in `D:\tmp\work\orch3.log` for a `B done ...` line (a group has just been written), so no write is about to happen. Confirm with `python D:\tmp\work\wq.py status`.

2. 先做最后一次同步:`sync_private_data.ps1 -DryRun` 应该显示没有要复制的文件(`would copy 0`),然后正式同步并检查私有克隆的提交。

   Do a last sync: `sync_private_data.ps1 -DryRun` should say `would copy 0`, then sync for real and check the commit in the private clone.

3. 停掉正在运行的 `orch2.py`(它持有 `D:\tmp\work\orch2.lock`,同一时间只能有一个),不要在写文件的一刻停。如果有分析子进程(`analyze2.py`、KataGo)正在跑,先让它结束;缓存都在 `WEIQI_WORK` 里,不会因为切换而丢失(续跑行为按设计应当如此,但没有实际验证)。

   Stop the running `orch2.py` (it holds `D:\tmp\work\orch2.lock`, only one may run), and not in the middle of a write. If an analysis child (`analyze2.py`, KataGo) is running, let it finish first; the caches are all in `WEIQI_WORK` and are not lost by the cutover (resuming is meant to work that way by design but was not verified).

4. 在同一个 shell 里设置 `WEIQI_PROJ`,再用和原来相同的命令启动(参考 `D:\tmp\work\launch_orch.sh`,命令是 `python -u orch2.py`,日志追加到 `orch3.log`)。同时重启 `serve.py`,让它也用同一个 `WEIQI_PROJ`,否则查看器还在读旧位置。

   In the same shell set `WEIQI_PROJ`, then start with the same command as before (see `D:\tmp\work\launch_orch.sh`; the command is `python -u orch2.py`, with the log appended to `orch3.log`). Restart `serve.py` as well with the same `WEIQI_PROJ`, otherwise the viewer keeps reading the old place.

5. 观察 `orch3.log`,确认没有错误,下一组写出的 SGF 出现在私有克隆里,并且文件头的 `AP`、`CP`、`SO` 署名属性都在。

   Watch `orch3.log`, confirm there is no error, that the next group's SGF shows up in the private clone, and that the `AP`, `CP` and `SO` credit properties are in the file header.

切换前要核对的事项:

What to check before the cutover:

- 私有克隆里有 `data/sources/<来源>/plan.json` 和 `index.json`(已有),并且在私有克隆根目录放一个 `VERSION` 文件(现在没有,否则 AP 属性会写成 `unknown`)。

  The private clone has `data/sources/<source>/plan.json` and `index.json` (it does), and a `VERSION` file in its root (it has none today, so the AP property would say `unknown`).

- `sync_private_data.ps1 -DryRun` 显示 `would copy 0`,私有克隆里 `git status` 是干净的,最新提交已经推送。

  `sync_private_data.ps1 -DryRun` says `would copy 0`, `git status` is clean in the private clone and the latest commit is pushed.

- 私有仓库仍然是私有的:`gh repo view Xtraordinaire9911/ai-weiqi-new-mind-data --json visibility` 显示 `PRIVATE`。

  The repository is still private: `gh repo view Xtraordinaire9911/ai-weiqi-new-mind-data --json visibility` says `PRIVATE`.

- 谁在重建 `data/library.js` 还没有查清:`orch2.py` 里没有调用,而 `tools/build.ps1` 以脚本所在仓库为根目录。切换后要确认 `library.js` 也在私有克隆里被重建(例如把 `build.ps1` 放进私有克隆运行),否则查看器会读到过期的库。这一点没有核实。

  Who rebuilds `data/library.js` has not been established: `orch2.py` does not call it, and `tools/build.ps1` uses the repository that holds the script as its root. After the cutover, check that `library.js` is rebuilt inside the private clone as well (for example by running `build.ps1` from a copy placed in the private clone), otherwise the viewer reads a stale library. This is not verified.

- 工作目录里的 `kp_*.json` 和 `fixdict.json` 已经同步到私有克隆的 `pipeline/`;切换后它们仍由工作目录产生,继续用同步脚本复制。

  `kp_*.json` and `fixdict.json` of the work folder are in `pipeline/` of the private clone; after the cutover they are still produced in the work folder, so keep copying them with the sync script.

- 公开克隆的未提交改动(生成的 SGF 和 `library.js`)已经备份,并且切换后不要再被当作公开数据提交,直到决定好第 1 条和第 2 条。

  The uncommitted changes in the public clone (generated SGF files and `library.js`) are backed up, and must not be committed as public data after the cutover until decisions 1 and 2 are made.

- 公开发布前,对要发布的副本运行 `strip_commentary.py --check`,并确认副本里搜不到 `【老师讲解` 后面跟着正文的行。

  Before any public release, run `strip_commentary.py --check` on the copy that will be published and confirm no line has text after a `【老师讲解` header.

- 备份:切换前再备份一次工作克隆的 `data/` 和私有克隆,并比较文件数和 SHA-256。

  Back up: before the cutover make one more copy of `data/` of the working clone and of the private clone, and compare the file counts and the SHA-256 of every file.
