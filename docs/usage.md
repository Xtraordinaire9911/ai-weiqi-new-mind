# 定式库 (josekiapp)
双击 `index.html` 即可离线使用(无需服务器/Node/Python)。方向键: ←→ 步进, ↑↓ 选变化, Home/End。评论里的 `@mm:ss` 点击跳到视频对应时间。

## 命名规则 (SGF)
`<角>-<挂法/手法>-<夹击或应对>.sgf`，如 `星位-小飞挂-一间低夹`、`小目-小飞挂-二间高夹`。
同一"开局+夹法"的所有细分分支放同一个 SGF(用变化树), 夹法不同则分文件。
目录: `data/sgf/<来源>/<系列>/`。避雷/套路系列暂按单视频一个文件(`避雷-NN-标题`), 内容填充后可按上面规则合并改名(改 plan.json)。

## 数据格式
纯 SGF(FF4, UTF-8), 口述解析写在节点 `C[]`, 标记用标准 TR/SQ/CR/LB, 与 Lizzie/KataGo GUI/Sabaki 互通。

## 新增 UP 主 / 系列 (无需改代码)
1. `data/sources/<id>/index.json`: 视频列表 `{season,seasonName,idx,bvid,title}`(陈林涛的由 `tools/fetch_playlists.ps1` 生成)。
2. `data/sources/<id>/plan.json`: 参照 chenlintao 的 `series`(系列名) 与 `merge`(哪些视频合并为一个 SGF)。
3. `powershell -ExecutionPolicy Bypass -File tools/build.ps1`: 生成缺失的 SGF 骨架(不覆盖已填内容)并打包 `data/library.js`。
4. 用 Lizzie/KataGo GUI 打开 SGF 摆变化+写解析, 保存后重跑 build。
