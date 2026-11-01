# Contributing / 贡献指南

This is mostly a one person project, but small fixes from others are welcome: typos in the commentary, wrong variations, viewer bugs, docs. If you plan something bigger, open an issue first so we do not duplicate work. How branches and releases work is described in [docs/WORKFLOW.md](docs/WORKFLOW.md). This page only lists what you need to know when you send a change.

这个项目主要由一个人维护,但欢迎别人提交小的修正:讲解里的错别字、不对的变化图、查看器的 bug、文档。想做大一点的改动,请先开一个 issue 说明,免得重复劳动。分支和发布怎么走,见 [docs/WORKFLOW.md](docs/WORKFLOW.md)。本页只写你提交改动时需要知道的规则。

## The short version / 简要说明

1. Branch off `develop`. Name the branch `feature/<topic>`, `fix/<topic>` or `data/<batch>`.

   从 `develop` 切出分支,分支名用 `feature/<topic>`、`fix/<topic>` 或 `data/<batch>`。

2. Write commit messages as `type(scope): subject` (see below).

   提交信息写成 `type(scope): subject` 的形式(见下文)。

3. Run `python tools/check_repo.py` before you open the pull request. It only needs Python 3 and takes a few seconds.

   开 PR 之前先运行 `python tools/check_repo.py`。它只需要 Python 3,几秒钟就跑完。

4. Open the pull request against `develop`. Use the same `type(scope): subject` style for the title.

   PR 的目标分支选 `develop`,标题同样用 `type(scope): subject` 的写法。

5. Do not commit videos, audio, network weights, KataGo binaries, tokens or keys.

   不要提交视频、音频、网络权重、KataGo 可执行文件、令牌或密钥。

6. If you are not the maintainer, sign off every commit with `git commit -s` (see the contribution terms below).

   如果你不是维护者,每个提交都用 `git commit -s` 签署(见下面的贡献条款)。

## Branch names / 分支命名

| Branch / 分支 | Use it for / 用途 |
|---|---|
| `feature/<topic>` | New features and improvements, for example `feature/viewer-dark-mode` / 新功能和改进,例如 `feature/viewer-dark-mode` |
| `fix/<topic>` | Bug fixes, including data fixes such as transcription typos / 修 bug,也包括语音转写错字这类数据修正 |
| `data/<batch>` | One batch of new SGF files from the pipeline, for example `data/2026-12-joseki-batch-2` / 流水线产出的一批新 SGF,例如 `data/2026-12-joseki-batch-2` |
| `release/<version>` | Preparing a release, for example `release/v0.2.0` / 准备发布,例如 `release/v0.2.0` |
| `hotfix/<topic>` | An urgent fix on top of `main`, for example `hotfix/viewer-crash` / 在 `main` 上做的紧急修复,例如 `hotfix/viewer-crash` |

Feature, fix and data branches go to `develop`. `develop` is promoted to `main` only when a stage is stable. Release and hotfix branches are described in the workflow doc.

feature、fix 和 data 分支都合并到 `develop`。只有当某个阶段稳定了,才把 `develop` 合并到 `main`。release 和 hotfix 分支的用法见工作流文档。

## Commit messages / 提交信息

The style follows Conventional Commits 1.0.0, but keep it human. A short subject in the imperative mood, and if the change needs explaining, a short paragraph in plain words about why you did it and what a reviewer should look at. No bullet lists, no headings, no emoji. Commit messages, code comments and branch names are written in English.

格式遵循 Conventional Commits 1.0.0,但要像人写的:主题用简短的祈使句;如果改动需要解释,再用一小段平实的话说明为什么这样改、评审时该看哪里。不要列表,不要标题,不要 emoji。提交信息、代码注释和分支名一律用英文写。

```
type(scope): short imperative subject

Optional paragraph that explains the reason for the change in a few
plain sentences.
```

The subject should stay under about 72 characters and has no final period. Mark a breaking change with a `!` after the scope, or with a `BREAKING CHANGE:` line at the end. One commit should do one thing, and a data change should travel together with the rebuilt `data/library.js`.

主题尽量不超过 72 个字符,结尾不加句号。破坏性改动在 scope 后面加 `!`,或者在末尾写一行 `BREAKING CHANGE:`。一个提交只做一件事;数据改动要和重新打包出来的 `data/library.js` 放在同一个提交里。

Types: `feat` for new features or new content, `fix` for bugs and wrong data, `docs`, `style`, `refactor`, `perf`, `test`, `build` for packaging such as rebuilding `data/library.js`, `chore` for housekeeping such as version bumps, and `revert`.

类型:`feat` 用于新功能或新内容,`fix` 用于 bug 和错误的数据,另外有 `docs`、`style`、`refactor`、`perf`、`test`,`build` 用于打包类改动(例如重新打包 `data/library.js`),`chore` 用于版本号之类的杂务,以及 `revert`。

Scopes (optional, lower case): `viewer` for index.html, `pipeline`, `data` for SGF files, sources and the packed library, `remote`, `tools`, `engine`, `docs`, `repo`, `release`.

scope(可选,小写):`viewer` 指 index.html,还有 `pipeline`、`data`(SGF 文件、来源清单和打包出的库)、`remote`、`tools`、`engine`、`docs`、`repo`、`release`。

Examples of subjects that read well:

读起来顺的主题,例如:

```
feat(data): add star point small knight group
fix(viewer): use the right color in variation previews
fix(data): correct twelve transcription typos in the 3-3 group
docs(remote): explain how to enable GPU on Kaggle
refactor(pipeline): split out the SGF writer
chore(release): bump version to 0.2.0
```

Subjects like `update`, `fix bug`, `wip` or `Merge branch 'develop'` do not tell the reader anything.

像 `update`、`fix bug`、`wip` 或 `Merge branch 'develop'` 这样的主题,读的人什么也看不出来。

If you want your editor to show this reminder, run `git config commit.template .gitmessage`.

想在写提交信息时看到这份提示,运行 `git config commit.template .gitmessage` 即可。

## Pull requests / PR

Keep them small and focused. Viewer changes, pipeline changes and data batches should be separate pull requests so they are easy to review and to revert. The pull request template has a short checklist. For a data batch, say which videos and groups it covers, which KataGo version, network and number of visits were used, and whether the scores were converted to the point of view of the side to move.

PR 要小而专注。查看器、流水线和数据批次分开提,这样好评审也好回退。PR 模板里有一份简短的检查清单。数据批次要写清楚覆盖了哪些视频和分组、用的 KataGo 版本、网络和搜索次数,以及目差是否已经换算成行棋方的视角。

## Data and copyright / 数据与版权

The commentary in the SGF files comes from the spoken explanations in videos by the Bilibili uploader Chen Lintao (陈林涛). The copyright belongs to him and not to this project, and no license of this project covers that text. It is being moved to a private repository. Please do not commit video files, full subtitles, or other people's copyrighted text and images. When you report a content problem, describe where it is and what is wrong. There is no need to paste long passages. The license decision and its background are in [docs/LICENSE-ADVICE.md](docs/LICENSE-ADVICE.md).

SGF 里的讲解来自 B 站 UP 主陈林涛视频里的口述。版权属于他本人,不属于本项目,本项目的任何许可证也不覆盖这些文字。这部分文字正在迁移到私有仓库。请不要提交视频文件、完整字幕,或者别人享有版权的文字和图片。报告内容问题时,写清楚在哪里、哪里不对就行,不用贴大段原文。许可证的决定及其背景见 [docs/LICENSE-ADVICE.md](docs/LICENSE-ADVICE.md)。

## Local checks / 本地检查

```
python tools/check_repo.py              # everything
python tools/check_repo.py --only sgf   # only the SGF files
```

It checks that the files referenced by `index.html` exist, that JSON files parse, that `data/library.js` still matches the SGF files (rerun `tools/build.ps1` after editing an SGF), that SGF brackets and coordinates are valid, that Python files compile, and that no weights, videos or key files slipped in.

脚本会检查:`index.html` 引用的文件是否存在,JSON 能否解析,`data/library.js` 是否仍与 SGF 一致(改过 SGF 之后要重新运行 `tools/build.ps1`),SGF 的括号和坐标是否合法,Python 文件能否编译,以及有没有误提交权重、视频或密钥文件。

## Contribution terms / 贡献条款

The code is under the PolyForm Strict License 1.0.0 and our own data and docs are under CC BY-NC-ND 4.0, with the teacher's commentary excluded (the decision and the reasons are in [docs/LICENSE-ADVICE.md](docs/LICENSE-ADVICE.md), and the license files come in their own pull request). Sending a pull request means you agree to the following.

代码采用 PolyForm Strict License 1.0.0,我们自己的数据和文档采用 CC BY-NC-ND 4.0,老师的讲解文字不在其中(决定和理由见 [docs/LICENSE-ADVICE.md](docs/LICENSE-ADVICE.md),许可证文件放在单独的 PR 里)。提交 PR 即表示你同意以下几点。

1. Sign off every commit with `git commit -s`, which adds a `Signed-off-by` line. That line certifies the Developer Certificate of Origin 1.1 (https://developercertificate.org/) for your change: you wrote it, or you have the right to submit it under these terms.

   每个提交都用 `git commit -s` 签署,它会加上一行 `Signed-off-by`。这一行表示你对自己的改动确认了开发者原产地证书(DCO)1.1(https://developercertificate.org/):改动是你自己写的,或者你有权按这些条款提交。

2. You keep the copyright on your contribution. The maintainer may relicense your contribution together with the project, under whatever license the project uses now or later, commercial licenses included.

   你保留自己所贡献内容的版权。维护者可以把你的贡献连同项目一起重新授权,不论项目现在或将来使用哪种许可证,包括商业许可。

3. Your contribution does not contain anything you have no right to license, in particular transcripts of the teacher's videos or third party material.

   你的贡献里不含你无权授权的内容,尤其是老师视频的转写原文和第三方素材。

4. Because the code license does not allow changes by itself, the maintainer permits you to modify the code and data locally for the purpose of preparing and sending a contribution.

   因为代码许可证本身不允许修改,所以维护者允许你为了准备和提交贡献,在本地修改代码和数据。

This text is not legal advice. If you do not agree, please do not send a pull request, and open an issue to talk about it first. The maintainer does not need to sign off their own commits.

这段文字不是法律意见。如果你不同意,请先不要发 PR,开一个 issue 讨论。维护者自己的提交不需要签署。

## Leaked credentials / 凭据泄露

If you find a token or key in the repository, revoke it with the provider first, then open an issue that names the file. Do not paste the secret itself.

如果你在仓库里发现了令牌或密钥,先到对应的平台把它吊销,再开一个 issue 说明是哪个文件,不要把密钥本身贴出来。
