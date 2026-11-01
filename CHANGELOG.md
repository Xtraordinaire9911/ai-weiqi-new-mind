# Changelog

All notable changes to this project are recorded here. The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the version numbers follow [Semantic Versioning 2.0.0](https://semver.org/). When to bump the version during the 0.x phase is described in section 7 of [docs/WORKFLOW.md](docs/WORKFLOW.md).

## [Unreleased]

### Added
- Branching model: `main` for released versions, `develop` for integration, `feature/<topic>`, `fix/<topic>`, `data/<batch>`, `release/<version>` and `hotfix/<topic>`. Steps and commands are in `docs/WORKFLOW.md`.
- `CONTRIBUTING.md` with the commit message style (Conventional Commits, kept short and human), the contribution terms draft, and a `.gitmessage` template.
- A short pull request template and three issue forms (bug report, content issue, video suggestion).
- `tools/check_repo.py`, a local check that needs only Python 3: references in `index.html`, JSON files, `data/library.js` against the SGF files, SGF syntax, Python syntax, files that should not be committed, and a rough token scan.
- `docs/LICENSE-ADVICE.md`, license advice that is not in effect (the repository still has no LICENSE file), and `docs/COMPUTE-PLATFORMS.md`, a list of cloud GPU options with notes on LRZ.

### Changed
- `.gitignore` now also covers video, audio, network weights and credential files. New `.gitattributes` keeps SGF files and `data/library.js` on LF line endings.

### Fixed
- The placeholder SGF files written by `tools/build.ps1` contained an unescaped `]` in their text (the words "C[]"), so they were not valid SGF. The text is changed and group names, source names and video titles are now escaped. The 90 placeholders already in the repo are untouched, they get replaced when a group is filled in, and `tools/check_repo.py` reports them as one warning.

## [0.1] - 2026-11-01

First snapshot. Earlier changes were not versioned and cannot be rebuilt, so the state at this point is called v0.1 (read as 0.1.0 under SemVer; the existing tag `v0.1` stays as it is and later versions use three numbers, such as `v0.2.0`).

### Added
- Viewer `index.html`: browse the SGF variation tree; cards for the teacher's commentary, key points, engine evaluation and nearby stones; hover preview and click to pin for candidate moves; the teacher's moves as dashed blue circles with sequence numbers; links to video time stamps; focused and whole board views with a ladder demo; version and data time stamps.
- Data: four groups of Chen Lintao's "Joseki Encyclopedia" as SGF (one of them with the new engine evaluation); the video list and merge plan; a typo dictionary of about 300 entries.
- Pipeline: download, Whisper transcription, OpenCV board recognition, variation tree, KataGo local analysis (branch points only, the teacher's moves always evaluated), SGF output.

### Fixed
- Serious mistakes found along the way: (1) KataGo scores are from Black's point of view and were not converted, so the "best" move was wrong; (2) stone colors in variation previews were swapped; (3) the teacher's moves were not shown; (4) caching served an old page; (5) the whole board winrate is meaningless under a local search and was removed.

[Unreleased]: https://github.com/Xtraordinaire9911/ai-weiqi-new-mind/compare/v0.1...develop
[0.1]: https://github.com/Xtraordinaire9911/ai-weiqi-new-mind/releases/tag/v0.1
