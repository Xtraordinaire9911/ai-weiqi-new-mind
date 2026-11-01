# Contributing

This is mostly a one person project, but small fixes from others are welcome: typos in the commentary, wrong variations, viewer bugs, docs. If you plan something bigger, open an issue first so we do not duplicate work. How branches and releases work is described in [docs/WORKFLOW.md](docs/WORKFLOW.md). This page only lists what you need to know when you send a change.

## The short version

1. Branch off `develop`. Name the branch `feature/<topic>`, `fix/<topic>` or `data/<batch>`.
2. Write commit messages as `type(scope): subject` (see below).
3. Run `python tools/check_repo.py` before you open the pull request. It only needs Python 3 and takes a few seconds.
4. Open the pull request against `develop`. Use the same `type(scope): subject` style for the title.
5. Do not commit videos, audio, network weights, KataGo binaries, tokens or keys.

## Branch names

| Branch | Use it for |
|---|---|
| `feature/<topic>` | new features and improvements, for example `feature/viewer-dark-mode` |
| `fix/<topic>` | bug fixes, including fixes to data such as transcription typos |
| `data/<batch>` | one batch of new SGF files from the pipeline, for example `data/2026-12-joseki-batch-2` |
| `release/<version>` | preparing a release, for example `release/v0.2.0` |
| `hotfix/<topic>` | an urgent fix on top of `main`, for example `hotfix/viewer-crash` |

Feature, fix and data branches go to `develop`. `develop` is promoted to `main` only when a stage is stable. Release and hotfix branches are described in the workflow doc.

## Commit messages

The style follows Conventional Commits 1.0.0, but keep it human. A short subject in the imperative mood, and if the change needs explaining, a short paragraph in plain words about why you did it and what a reviewer should look at. No bullet lists, no headings, no emoji.

```
type(scope): short imperative subject

Optional paragraph that explains the reason for the change in a few
plain sentences.
```

The subject should stay under about 72 characters and has no final period. Mark a breaking change with a `!` after the scope, or with a `BREAKING CHANGE:` line at the end. One commit should do one thing, and a data change should travel together with the rebuilt `data/library.js`.

Types: `feat` for new features or new content, `fix` for bugs and wrong data, `docs`, `style`, `refactor`, `perf`, `test`, `build` for packaging such as rebuilding `data/library.js`, `chore` for housekeeping such as version bumps, and `revert`.

Scopes (optional, lower case): `viewer` for index.html, `pipeline`, `data` for SGF files, sources and the packed library, `remote`, `tools`, `engine`, `docs`, `repo`, `release`.

Examples of subjects that read well:

```
feat(data): add star point small knight group
fix(viewer): use the right color in variation previews
fix(data): correct twelve transcription typos in the 3-3 group
docs(remote): explain how to enable GPU on Kaggle
refactor(pipeline): split out the SGF writer
chore(release): bump version to 0.2.0
```

Subjects like `update`, `fix bug`, `wip` or `Merge branch 'develop'` do not tell the reader anything.

If you want your editor to show this reminder, run `git config commit.template .gitmessage`.

## Pull requests

Keep them small and focused. Viewer changes, pipeline changes and data batches should be separate pull requests so they are easy to review and to revert. The pull request template has a short checklist. For a data batch, say which videos and groups it covers, which KataGo version, network and number of visits were used, and whether the scores were converted to the point of view of the side to move.

## Data and copyright

The commentary in the SGF files comes from the spoken explanations in videos by the Bilibili uploader Chen Lintao. The copyright belongs to him and not to this project, and no license of this project covers that text. Please do not commit video files, full subtitles, or other people's copyrighted text and images. When you report a content problem, describe where it is and what is wrong. There is no need to paste long passages. Background and options are in [docs/LICENSE-ADVICE.md](docs/LICENSE-ADVICE.md), which is advice only and not a license.

## Local checks

```
python tools/check_repo.py              # everything
python tools/check_repo.py --only sgf   # only the SGF files
```

It checks that the files referenced by `index.html` exist, that JSON files parse, that `data/library.js` still matches the SGF files (rerun `tools/build.ps1` after editing an SGF), that SGF brackets and coordinates are valid, that Python files compile, and that no weights, videos or key files slipped in.

## Contribution terms (draft)

The project has no license yet, so by default all rights are reserved, and the maintainer is still deciding (see `docs/LICENSE-ADVICE.md`). So that the project can later be put under a clear license, including a separate commercial one, sending a pull request means you agree to this:

1. What the Developer Certificate of Origin 1.1 (https://developercertificate.org/) says is true for your change. Adding a `Signed-off-by` line with `git commit -s` is a good habit.
2. You keep the copyright on your contribution and give the maintainer a perpetual, worldwide, royalty free and irrevocable non-exclusive license to use, modify and distribute it under the license the project has now or chooses later, commercial licenses included, and to sublicense it.
3. Your contribution does not contain anything you have no right to license, in particular transcripts of the teacher's videos or third party material.

This is a draft and not legal advice. Once a license is chosen the maintainer will replace it with final wording. If you do not agree, please do not send a pull request and open an issue to talk about it first.

## Leaked credentials

If you find a token or key in the repository, revoke it with the provider first, then open an issue that names the file. Do not paste the secret itself.
