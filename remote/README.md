# 远程 GPU 与算力切换（界面 v4） / Remote GPU / compute switch (UI v4)

> 调研日期：2026-11-01。数字以来源页面为准（来源列在文末）；“未验证”表示没有在真实硬件上跑过。查看器界面本身是中文的，英文段落里的界面文字是译名，中文段落直接使用界面原文。
>
> Researched on 2026-11-01. Numbers follow the source pages (sources at the end); "unverified" means it has not been run on real hardware. The viewer UI itself is in Chinese; UI labels are given here in English translation.

## 1. 结论 / Conclusions

- **瓶颈确实在显卡上，而且是最慢的那种组合**：本机用的是 OpenCL 后端，加上 Transformer 网络（b11c768）。KataGo v1.18.0 的发布说明写明，OpenCL 慢得多，对 Transformer 模型尤其如此；而 NVIDIA 的 CUDA 版本在 Transformer 上要快 1.2 到 2 倍，v1.18.2 又为 T4 / RTX 20 系列（Turing）加入了 tensor core 注意力计算。任何一块 NVIDIA 独立显卡都会带来明显差别。

  **The bottleneck really is the graphics card, and it is the slowest possible combination**: the local machine uses the OpenCL backend with a Transformer network (b11c768). The KataGo v1.18.0 release notes state that OpenCL is "much slower, particularly for transformer models", while the NVIDIA CUDA build is 1.2~2x faster on Transformers, and v1.18.2 adds tensor-core attention for T4 / RTX 20 series (Turing). Any NVIDIA discrete GPU will make a clear difference.

- **推荐离线批处理，而不是“网页实时连云端”。** 你要的是“给约 29 个分组一次性生成 AI 数据”，不是低延迟对弈。批处理任务只需要占用一台机器几个小时，产出 `g_<name>.a2.json`，网页完全不需要联网。这也是最合规的方案（见第 5 节），因为免费平台明确禁止“把 Colab/Kaggle 当服务器用”。

  **Recommended: offline batch, not "web page talking to the cloud in real time".** What you need is to "generate AI data once for ~29 groups", not low-latency play. A batch job needs one machine for a few hours and produces `g_<name>.a2.json`; the web page does not need the network at all. This is also the most compliant option (see section 5), because the free platforms specifically forbid "using Colab/Kaggle as a server".

- 实时分析作为**可选项**内置在页面里（默认关闭）：它只会连接你自己掌控的 KataGo（本机、LRZ，或你租用的机器）。连接失败时，页面会自动回退到已缓存的 AI 数据。

  Real-time analysis is built into the page as an **option** (off by default): it only connects to a KataGo that you control (this machine, or LRZ / a machine you rent). If the connection fails, it falls back to the cached AI data automatically.

| 方案 / Option | 速度（估算，未实测） / Speed (estimate, not measured) | 成本 / Cost | 主要风险 / Main risks | 是否合规？ / Compliant? |
|---|---|---|---|---|
| 现状：本机 780M 核显，OpenCL / Status quo: local 780M integrated GPU, OpenCL | 基准：220 visits（搜索次数）约 11 秒，每组 30 到 40 分钟，总计约 15 到 19 小时 / Baseline: 220 visits ≈ 11 s, 30~40 min per group, about 15~19 hours in total | 免费 / 0 | 占用本机，拖慢其他工作 / Ties up the local machine and slows other work | 是 / Yes |
| **Colab 免费版，批处理**（`katago_batch.ipynb`） / **Colab free tier, batch** (`katago_batch.ipynb`) | T4 + CUDA：我估计快 5 到 15 倍，总计 2 到 4 小时 / T4 + CUDA: I estimate 5~15x, 2~4 hours in total | 免费 / 0 | 不保证分到 GPU；单次会话最长 12 小时；页面必须保持打开；配额未公布 / No GPU guaranteed; sessions last at most 12 hours; the page must stay open; quota is not published | **是**（只在笔记本内跑批处理，不开隧道） / **Yes** (batch jobs inside the notebook only, no tunnels) |
| **Kaggle Notebooks，批处理** / **Kaggle Notebooks, batch** | T4/P100（官方文档：每周约 30 小时 GPU）；可用 “Save & Run All” 在后台运行 / T4/P100 (official docs: about 30 GPU hours per week); can run in the background with "Save & Run All" | 免费 / 0 | 需要手机验证；必须开启联网；P100（没有 tensor core）上的速度未知 / Phone verification needed; Internet must be on; speed on P100 (no tensor cores) unknown | 是（批处理）；有报告称隧道式用法会被封 / Yes (batch); tunnel-style use has been reported to get banned |
| **LRZ AI Systems + Slurm，批处理** / **LRZ AI Systems + Slurm, batch** | V100/A100/H100：估计快 10 到 50 倍 / V100/A100/H100: estimate 10~50x | 文档没有提到费用 / Docs do not mention fees | 需要 LRZ 项目账号（学生账号不够）；计算节点通常不能联网 / Needs an LRZ project account (a student account is not enough); compute nodes often have no internet | 是（正是其预期用途） / Yes (intended use) |
| Lightning AI 免费 Studio / Lightning AI free Studio | 取决于 GPU；单个 Studio，每 4 小时需重启 / Depends on the GPU; one Studio, restart every 4 hours | 免费额度（各来源数额不一；价格似乎在 2026-09 调整过） / Free credits (amounts differ between sources; prices were apparently changed in 2026-09) | 额度规则一直在变；未验证能否开放端口 / The credit rules keep changing; not verified whether ports can be exposed | 未验证 / Not verified |
| Hugging Face Spaces | T4 small 官方价 0.40 美元/小时；ZeroGPU 只支持 Gradio，每天免费 5 分钟 / T4 small is officially 0.40 USD/hour; ZeroGPU supports Gradio only, 5 free minutes per day | 付费 / Paid | 不适合长时间的 KataGo 任务 / Not suited to long KataGo jobs | 是（付费） / Yes (paid) |
| 浏览器 WebGPU 版 KataGo（web-katrain / Kaya） / Browser WebGPU KataGo (web-katrain / Kaya) | 可能用到核显（经由 D3D12）；速度未实测 / May use the integrated GPU (via D3D12); speed not measured | 免费 / 0 | 上传的模型限 128MB，而我们的权重有 262MB；换网络 => 结果无法与现有数据比较 / Uploaded models are limited to 128MB and our weights are 262MB; a different network => results not comparable with the existing data | 是 / Yes |
| **Colab/Kaggle + ngrok/cloudflared 隧道，供网页实时使用** / **Colab/Kaggle + ngrok/cloudflared tunnel for real-time web page use** | - | - | 账号被封或运行时被终止 / Account ban / runtime termination | **违反条款；本目录不提供** / **Violates the terms; not provided in this directory** |

速度一栏是我根据“本机约 20 visits/秒”和社区数据估出来的（有一篇旧帖给出 T4 上每秒约 390 次网络评估，但那是小网络、旧版本）。**第一组跑完后，请用 `meta.json` 里的 `seconds` 字段校准。**

The speed column is my estimate from "20 visits/s locally" and community data (one old post gives about 390 network evaluations per second on a T4, but that was a small network and an old version). **After the first group finishes, calibrate with the `seconds` field in `meta.json`.**

## 2. 为什么这样设计 / Why it is designed this way

1. **批处理优先**：一次运行就产出整组的 `a2.json`，格式与现有流水线相同，可以审计，也可以重跑（已完成的分组会自动跳过）。

   **Batch first**: one run produces a whole group's `a2.json`, in the same format as the existing pipeline, auditable and re-runnable (finished groups are skipped automatically).

2. **移植逻辑，不要重写**：`analyze_remote.py` 是 `analyze2.py` 的逐行移植（定式区域、分叉点、对老师着手的强制评估、`reportAnalysisWinratesAs=BLACK` → 行棋方视角）。`selftest.py --ref analyze2.py` 会让两者在同一个模拟引擎上运行，输出**逐字节相同**。

   **Port the logic, do not rewrite it**: `analyze_remote.py` is a line-by-line port of `analyze2.py` (region, branch points, forced evaluation of the teacher's moves, `reportAnalysisWinratesAs=BLACK` → side-to-move perspective). `selftest.py --ref analyze2.py` runs both on the same fake engine and the outputs are **byte-for-byte identical**.

3. **视角错误不能再犯**：桥接服务强制使用 `reportAnalysisWinratesAs=BLACK`，并在每个响应里声明 `bridge.winratesAs`；页面只有看到 BLACK 才会换算成行棋方视角，否则拒绝使用该响应。页面展示的仍然只是“比局部最优差多少目”，绝不展示全盘胜率。

   **The perspective error must not happen again**: the bridge forces `reportAnalysisWinratesAs=BLACK` and declares `bridge.winratesAs` in every response; the page converts to the side-to-move perspective only when it sees BLACK, and refuses to use the response otherwise. The page still only shows "how many points worse than the local best", never the whole-board winrate.

4. **默认不改变现有行为**：算力控件默认是“缓存”，完全不发网络请求；只有切到本机或远程之后才会建立连接；连接失败、断开或视角不一致时，页面继续显示缓存数据。

   **No change to existing behaviour by default**: the compute control defaults to "cache" and sends no network request at all; connections are made only after switching to local/remote; on failure / disconnect / perspective mismatch the page keeps showing the cached data.

5. **让桥接服务保持精简**：它只转发字段在白名单内的分析查询，带令牌校验和 CORS 白名单，并限制 visits、着手数和并发数，默认只监听 127.0.0.1。

   **Keep the bridge small**: it only forwards analysis queries with allowlisted fields, has a token, a CORS allowlist, and limits on visits / number of moves / concurrency, and listens on 127.0.0.1 only by default.

## 3. 用法 A：离线批处理（推荐） / Usage A: offline batch (recommended)

**准备工作（本机，只读）**：把要分析的 `g_*.n.json` 打包（不会修改原文件；流水线还在运行时，也可以先把已完成的那部分打包）：

**Preparation (local machine, read-only)**: pack the `g_*.n.json` files to analyze (the originals are not modified; you can also pack the finished ones while the pipeline is still running):

```powershell
Compress-Archive -Path D:\tmp\work\g_*.n.json -DestinationPath $env:USERPROFILE\Desktop\n_json.zip
```

权重文件 `kata1-tf3-b11c768-s12752M-d6531M.bin.gz`（262MB）与本机使用的是同一个文件；只需上传一次到 Google Drive 或 Kaggle Dataset。**不要换网络**，否则新旧结果无法比较。

The weights `kata1-tf3-b11c768-s12752M-d6531M.bin.gz` (262MB) are the same file the local machine uses; upload it once to Google Drive / a Kaggle Dataset. **Do not switch networks**, otherwise old and new results are not comparable.

**Colab 免费版 / Colab free tier**

1. 打开 [colab.research.google.com](https://colab.research.google.com) 并上传 `remote/katago_batch.ipynb`；然后选 *Runtime → Change runtime type → T4 GPU*（即“运行时 → 更改运行时类型”）。

   Open [colab.research.google.com](https://colab.research.google.com) and upload `remote/katago_batch.ipynb`; *Runtime → Change runtime type → T4 GPU*.

2. 为了避免断线时丢失进度：在第 4 个代码单元格里设置 `USE_DRIVE = True` 并授权 Drive（由你自己确认授权）。

   To avoid losing progress on a disconnect: in the 4th code cell set `USE_DRIVE = True` and authorize Drive (you approve it yourself).

3. 从上到下依次运行；出现提示时上传输入 zip 和权重（也可以事先放在 `MyDrive/josekiapp/`）。先运行“3 个分叉点的试跑”来确认速度。

   Run from top to bottom; upload the input zip and the weights when prompted (or put them in `MyDrive/josekiapp/`). First run the "trial run on 3 branch points" to check the speed.

4. **保持页面打开，人也别走远。** 断线后重新连接并重新运行所有单元格；已完成的分组会自动跳过。

   **Keep the page open and stay nearby.** After a disconnect, reconnect and re-run all cells; finished groups are skipped automatically.

5. 最后一个单元格会下载 `a2_results.zip`。解压后把 `g_*.a2.json` 放回 `D:\tmp\work`，再按平时的流程继续（`regen.py` → `tools\build.ps1`）。我没有读过 `orch2.py`，所以请对照你现有的流程确认它的断点逻辑能否直接识别这些文件。

   The last cell downloads `a2_results.zip`. Unpack it, put the `g_*.a2.json` files back into `D:\tmp\work`, and continue with the usual flow (`regen.py` → `tools\build.ps1`). I did not read `orch2.py`, so please check against your existing flow whether its checkpoint logic picks the files up directly.

**Kaggle**：新建一个 Notebook，在右侧面板的 Accelerator 里选一块 GPU，并打开 Internet（需要手机验证）；把 n.json 文件和权重分别做成 Dataset 并添加进来；导入同一个 `.ipynb`；用 *Save & Run All* 可以在后台无人值守地运行，结果可从 Output 下载。

**Kaggle**: create a new Notebook, choose a GPU as Accelerator in the right-hand panel, and turn Internet on (phone verification required); make the n.json files and the weights into Datasets and add them; import the same `.ipynb`; *Save & Run All* runs unattended in the background and the results can be downloaded from Output.

**Slurm（LRZ 等）**：见 `slurm_analyze.sbatch` 开头的注释。简单说：先在登录节点用 `setup_katago.py` 把所有东西下载好，让作业只读本地文件；把分区名和容器镜像换成你所在集群的。**这只是模板，没有在真实硬件上验证过。**

**Slurm (LRZ etc.)**: see the comment at the top of `slurm_analyze.sbatch`. In short: download everything on the login node with `setup_katago.py` first, and let the job read local files only; replace the partition name / container image with your cluster's. **A template, not verified on real hardware.**

**如何获得 LRZ 权限**（据官方文档）：你需要有 LRZ 账号，**并且**属于一个已开通 AI Systems 的项目；TUM / LMU 的学生账号默认只有邮件、云存储这类服务，没有高性能计算系统的权限。途径有两条：找你的课程、Praktikum 或毕业论文导师，请其 LRZ 项目管理员（Master User）把你加进去；或者通过 BayernKI 申请。提交服务请求“AI topics → LRZ AI Systems - Request for Access”，并说明用途。登录 `login.ai.lrz.de` 需要身处慕尼黑科学网络（Munich Scientific Network）内，或者使用 VPN。

**How to get LRZ access** (official docs): you need an LRZ account **and** membership in a project with AI Systems enabled; TUM/LMU student accounts by default only get services such as mail and cloud storage, not the high-performance systems. Ways in: ask your course / Praktikum / thesis supervisor, whose LRZ project administrator (Master User) can add you; or apply through BayernKI. Submit a service request "AI topics → LRZ AI Systems - Request for Access" and state the purpose. Logging in to `login.ai.lrz.de` requires being inside the Munich Scientific Network or using the VPN.

**参数**：`--visits 220 --forced 100` 与本机基准一致；GPU 足够强时可以加 `--threads 3` 提速，但不要改 visits（否则结果无法与旧数据比较）。GPU/FP16 算出的数值与核显的并不逐位相同，这属于正常波动。

**Parameters**: `--visits 220 --forced 100` match the local baseline; on a strong GPU you can add `--threads 3` for more speed, but do not change visits (otherwise results are not comparable with the old data). GPU/FP16 numbers are not bit-identical to the integrated GPU's; that is normal fluctuation.

## 4. 用法 B：页面里的“算力”开关（可选，实时分析） / Usage B: the "compute" switch in the page (optional, real-time analysis)

左侧边栏底部有一行小字，“● 算力 · 缓存”。点击即可展开：

A small line at the bottom of the left sidebar, "● Compute · Cache". Click it to expand:

| 项目 / Item | 说明 / Description |
|---|---|
| 缓存（默认） / Cache (default) | 不联网，像以前一样使用已生成的 AI 数据 / No network; uses the already-generated AI data as before |
| 本机引擎 / Local engine | 连接你自己电脑上的 `katago_bridge.py`（默认 `http://127.0.0.1:8787`） / Connects to `katago_bridge.py` on your own computer (default `http://127.0.0.1:8787`) |
| 远程 GPU / Remote GPU | 连接你掌控的另一台机器（填写它的地址） / Connects to another machine you control (enter its address) |
| 令牌 / token | 桥接服务启动时会打印（也可以自己设置）。只保存在本浏览器的 localStorage 里（明文，同源脚本可以读取；不要在公用电脑上保存） / Printed when the bridge starts (or set it yourself). Stored only in this browser's localStorage (in plain text, readable by scripts of the same origin; do not store it on a shared computer) |
| 测试连接 / Test connection | 显示延迟、KataGo 版本和模型名称；模拟数据会明确标注 / Shows latency, KataGo version and model name; simulated data is clearly labeled |
| 分析当前局面 / Analyze current position | 在当前节点做 220 visits 的搜索，并对老师的每一手各做 100 visits 的强制评估（与离线流程相同） / Runs a 220-visit search at the current node and a forced 100-visit evaluation of each of the teacher's moves (same as the offline flow) |
| 点击棋盘上的空点 / Click an empty point on the board | 试下该点（颜色为行棋方），并在新局面中分析对方的应对；用左右方向键可以退回 / Tries that move (color = side to move) and analyzes the opponent's replies in the new position; the left/right keys step back |
| 无缓存时自动分析 / Auto-analyze when uncached | 走到没有缓存 AI 数据的节点时自动分析（默认关闭） / Automatically analyzes a node that has no cached AI data when you reach it (off by default) |

实时结果的呈现方式与缓存结果一致：半透明棋子的颜色 = 行棋方，圈的颜色和数字 = 比局部最优差多少目，蓝色虚线圈 = 老师走的那一手，悬停可以查看变化图；说明栏会显示“实时分析（本机/远程） · 搜索次数 · 秒数”。只会搜索讲解所在的局部区域（按与 `analyze2.region` 相同的分位数规则，由棋谱算出）。

Live results are presented the same way as cached ones: translucent stone color = side to move, ring color/number = how many points worse than the local best, blue dashed ring = the teacher's move, hover to see the variation; the caption bar says "live analysis (local/remote) · visits · seconds". Only the "teaching region" is searched (computed from the game record with the same percentile rule as `analyze2.region`).

**启动桥接服务（本机，以 Windows 为例）**：流水线 `orch2.py` 正在占用 GPU 时，不要启动真实引擎。下面代码块里的英文注释说明：没有设置令牌变量时，会自动生成一个并只打印一次；加上 `--fake` 则返回标注为模拟的假数据，可以在不占用 GPU 的情况下试用界面。

**Starting the bridge (local machine, Windows example)**: do not start the real engine while the pipeline `orch2.py` is using the GPU.

```powershell
$env:KATAGO_BRIDGE_TOKEN = "make up a random string of 20+ characters"   # if unset, one is generated and printed once
python remote\katago_bridge.py --katago D:\workspace\fun\Weiqi\Weiqi_AI\engine\katago-v1.18.0-opencl-windows-x64\katago.exe `
       --model D:\workspace\fun\Weiqi\Weiqi_AI\weights\network_file\kata1-tf3-b11c768-s12752M-d6531M.bin.gz
# To try the UI without touching the GPU:  python remote\katago_bridge.py --fake      (returns fake data labeled as simulated)
```

从 `http://localhost:8765` 打开的页面默认被允许；双击打开的 `file://` 页面需要加 `--allow-file-origin`；其他来源需要 `--allow-origin`。

A page opened from `http://localhost:8765` is allowed by default; a `file://` page opened by double-clicking needs `--allow-file-origin`; other origins need `--allow-origin`.

**使用远程 GPU 的合规方式**：(1) 在 LRZ、学校或自己租的虚拟机上启动桥接服务，再用 `ssh -L 8787:127.0.0.1:8787 <machine>` 把端口转发到本机，页面仍然使用 `http://127.0.0.1:8787`；(2) 或者在前面加一层带 TLS 的反向代理，或者给桥接服务传 `--cert/--key`。**不要**在没有 TLS 的情况下监听 `0.0.0.0`（令牌会以明文发送，桥接服务会对此发出警告）。我没有验证过 LRZ 的端口转发流程，请先读 LRZ 的 Jupyter/隧道 FAQ 并确认相关政策。

**Compliant ways to use a remote GPU**: (1) start the bridge on an LRZ / university / self-rented VM and forward the port to your machine with `ssh -L 8787:127.0.0.1:8787 <machine>`, so the page still uses `http://127.0.0.1:8787`; (2) or put a reverse proxy with TLS in front, or give the bridge `--cert/--key`. **Do not** listen on `0.0.0.0` without TLS (the token would be sent in clear text; the bridge warns about it). I have not verified LRZ's port-forwarding procedure; read the LRZ Jupyter/tunnel FAQ first and check the policy.

## 5. 服务条款风险（请认真读） / Terms-of-service risks (read this honestly)

来源列在文末；以官方页面当前的措辞为准。

Sources are listed at the end; the current wording of the official pages is what counts.

- **Colab 免费版**：FAQ 把“连接远程代理”和“文件托管 / 媒体服务 / 其他与交互式计算无关的 Web 服务”列为所有托管运行时上的禁止项，并把“SSH、远程桌面等远程控制”列为免费（或计算单元为零）运行时上的禁止项；违规的运行时可能被不经警告直接终止。FAQ 还列出了“国际象棋训练”和“分布式计算 worker”。因此：

  **Colab free tier**: the FAQ lists "connecting to remote proxies" and "file hosting / media serving / other web services unrelated to interactive computing" as prohibited on all hosted runtimes, and "remote control such as SSH, remote desktop" as prohibited on free (or zero-compute-unit) runtimes; offending runtimes may be terminated without warning. It also lists "chess training" and "distributed computing workers". Therefore:

  - 直接在笔记本里跑 KataGo 批量分析并下载结果，属于交互式计算，**是允许的**，但你必须在场并保持页面打开。KataGo 分析既不是训练，也不是分布式 worker，但这只是我的理解，不是 Google 的保证。

    Running KataGo batch analysis directly in the notebook and downloading the results is interactive computing and **allowed**, but you must be present with the page open. KataGo analysis is neither training nor a distributed worker, but that is my reading, not a guarantee from Google.

  - 开 ngrok/cloudflared 隧道、使用 `colab_ssh`、让网页从外部实时连接 Colab 里的桥接服务，或者使用保活脚本：这些做法**违反**条款，或者是在绕过限制。**不要这么做，本目录也不提供。** 对于仍有剩余计算单元的付费用户，SSH 限制有所不同，但“远程代理 / Web 服务”这条规则仍然适用于所有托管运行时，所以即便用 Pro，也不建议把桥接服务暴露出去。

    Opening an ngrok/cloudflared tunnel, `colab_ssh`, letting the web page connect from outside to a bridge inside Colab in real time, or using keep-alive scripts: these **violate** the terms or circumvent the limits. **Do not do it; this directory does not provide it.** SSH restrictions differ for paid users with positive compute units, but the "remote proxy / web service" rule still applies to every hosted runtime, so exposing the bridge is not recommended even with Pro.

  - 配额没有公布，也不保证分到 GPU；提示已达到使用上限时就停下来，不要换账号，也不要想办法绕过。

    The quota is not published and a GPU is not guaranteed; when it says the usage limit has been reached, stop. Do not switch accounts or work around it.

- **Kaggle**：官方文档给出每周的 GPU 配额（约 30 小时，“有时更高”）和 60 分钟的空闲超时；GPU 和 Internet 都需要手机验证。一个开源项目报告说，Kaggle 封堵了进入运行中 kernel 的 SSH 隧道，并警告这可能违反条款。我没有在 Kaggle 的条款里找到明确允许“对外提供服务”的文字，所以只使用批处理模式。

  **Kaggle**: the official docs give a weekly GPU quota (about 30 hours, "or sometimes higher") and a 60-minute idle timeout; GPU and Internet need phone verification. An open-source project reports that Kaggle blocked SSH tunnels into running kernels and warned that this may violate the terms. I found no text in Kaggle's terms that explicitly allows "serving to the outside", so only batch mode is used.

- **LRZ**：账号与项目绑定，必须说明用途，还要遵守出口管制声明；学生账号需要挂靠项目。合规的用法是批处理作业。

  **LRZ**: accounts are tied to projects, the purpose must be stated, and the export-control statement must be observed; student accounts need a project. The compliant use is batch jobs.

- **Lightning AI**：免费额度的规则最近变过（见来源）；它的 Studio 支持 SSH，但我没有核实对外开放端口的条款，所以目前既不推荐，也没有提供脚本。

  **Lightning AI**: the free-credit rules have changed recently (see the sources); its Studios support SSH, but I did not verify the port-exposure terms, so it is neither recommended nor given a script for now.

- **数据**：上传到云端的只有视频里摆出的棋局局面（坐标），不包含账号或个人信息。

  **Data**: the only thing uploaded to the cloud is the Go positions set up in the videos (coordinates); no account or personal information.

## 6. 文件 / Files

| 文件 / File | 用途 / Purpose |
|---|---|
| `analyze_remote.py` | `analyze2.py` 的移植版，加上断点续跑和多分组循环；输出 `g_<name>.a2.json` 和 `.a2.meta.json` / Port of `analyze2.py` + resume + loop over several groups; outputs `g_<name>.a2.json` + `.a2.meta.json` |
| `setup_katago.py` | 下载 Linux GPU 版 KataGo（默认 v1.18.2 + cuda12.1-cudnn9.8.0），用 `ldd` 检查依赖，并把缺失的 CUDA 库用 pip 装到单独的目录 / Downloads the Linux GPU build of KataGo (default v1.18.2 + cuda12.1-cudnn9.8.0), checks with `ldd`, and pip-installs missing CUDA libraries into a separate directory |
| `katago_batch.ipynb` / `make_notebook.py` | 同时适用于 Colab 和 Kaggle 的笔记本（内嵌上面两个脚本）；修改脚本后用 `python make_notebook.py` 重新生成 / Notebook for both Colab and Kaggle (embeds the two scripts above); after changing a script, regenerate with `python make_notebook.py` |
| `slurm_analyze.sbatch` | Slurm 批处理模板（未在真实硬件上验证） / Slurm batch template (not verified on real hardware) |
| `katago_bridge.py` | 可选：把 KataGo 分析暴露为 HTTP 接口（令牌 + CORS + 参数校验）；`--fake` 让你不用 GPU 也能试用界面 / Optional: KataGo analysis → HTTP (token + CORS + validation); `--fake` lets you try the UI without a GPU |
| `selftest.py` | 无需 GPU 的自检（模拟引擎）：视角换算、区域、强制评估、断点续跑、与 `analyze2.py` 对比、桥接服务的校验/认证/CORS / GPU-free self-test (fake engine): perspective conversion, region, forced evaluation, resume, comparison with `analyze2.py`, bridge validation/auth/CORS |

## 7. 排障 / Troubleshooting

- **`nvidia-smi` 没有任何输出**：没有选择 GPU 运行时（Colab：Runtime → Change runtime type；Kaggle：Accelerator）。

  **`nvidia-smi` prints nothing**: the GPU runtime is not selected (Colab: Runtime → Change runtime type; Kaggle: Accelerator).

- **Colab 提示无法连接到 GPU，或已达到使用上限**：免费额度用完了；等一会儿再试，或者改用 Kaggle / LRZ。

  **Colab says it cannot connect to a GPU / the usage limit has been reached**: the free quota is used up; wait a while and retry, or switch to Kaggle / LRZ.

- **`setup_katago.py` 报告缺少 `libcudnn.so.9` / `libcublas.so.12` 等**：脚本会用 pip 把它们装到 `katago_env/nvlibs` 并设置 `LD_LIBRARY_PATH`；如果仍然失败，就把 `KATAGO_BUILD` 改成 `cuda12.5-cudnn9.8.0` 或 `cuda12.8-cudnn9.8.0` 再试；还不行就用 v1.18.1 的 Linux OpenCL 版（慢，但兼容性最好）。Transformer 网络需要 cuDNN >= 9.8，8.9.7 的构建版本会慢得多。

  **`setup_katago.py` reports missing `libcudnn.so.9` / `libcublas.so.12` etc.**: the script pip-installs them into `katago_env/nvlibs` and sets `LD_LIBRARY_PATH`; if it still fails, change `KATAGO_BUILD` to `cuda12.5-cudnn9.8.0` or `cuda12.8-cudnn9.8.0` and retry; failing that, use the OpenCL Linux build of v1.18.1 (slow, but the most universal). Transformer networks need cuDNN >= 9.8; the 8.9.7 builds are "a LOT slower".

- **缺少 `libzip.so.x`**：有 root 权限时执行 `apt-get install libzip4`（Ubuntu 24.04 上叫 `libzip4t64`）；在集群上则请管理员加载对应的模块。

  **Missing `libzip.so.x`**: with root, `apt-get install libzip4` (on Ubuntu 24.04 it is `libzip4t64`); on a cluster, ask the admin to load the module.

- **KataGo 一启动就退出**：查看输出目录里的 `katago_stderr.log`；常见原因是显存不足（把 `--batch 64` 改成 `32`）或模型路径写错。

  **KataGo exits right after starting**: look at `katago_stderr.log` in the output directory; the usual causes are insufficient GPU memory (change `--batch 64` to `32`) or a wrong model path.

- **`ModuleNotFoundError` / 找不到 n.json**：输入文件必须命名为 `g_*.n.json`。

  **`ModuleNotFoundError` / n.json not found**: input files must be named `g_*.n.json`.

- **页面提示无法连接**：桥接服务没有运行，或者地址 / 端口不对，或者页面来源不在白名单里（`--allow-origin`、`--allow-file-origin`），或者 `https` 页面去连 `http` 地址（浏览器会拦截）。页面会自动回退到缓存数据。

  **The page says it cannot connect**: the bridge is not running / wrong address or port / the page origin is not in the allowlist (`--allow-origin`, `--allow-file-origin`) / an `https` page connecting to an `http` address (the browser blocks it). The page falls back to the cached data automatically.

- **页面提示没有声明 winratesAs=BLACK**：你连到的不是本目录的桥接服务，或者版本不匹配；为避免视角错误，页面拒绝使用它。

  **The page says winratesAs=BLACK was not declared**: you connected to something that is not this directory's bridge, or the versions do not match; the page refuses to use it to avoid perspective errors.

- **分数看起来系统性偏正或偏负**：先看说明栏里的“颜色 = 行棋方”；离线数据和实时数据用的都是行棋方视角，而不是黑棋视角。

  **Scores look systematically positive/negative**: first look at "color = side to move" in the caption bar; both offline and live data use the side-to-move perspective, not Black's.

## 8. 已验证与未验证的内容 / What was verified / what was not

已验证：`selftest.py` 全部通过（模拟引擎；与 `analyze2.py` 逐字节相同；桥接服务的校验 / 认证 / CORS / HTTP 处理在内存流上运行正确）；页面的默认行为没有变化，控制台没有报错；页面的连接测试、分析、试下、失败回退和视角声明检查，在**页内 fetch 桩（模拟的桥接服务）**上运行正确，候选点的颜色、正负号和强制评估都符合预期；真实地址连不上时，约 3 秒后给出提示并回退到缓存。

Verified: `selftest.py` passes completely (fake engine; byte-for-byte identical with `analyze2.py`; the bridge's validation / auth / CORS / HTTP handling runs correctly on in-memory streams); the page's default behaviour is unchanged with no console errors; the page's connection test, analysis, trial moves, failure fallback, and perspective-declaration check run correctly against an **in-page fetch stub (a simulated bridge)**, with candidate-point colors / signs / forced evaluations as expected; an unreachable real address → a message and fallback to the cache after about 3 seconds.

**未验证**：真实的 KataGo、真实的 GPU、在 Colab/Kaggle/LRZ 上的实际运行（没有账号，而且按要求没有运行 KataGo）；`setup_katago.py` 在各云端镜像上的库兼容性；各个加速倍数（都是估算）；桥接服务的真实 socket 和 SSH 端口转发；Slurm 模板；浏览器 WebGPU 方案也没有试过。

**Not verified**: a real KataGo, a real GPU, actual runs on Colab/Kaggle/LRZ (no accounts, and as requested KataGo was not run); library compatibility of `setup_katago.py` on the cloud images; the speed-up factors (all estimates); the bridge's real sockets and SSH port forwarding; the Slurm template; the browser WebGPU option was not tried.

## 来源（访问日期 2026-11-01） / Sources (accessed 2026-11-01)

- Colab FAQ（禁止的用法、12 小时上限、GPU 型号可能变化）：<https://research.google.com/colaboratory/faq.html>

  Colab FAQ (prohibited uses, 12 hours, GPU models may change): <https://research.google.com/colaboratory/faq.html>

- KataGo v1.18.2 / v1.18.0 / v1.17.0 发布说明：<https://github.com/lightvector/KataGo/releases/tag/v1.18.2> · <https://github.com/lightvector/KataGo/releases/tag/v1.18.0> · <https://github.com/lightvector/KataGo/releases/tag/v1.17.0>

  KataGo v1.18.2 / v1.18.0 / v1.17.0 release notes: <https://github.com/lightvector/KataGo/releases/tag/v1.18.2> · <https://github.com/lightvector/KataGo/releases/tag/v1.18.0> · <https://github.com/lightvector/KataGo/releases/tag/v1.17.0>

- 免费 GPU 汇总（第三方，2026-09-21）：<https://gpuperhour.com/blog/free-cloud-gpus-and-credits>

  Free GPU roundup (third party, 2026-09-21): <https://gpuperhour.com/blog/free-cloud-gpus-and-credits>

- Kaggle 文档：<https://www.kaggle.com/docs/efficient-gpu-usage> · <https://www.kaggle.com/docs/notebooks> · 手机验证的讨论 <https://www.kaggle.com/product-feedback/255038> · 隧道被封的报告（社区） <https://github.com/lamhoangtung/remokaggle>

  Kaggle docs: <https://www.kaggle.com/docs/efficient-gpu-usage> · <https://www.kaggle.com/docs/notebooks> · phone verification discussion <https://www.kaggle.com/product-feedback/255038> · report of blocked tunnels (community) <https://github.com/lamhoangtung/remokaggle>

- Lightning AI：<https://lightning.ai/pricing> · 价格调整的报道（第三方） <https://www.usagepricing.com/blueprint/activity/lightning-ai-2026-09-21-gpu-rate-card-reprice>

  Lightning AI: <https://lightning.ai/pricing> · price-change report (third party) <https://www.usagepricing.com/blueprint/activity/lightning-ai-2026-09-21-gpu-rate-card-reprice>

- Hugging Face Spaces 的 GPU 文档：<https://huggingface.co/docs/hub/main/spaces-gpus>

  Hugging Face Spaces GPU: <https://huggingface.co/docs/hub/main/spaces-gpus>

- LRZ AI Systems：<https://doku.lrz.de/ai-systems-11484278.html> · 申请权限 <https://doku.lrz.de/1-access-10746642.html> · 登录 <https://doku.lrz.de/1-1-ai-systems-login-2498299908.html> · Jupyter/隧道 FAQ <https://doku.lrz.de/faq-jupyter-on-hpc-systems-10746056.html>

  LRZ AI Systems: <https://doku.lrz.de/ai-systems-11484278.html> · access request <https://doku.lrz.de/1-access-10746642.html> · login <https://doku.lrz.de/1-1-ai-systems-login-2498299908.html> · Jupyter/tunnel FAQ <https://doku.lrz.de/faq-jupyter-on-hpc-systems-10746056.html>

- NHR@FAU / BayernKI：<https://hpc.fau.de/application-for-bayernki-access-at-nhrfau>

  NHR@FAU / BayernKI: <https://hpc.fau.de/application-for-bayernki-access-at-nhrfau>

- 在浏览器里运行的 KataGo：web-katrain <https://github.com/Sir-Teo/web-katrain>（TF.js WebGPU，MIT，上传上限 128MB） · Kaya <https://github.com/kaya-go/kaya>（ONNX）

  In-browser KataGo: web-katrain <https://github.com/Sir-Teo/web-katrain> (TF.js WebGPU, MIT, upload limit 128MB) · Kaya <https://github.com/kaya-go/kaya> (ONNX)

- 社区提供的 KataGo 在 T4 上的数据（较旧）：<https://lifein19x19.com/viewtopic.php?p=263794>

  Community data for KataGo on a T4 (old): <https://lifein19x19.com/viewtopic.php?p=263794>
