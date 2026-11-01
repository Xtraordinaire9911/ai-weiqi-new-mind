<!--
Title: type(scope): short imperative subject, for example  feat(data): add star point 3-3 group
标题:type(scope): 简短的祈使句主题,例如 feat(data): add star point 3-3 group

Branches: feature/<topic>, fix/<topic>, data/<batch> go to develop. Only promote develop to main when a stage is stable.
分支:feature/<topic>、fix/<topic>、data/<batch> 合并到 develop;只有阶段稳定时才把 develop 合并到 main。
Details / 详情: CONTRIBUTING.md, docs/WORKFLOW.md
-->

## What changed and why / 改了什么,为什么改

## How to check it / 怎么检查
<!-- Which page or file to open and what you should see. For data batches also list the groups, video ids and KataGo settings. -->
<!-- 打开哪个页面或文件,应该看到什么。数据批次还要列出分组、视频 BV 号和 KataGo 设置。 -->

## Before merging / 合并之前
- [ ] The base branch is `develop` (or `main` for a release or hotfix) / 目标分支是 `develop`(发布或紧急修复才用 `main`)
- [ ] `python tools/check_repo.py` shows no errors / `python tools/check_repo.py` 没有报错
- [ ] No videos, audio, network weights, KataGo binaries, tokens or keys are included / 没有包含视频、音频、网络权重、KataGo 可执行文件、令牌或密钥
- [ ] Data batch only: `tools/build.ps1` was rerun, scores are from the side to move, the teacher's moves are marked / 仅数据批次:已重新运行 `tools/build.ps1`,目差是行棋方视角,老师的着法已标出
