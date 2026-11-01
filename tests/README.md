# 测试 / Tests

训练模块的纯逻辑（出题、答案集合、棋盘对称、记忆曲线、每日题单、进度导入导出）放在 `quiz_core.js`，不依赖浏览器，可以在 Node 里直接测。测试用 Node 自带的 `node:test`，不装任何依赖。

The pure logic of the training mode (question extraction, accepted answers, board symmetries, the memory curve, the daily session, progress export and import) lives in `quiz_core.js`. It does not touch the browser, so it can be tested in plain Node. The tests use the built in `node:test` runner and need no dependencies.

## 运行 / Running

测试在 Docker 里跑，主机上不需要安装 Node，也不要建 venv。在仓库根目录执行：

The tests run in Docker, so nothing has to be installed on the host and no venv is used. From the repository root:

```
docker run --rm -v "$PWD:/app:ro" -w /app node:20-alpine node --test tests/quiz_core.test.js
```

PowerShell 里把 `$PWD` 写成 `${PWD}`；Git Bash 里先设 `MSYS_NO_PATHCONV=1`，并把挂载路径写成 Windows 路径，例如 `-v 'D:\path\to\repo:/app:ro'`。

In PowerShell write `${PWD}` instead of `$PWD`. In Git Bash set `MSYS_NO_PATHCONV=1` first and give the mount as a Windows path, for example `-v 'D:\path\to\repo:/app:ro'`.

仓库以只读方式挂载，测试不会改动任何文件。

The repository is mounted read only, so the tests cannot change any file.

## 覆盖范围 / What is covered

测试覆盖：小棋谱上的出题规则（分叉点、AN 节点、没有讲解就跳过、少于两个合理着法就跳过）、答案集合（前 N 名、老师着法、-3 目和 -1 目两个阈值、并列）、题目编号的稳定性、八种棋盘对称（恒等、逆变换往返、群的封闭性、角点映射、变换后坐标标签、提子后局面一致）、七档记忆曲线（间隔 0、1、2、4、7、15、30 天）和掌握规则、每日题单（先复习后新题、每日上限、十分钟内不重复、混合模式交错）、进度的导出导入往返。最后一个测试会读取 `data/library.js`（存在时），检查真实数据里每道题的不变量。

The tests cover: the extraction rules on toy trees (branch points, AN nodes, skipping nodes without commentary, skipping questions with fewer than two sensible moves), the accepted set (top N, teacher moves, the -3 and -1 point thresholds, ties), id stability, the eight board symmetries (identity, inverse round trip, group closure, corner mapping, labels after the transformation, same position after captures), the Leitner boxes and the mastery rule, the daily session (reviews first, then new questions, daily limit, no repeat within ten minutes, interleaving in mixed mode) and the export and import round trip. The last test reads `data/library.js` when it exists and checks the invariants of every real question.

## 数据扫描 / Data scan

`scan_library.js` 对真实的 `data/library.js` 跑一遍出题，按定式分别列出题数、没有可接受着法或只有一个可接受着法的题数、带 AI 数据的题数和深度分布，用来检查阈值是否合理。它只读文件。

`scan_library.js` runs the extraction over a real `data/library.js` and prints, per collection, the number of questions, how many have no or a single accepted move, how many carry AI data and the depth distribution. It is meant for checking whether the thresholds are sensible. It only reads the file.

```
docker run --rm -v "$PWD:/app:ro" -v "$PWD/data/library.js:/data/library.js:ro" -w /app node:20-alpine node tests/scan_library.js /data/library.js
```
