<!--
Title: type(scope): short imperative subject, for example  feat(data): add star point 3-3 group
Branches: feature/<topic>, fix/<topic>, data/<batch> go to develop. Only promote develop to main when a stage is stable.
Details are in CONTRIBUTING.md and docs/WORKFLOW.md.
-->

## What changed and why

## How to check it
<!-- Which page or file to open and what you should see. For data batches also list the groups, video ids and KataGo settings. -->

## Before merging
- [ ] The base branch is `develop` (or `main` for a release or hotfix)
- [ ] `python tools/check_repo.py` shows no errors
- [ ] No videos, audio, network weights, KataGo binaries, tokens or keys are included
- [ ] Data batch only: `tools/build.ps1` was rerun, scores are from the side to move, the teacher's moves are marked
