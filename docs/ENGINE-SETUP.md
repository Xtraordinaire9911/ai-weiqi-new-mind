# KataGo 继续推演:本机与远程设置 / Continue with KataGo: local and remote setup

本文说明怎样让查看器里的「KataGo 继续推演」面板连上你自己的 KataGo:在你自己的电脑上(本机),或者在你有权使用的远程 GPU 上。面板只需要两样东西:桥接服务的地址和 token。资料读取于 2026-11-01;凡是没有在官方页面上核实的内容,都写作"未核实 / not verified"。写这份文档时没有注册任何账号,也没有在任何平台上运行任何东西,没有运行真实的 KataGo。

This explains how to connect the viewer's "continue with KataGo" panel to your own KataGo: on your own computer (local), or on a remote GPU you are allowed to use. The panel needs only two things: the address of the bridge and a token. Facts were read on 2026-11-01; whatever could not be checked on an official page is marked "未核实 / not verified". No account was created, nothing was run on any platform, and no real KataGo was run while writing this.

批量离线分析(一次性给整批定式生成 AI 数据)是另一件事,见 [`docs/COMPUTE-PLATFORMS.md`](COMPUTE-PLATFORMS.md) 和 [`remote/README.md`](../remote/README.md);本文不重复它们。

Batch offline analysis (generating AI data for a whole set of joseki in one go) is a different job, see [`docs/COMPUTE-PLATFORMS.md`](COMPUTE-PLATFORMS.md) and [`remote/README.md`](../remote/README.md); this page does not repeat them.

## 1. 隐私:你的数据去哪里 / Privacy: where your data goes

默认情况下页面不联网:算力是「缓存」,只读取已经生成的数据。只有你把「算力」改成「本机」或「远程」之后,页面才会向你自己填写的那个地址发请求,内容是当前局面的棋盘坐标(哪些点有子、走了哪几手、讲解区域),token 只放在 `Authorization` 头里,不会出现在地址里。作者没有服务器,也不会收到任何数据;页面里没有统计、没有第三方请求、没有 cookie。

By default the page does not use the network: the compute source is "cache" and only reads the data that was already generated. Only after you switch the compute source to "local" or "remote" does the page send requests, and only to the address you typed. A request carries the board coordinates of the current position (which points hold stones, the moves, the teaching region); the token goes in the `Authorization` header only and never in the address. The author runs no server and receives nothing; the page has no analytics, no third party requests and no cookies.

| 什么 / What | 去哪里 / Where it goes |
|---|---|
| 当前局面的坐标 / Coordinates of the current position | 只发给你填的地址,而且只在选了「本机/远程」之后 / Only to the address you typed, and only after choosing "local/remote" |
| 令牌 token / The token | 只放在发往该地址的 `Authorization` 头里;存在本浏览器的 localStorage / Only in the `Authorization` header to that address; stored in this browser's localStorage |
| 地址、token、次数上限等设置 / Address, token, visits cap and other settings | 本浏览器的 localStorage(键 `josekiapp.rc.v1` 和 `josekiapp.ep.v1`),每次读写都在 try/catch 里 / This browser's localStorage (keys `josekiapp.rc.v1` and `josekiapp.ep.v1`), every access inside try/catch |
| 「采用这条线」复制的 SGF / The SGF that "adopt this line" copies | 只进剪贴板,不联网 / Clipboard only, no network |
| 「网络活动」列表 / The "network activity" list | 只在内存里,刷新页面就清空,不保存也不发送 / In memory only, cleared on reload, never stored or sent |
| 视频链接 / Video links | 只有你点击时才会打开 / Opened only when you click them |

如果你用远程 GPU,当前局面的坐标会到达那家服务商的机器,他们能看到;经 SSH 转发或 https 时,路上的人看不到内容。页面打开时,如果「算力」还停在「本机/远程」,它会向你填的地址做一次连接测试(`/health`),不会更多。

With a remote GPU, the coordinates of the position reach that provider's machine and the provider can see them; over an SSH forward or https, people on the way cannot. If the compute source was left on "local/remote", the page makes one connection test (`/health`) to your address when it opens, nothing more.

怎么自己验证:面板里的「网络活动」列出本页自己发出的每一个请求(时间、主机、路径、用途、字节数、状态),它由唯一的联网函数 `EngineNet.request`(`engine_net.js`,全文不到 80 行)写入,所以按构造就是完整的;浏览器开发者工具的网络面板也应该只看到你的地址和本页自己的文件。源码可以审计,联网代码只在 `engine_net.js`。自动测试 `tests/privacy.test.js` 会读取 `index.html` 和所有查看器 js 文件,发现 `engine_net.js` 之外出现任何联网接口(`fetch`、`XMLHttpRequest`、`WebSocket`、`EventSource`、`sendBeacon`、`importScripts`、地理位置、cookie、动态创建脚本或图片等),或者自动加载绝对地址的外部资源,就会失败。这个测试能挡住疏忽和后来的改动,但它不能证明一个故意隐藏代码的人不存在,所以请以读源码为准。

How to check it yourself: the "network activity" fold-out in the panel lists every request the page itself made (time, host, path, purpose, bytes, status). It is written by the one network function `EngineNet.request` (`engine_net.js`, under 80 lines), so it is complete by construction; the network tab of the browser developer tools should also show only your address and the page's own files. The source can be audited, and the network code is only in `engine_net.js`. The automatic test `tests/privacy.test.js` reads `index.html` and every viewer js file and fails if any network interface (`fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `sendBeacon`, `importScripts`, geolocation, cookies, dynamically created scripts or images and so on) appears outside `engine_net.js`, or if an external absolute address is loaded automatically. The test guards against accidents and later changes; it cannot prove that nobody hides code on purpose, so reading the source is the real check.

```
docker run --rm -v "$PWD":/app:ro -w /app node:20-alpine node --test tests/
```

## 2. 一分钟上手 / Quick start

先在本机启动桥接服务,再在页面里选「本机」。第一步,运行启动脚本(Windows 用 PowerShell,macOS 和 Linux 用 bash),它会在常见位置找 KataGo 和网络文件并启动桥,屏幕上会打印一次 token。第二步,打开页面,在右侧一条变化的终点(或点棋盘下方的「推演」按钮)找到「KataGo 继续推演」卡片,把「算力」选为「本机」,在左侧「算力」里填 token(地址默认就是 `http://127.0.0.1:8787`)。第三步,点「开始」。

Start the bridge on your computer first, then choose "local" in the page. Step one: run the launcher (PowerShell on Windows, bash on macOS and Linux); it looks in the usual places for KataGo and a network file, starts the bridge, and prints a token once. Step two: open the page, find the "KataGo 继续推演" card at the end of a variation in the right column (or press the "推演" button under the board), set the compute source to "local" and paste the token into the "算力" fold-out on the left (the address already defaults to `http://127.0.0.1:8787`). Step three: press "开始".

```
powershell -ExecutionPolicy Bypass -File remote\start_bridge.ps1
bash remote/start_bridge.sh
```

不想动真实引擎、只想看看界面:加 `-Fake`(PowerShell)或 `--fake`(bash),桥会返回明确标注为"模拟"的假数据。

To only look at the interface without touching a real engine, add `-Fake` (PowerShell) or `--fake` (bash); the bridge then returns data that is clearly labelled as simulated.

## 3. 本机 KataGo / Local KataGo

### 3.1 下载什么 / What to download

KataGo 官方发布页是 <https://github.com/lightvector/KataGo/releases>,神经网络在 <https://katagotraining.org/networks/>。选哪个后端,官方发布说明(v1.18.1)的建议是:NVIDIA 显卡用 CUDA(cuDNN 9.8.0 或更新)或 TensorRT;AMD 显卡用新的 ROCm 后端;Intel 的 GPU 或 NPU 用 ONNX 加 OpenVINO;其他或较老的 GPU 用 OpenCL(能用但对 Transformer 网络慢得多);macOS 用 Metal(一般通过 Homebrew 安装);只有 CPU 时用 Eigen AVX2(很慢)。发布页提示:v1.18.1 是 CUDA 之外所有后端的最新版本,CUDA 的更新版本是 v1.18.2。Windows 和 Linux 有预编译的压缩包,macOS 没有官方压缩包。

The official KataGo releases are at <https://github.com/lightvector/KataGo/releases> and the neural networks at <https://katagotraining.org/networks/>. For choosing a backend, the official release notes (v1.18.1) advise: CUDA (cuDNN 9.8.0 or newer) or TensorRT for NVIDIA cards; the new ROCm backend for AMD cards; ONNX with OpenVINO for Intel GPUs or NPUs; OpenCL for other or older GPUs (it works but is much slower for transformer networks); Metal on macOS (usually installed through Homebrew); and Eigen AVX2 when you only have a CPU (very slow). The notes say v1.18.1 is the latest release for every backend except CUDA, whose newer release is v1.18.2. Windows and Linux have precompiled zip files; macOS has no official zip.

| 系统与硬件 / System and hardware | 下载什么 / What to download | 备注 / Notes |
|---|---|---|
| Windows,NVIDIA / Windows, NVIDIA | `katago-v1.18.2-cuda12.8-cudnn9.8.0-windows-x64.zip`(或同系列的其他 CUDA 版本) / `katago-v1.18.2-cuda12.8-cudnn9.8.0-windows-x64.zip` (or another CUDA build of the same series) | 要先装 NVIDIA 驱动和对应的 CUDA、cuDNN;发布说明说 cuDNN 8.9.7 的包跑 Transformer 会慢很多 / Install the NVIDIA driver and the matching CUDA and cuDNN first; the notes say the cuDNN 8.9.7 builds are much slower for transformers |
| Windows,AMD / Windows, AMD | `katago-v1.18.1-rocm7.13-<gfx 系列>-windows-x64.zip` / `katago-v1.18.1-rocm7.13-<gfx family>-windows-x64.zip` | 按显卡系列选(gfx103X、gfx110X、gfx1151、gfx120X),需要较新的 Adrenalin 驱动,构建标注为偏实验性 / pick by GPU family (gfx103X, gfx110X, gfx1151, gfx120X); needs a recent Adrenalin driver; the notes call the build somewhat experimental |
| Windows,其他显卡 / Windows, other GPUs | `katago-v1.18.1-opencl-windows-x64.zip` | 第一次运行会自动调优,通常 5 到 30 秒,旧机器可能要几分钟,不是卡住 / the first run tunes itself, usually 5 to 30 seconds, minutes on old machines, it is not hung |
| Windows,只有 CPU / Windows, CPU only | `katago-v1.18.1-eigenavx2-windows-x64.zip` | 很慢;太老的 CPU 用 `eigen` / very slow; use `eigen` on an ancient CPU |
| Linux | 同样的命名,把 `windows` 换成 `linux`:`cuda...`、`trt...`、`opencl`、`eigenavx2` / the same names with `linux` instead of `windows`: `cuda...`, `trt...`, `opencl`, `eigenavx2` | 可执行文件在 Ubuntu 22.04 上编译;CUDA、TensorRT、OpenCL 驱动要自己装 / the executables were built on Ubuntu 22.04; you install the CUDA, TensorRT or OpenCL drivers yourself |
| macOS,Apple 芯片 / macOS, Apple silicon | `brew install katago`(Metal 后端) / `brew install katago` (Metal backend) | Homebrew 的预编译包列表里有 arm64 的 macOS(arm64_tahoe、arm64_sequoia、arm64_golden_gate) / the Homebrew bottle list has arm64 macOS (arm64_tahoe, arm64_sequoia, arm64_golden_gate) |
| macOS,Intel 芯片 / macOS, Intel | 没有官方压缩包,Homebrew 的预编译包列表里没有 Intel macOS / no official zip, and the Homebrew bottle list has no Intel macOS | 从源码编译(见官方 Compiling.md),选 Eigen 或 OpenCL;Metal 能否用于 Intel Mac:未核实 / build from source (see the official Compiling.md) with Eigen or OpenCL; whether Metal works on Intel Macs: not verified |

网络文件(`.bin.gz`)去 <https://katagotraining.org/networks/> 下载;官方 README 建议默认用最强或最新的 b18 尺寸网络(b18c384nbt)。本项目已缓存的 AI 数据是用 `kata1-tf3-b11c768-s12752M-d6531M.bin.gz` 生成的,换一个网络,同一局面的数字会略有不同;桥接服务可以在你允许的几个网络之间切换(见第 5 节)。网络文件的许可条款以官方网络页面为准,未核实。

Download the network file (`.bin.gz`) from <https://katagotraining.org/networks/>; the official README suggests the strongest or most recent b18 sized net (b18c384nbt) as the default. The AI data cached in this project was made with `kata1-tf3-b11c768-s12752M-d6531M.bin.gz`; with another network the numbers for the same position differ a little, and the bridge can switch between the networks you allow (section 5). The licence terms of a network file follow the official networks page, not verified.

装好以后先自检一次:`katago benchmark -model <网络>.bin.gz` 会给出建议的线程数,`katago genconfig -model <网络>.bin.gz -output gtp_custom.cfg` 会生成配置(官方 README)。桥接服务自己会生成一份分析配置,所以多数情况下你只需要这两样:KataGo 可执行文件和网络文件。

After installing, check it once: `katago benchmark -model <net>.bin.gz` suggests a thread count, and `katago genconfig -model <net>.bin.gz -output gtp_custom.cfg` writes a config (official README). The bridge generates an analysis config itself, so in most cases you only need two things: the KataGo executable and a network file.

### 3.2 启动桥接服务 / Start the bridge

启动脚本不下载、不安装、不联网,只在这台电脑的几个常见位置找 KataGo 可执行文件和最新的 `.bin.gz`,然后在 127.0.0.1 启动桥。找不到时它会说缺什么,并打印你需要提供的全部内容(`--print-setup` 也可以单独运行):KataGo 可执行文件的路径、网络文件、可选的配置文件、端口,仅此而已。

The launchers download nothing, install nothing and use no network. They only look in a few usual places on this computer for the KataGo executable and the newest `.bin.gz`, then start the bridge on 127.0.0.1. When something is missing they say what, and print everything you must provide (`--print-setup` also runs on its own): the path of the KataGo executable, the network file, an optional config file, and the port, nothing else.

| 系统 / System | 命令 / Command |
|---|---|
| Windows | `powershell -ExecutionPolicy Bypass -File remote\start_bridge.ps1`(加 `-PrintSetup` 只看需要提供什么;`-Katago`、`-Model`、`-Config`、`-Port` 手动指定) / `powershell -ExecutionPolicy Bypass -File remote\start_bridge.ps1` (`-PrintSetup` only shows what is needed; `-Katago`, `-Model`, `-Config`, `-Port` set things by hand) |
| macOS、Linux / macOS, Linux | `bash remote/start_bridge.sh`(加 `--print-setup`;`--katago`、`--model`、`--config`、`--port`) / `bash remote/start_bridge.sh` (`--print-setup`; `--katago`, `--model`, `--config`, `--port`) |
| 手动 / By hand | `python remote/katago_bridge.py --katago <路径/path> --model <网络/net>.bin.gz` |

启动后屏幕上会打印一次随机 token(也可以用环境变量 `KATAGO_BRIDGE_TOKEN` 自己设一个,至少 16 个字符更稳妥)。页面如果是从 `http://localhost:8765` 打开的,桥默认就允许;如果是直接双击 `index.html`(`file://`),启动时要加 `--allow-file-origin`(脚本里写成 `-ExtraArgs '--allow-file-origin'`,或 bash 里 `-- --allow-file-origin`);其他来源要用 `--allow-origin <来源>`。同一目录里的其他 `.bin.gz` 会自动出现在面板的「网络」下拉框里,可以随时切换。

On start-up a random token is printed once (you can also set your own with the environment variable `KATAGO_BRIDGE_TOKEN`, at least 16 characters is safer). A page opened from `http://localhost:8765` is allowed by default; if you double-click `index.html` (`file://`), start the bridge with `--allow-file-origin` (in the script: `-ExtraArgs '--allow-file-origin'`, or `-- --allow-file-origin` in bash); any other origin needs `--allow-origin <origin>`. The other `.bin.gz` files in the same folder appear automatically in the panel's "网络" drop-down and can be switched at any time.

### 3.3 在面板里填什么 / What to fill in the panel

只填两样:桥接地址和 token。本机时地址就是 `http://127.0.0.1:8787`(端口改过就写你改的),token 是启动桥时打印的那串。填写位置是页面左侧底部「算力」折叠栏里的两个输入框;卡片里的「打开算力设置」按钮会直接带你过去。填好后页面会做一次连接测试,成功时卡片状态行会显示"本机 · 网络名 · 后端 · 空闲"。

Only two things: the bridge address and the token. For a local bridge the address is `http://127.0.0.1:8787` (your own port if you changed it) and the token is the string printed when the bridge started. They go into the two input fields of the "算力" fold-out at the bottom of the left column; the "打开算力设置" button on the card takes you there. The page then makes a connection test, and on success the card's status line reads "本机 · network name · backend · 空闲".

## 4. 远程 GPU / Remote GPU

### 4.1 先读这三条 / Read these three first

第一,只在服务条款允许的平台上运行桥。很多免费笔记本服务(Colab、Kaggle,以及一些国内平台)禁止把它当服务器,不要用隧道、代理或保活脚本去绕开,账号可能被封;这些平台只适合批量离线分析,见 [`docs/COMPUTE-PLATFORMS.md`](COMPUTE-PLATFORMS.md)。第二,不要让桥在没有 TLS 的情况下对公网开放:要么用 SSH 端口转发,要么用平台自己提供的 https 地址,要么在前面放一个带证书的反向代理。第三,https 页面不能调用普通的 http 地址(只有 `localhost`、`127.0.0.1` 这类回环地址是例外),所以"公网 IP 加端口"的 http 地址只能给 http 页面或本地文件使用。

First, run the bridge only on platforms whose terms allow it. Many free notebook services (Colab, Kaggle, and some Chinese platforms) forbid using them as a server; do not work around that with tunnels, proxies or keep-alive scripts, the account can be banned. Those platforms are for batch offline analysis only, see [`docs/COMPUTE-PLATFORMS.md`](COMPUTE-PLATFORMS.md). Second, never expose the bridge to the internet without TLS: use an SSH port forward, or the https address the platform itself provides, or put a reverse proxy with a certificate in front. Third, an https page cannot call a plain http address (the loopback addresses `localhost` and `127.0.0.1` are the exception), so a "public IP plus port" http address only works for an http page or a local file.

### 4.2 四种连接方式 / Four ways to connect

| 方式 / Method | 怎么做 / How | 面板里填 / What goes into the panel | 注意 / Caution |
|---|---|---|---|
| SSH 端口转发 / SSH port forward | 在你的电脑上:`ssh -L 8787:127.0.0.1:8787 <用户>@<主机>`,桥在远程机器上保持默认的 127.0.0.1 监听 / on your computer: `ssh -L 8787:127.0.0.1:8787 <user>@<host>`; on the remote machine the bridge keeps its default 127.0.0.1 listening | `http://127.0.0.1:8787` 和 token / `http://127.0.0.1:8787` and the token | 最简单也最安全,不需要任何公网端口;连接断开时要重新转发 / simplest and safest, no public port needed; re-run the forward when the connection drops |
| 平台的端口映射或 HTTP 代理 / Vendor port mapping or HTTP proxy | 在平台的控制台里把容器端口 8787 暴露出来;桥要监听 `0.0.0.0` 并带 `--allow-origin <你的页面来源>` / expose container port 8787 in the vendor console; the bridge must listen on `0.0.0.0` and take `--allow-origin <your page origin>` | 平台给出的地址(见下表)和 token / the address the platform gives (see the table below) and the token | 只靠 token 保护:用 20 个字符以上的随机 token;http 地址不能给 https 页面用 / protected by the token only: use a random token of 20 or more characters; an http address cannot be used from an https page |
| JupyterLab 代理 / JupyterLab proxy | 有些平台的 JupyterLab 带 `jupyter-server-proxy`,桥的页面地址形如 `https://<平台主机>/proxy/8787`(路径前缀会被保留) / some platforms ship JupyterLab with `jupyter-server-proxy`, the bridge then answers at an address like `https://<platform host>/proxy/8787` (a path prefix is kept) | 带 `/proxy/8787` 的 https 地址和 token / the https address with `/proxy/8787` and the token | 未在真实平台上验证;只有平台条款允许在笔记本里提供服务时才可以用,Colab 和 Kaggle 不行 / not verified on a real platform; only if the platform terms allow serving from a notebook, which Colab and Kaggle do not |
| 自己的 https 反向代理 / Your own https reverse proxy | 在远程机器上用 Caddy 或 nginx 放一个带证书的代理,转发到 127.0.0.1:8787;流式响应要关掉缓冲 / put Caddy or nginx with a certificate in front on the remote machine, forwarding to 127.0.0.1:8787; turn buffering off for the streamed responses | `https://<你的域名>` 和 token / `https://<your domain>` and the token | 桥已经发送 `X-Accel-Buffering: no`;Caddy 示例见下 / the bridge already sends `X-Accel-Buffering: no`; a Caddy example follows |

```
# Caddyfile (example): certificate by Caddy, no buffering for the NDJSON stream
bridge.example.org {
    reverse_proxy 127.0.0.1:8787 {
        flush_interval -1
    }
}
```

路径前缀(像 `/proxy/8787`)可以直接写在面板的桥接地址里,面板会把接口名接在后面;但地址里不能带 `?` 参数或 `#`,token 永远只填在 token 栏。

A path prefix (like `/proxy/8787`) can be written directly into the panel's bridge address and the panel appends the endpoint name; but the address must not carry a `?` query or a `#`, and the token is only ever typed into the token field.

浏览器的拦截有三种,面板会把它们翻译成一句话加一条修法(见第 6 节):混合内容(https 页面访问 http 地址)、CORS(桥不认这个页面的来源,用 `--allow-origin` 加上)、以及从公网页面访问局域网或本机地址时的"私有网络访问"预检(桥会回应 `Access-Control-Allow-Private-Network: true`)。较新的 Chrome 是否还会弹出"本地网络访问"的权限提示、Safari 是否放行从 https 页面访问 `http://127.0.0.1`:未核实。

The browser can block in three ways, and the panel turns each into one sentence and one fix (section 6): mixed content (an https page calling an http address), CORS (the bridge does not know this page's origin, add it with `--allow-origin`), and the "private network access" preflight when a public page calls a LAN or local address (the bridge answers with `Access-Control-Allow-Private-Network: true`). Whether newer Chrome versions still show a "local network access" permission prompt, and whether Safari lets an https page call `http://127.0.0.1`: not verified.

### 4.3 各平台要准备什么 / What to prepare per platform

"填进面板"一栏几乎总是同一件事:桥接地址加 token。下面的表由逐平台调研汇总,价格和配额以平台自己的页面为准;"禁止"和"不明确"的平台请当作只能批处理。

The "what you type into the panel" column is almost always the same thing: the bridge address plus the token. The tables below summarise the platform by platform research; prices and quotas follow the platforms' own pages; treat platforms marked "forbidden" or "unclear" as batch only.

#### 海外平台 / Abroad platforms

| 平台 / Platform | 要准备什么 / What you must prepare | 填进面板 / What you type into the panel | 连接方式 / Connection | 注意 / Caution |
|---|---|---|---|---|
| RunPod | 账号、预付余额(至少够 1 小时)、模板里暴露 HTTP 端口 8787 且 bridge 监听 0.0.0.0、含 KataGo 和 bridge 的镜像 / account, prepaid balance (at least one hour), a template exposing HTTP port 8787 with the bridge on 0.0.0.0, an image with KataGo and the bridge | `https://<POD_ID>-8787.proxy.runpod.net` 和 token / `https://<POD_ID>-8787.proxy.runpod.net` and the token | 官方 HTTP 代理(HTTPS) / vendor HTTP proxy (HTTPS) | 100 秒连接上限;零余额会停止甚至删除 Pod;社区云主机是第三方 / 100 s connection limit; zero balance stops (and may delete) the Pod; Community Cloud hosts are third parties |
| Vast.ai | 账号、充值(最低额未写)、SSH 公钥、SSH 启动模式的实例 / account, credit (minimum not stated), an SSH public key, an instance in SSH launch mode | `http://127.0.0.1:8787`(SSH `-L` 之后)和 token;或 portal 的 `https://<随机单词>.trycloudflare.com` / `http://127.0.0.1:8787` after SSH `-L`, plus the token; or the portal's `https://<random-words>.trycloudflare.com` | SSH 端口转发或 Instance Portal 隧道 / SSH port forward or Instance Portal tunnel | 主机是第三方,敏感用途选 Secure Cloud;停止后仍计存储费 / hosts are third parties, use Secure Cloud for sensitive use; storage is billed when stopped |
| Lambda Cloud | 账号、先加入工作区的 SSH 公钥、有货的单卡实例(A10/RTX 6000) / account, an SSH key added to the workspace first, an available single-GPU instance (A10/RTX 6000) | `http://127.0.0.1:8787`(SSH `-L` 之后)和 token / `http://127.0.0.1:8787` after SSH `-L`, plus the token | SSH 隧道(官方命令) / SSH tunnel (vendor command) | 没有 T4/L4/3090;新账户有数量上限;不要对 0.0.0.0/0 开放 8787 / no T4, L4 or 3090; new accounts have a limit; do not open 8787 to 0.0.0.0/0 |
| Paperspace (DigitalOcean) | 账号、银行卡、GPU Machine 加公网 IP、向支持确认可对外服务 / account, a card, a GPU Machine with a public IP, support confirmation that serving is allowed | `http://<IP>:8787` 和 token(端口策略未核实) / `http://<IP>:8787` and the token (port policy not verified) | 公网 IP 或 SSH(文档未给端口转发) / public IP or SSH (port forwarding not shown in docs) | 服务规则不明确;笔记本不能当服务器;H100 需审批 / serving rules unclear; notebooks must not be used as a server; H100 needs approval |
| Modal | 账号、付款方式、Modal 应用(启动 KataGo 和 bridge,监听 0.0.0.0) / account, a payment method, a Modal app that starts KataGo and the bridge on 0.0.0.0 | 部署后的 `https://...modal.run` 地址或隧道 `https://<随机>.modal.host` 地址,加 token / the deployed `https://...modal.run` address or the tunnel `https://<random>.modal.host` address, plus the token | 公网 HTTPS URL 或 `modal.forward` 隧道 / public HTTPS URL or `modal.forward` tunnel | Proxy Token 与 bridge 的 Authorization 冲突;空闲缩到零;条款限内部使用 / the Proxy Token clashes with the bridge's Authorization; scale-to-zero when idle; terms limit use to internal use |
| Hugging Face Jobs | 账号、预付余额(信用卡)、`hf` 命令行、Docker 镜像(KataGo 加 bridge,监听 0.0.0.0)、足够长的 `--timeout` / account, prepaid balance (credit card), the `hf` CLI, a Docker image (KataGo plus bridge on 0.0.0.0), a long enough `--timeout` | `https://<job_id>--8787.hf.jobs`(`--expose-public 8787`)和 token;或 SSH 转发后的 `http://127.0.0.1:8787` / `https://<job_id>--8787.hf.jobs` (`--expose-public 8787`) and the token; or `http://127.0.0.1:8787` after an SSH forward | 官方 Jobs 代理(HTTPS)或 SSH 转发 / vendor Jobs proxy (HTTPS) or SSH forward | 默认 30 分钟超时;公开端口只靠 bridge token;HF token 不要填进网页 / 30-minute default timeout; a public port is protected only by the bridge token; never type an HF token into the page |
| Lightning AI | 账号、真实手机号、积分、GPU Studio、API builder 插件 / account, a real phone number, credits, a GPU Studio, the API builder plugin | API builder 给出的地址(格式未核实)和 token / the address the API builder gives (format not verified) and the token | 官方 API builder 公网 API 或 SSH / vendor API builder public API or SSH | 条款未读到;原型用途;10 分钟无活动休眠 / terms not read; prototype use; sleeps after 10 minutes of inactivity |
| Google Colab | Google 账号 / a Google account | 无,不要用于服务 / nothing, do not use for serving | 无合规方式 / no compliant route | 禁止部署服务,仅批处理 / forbidden for serving, batch only |
| Kaggle Notebooks | Kaggle 账号 / a Kaggle account | 无 / nothing | 无入站路径 / no inbound route | 仅批处理,不要当服务器 / batch only, not a server |
| AWS EC2 GPU | AWS 账号,G 实例 vCPU 配额(至少 4),带 SSM 权限的实例配置文件,本机 AWS CLI 与 Session Manager 插件 / AWS account, G-instance vCPU quota (at least 4), instance profile with SSM permissions, local AWS CLI and Session Manager plugin | 桥接地址 `http://127.0.0.1:8787` 与令牌 / bridge address `http://127.0.0.1:8787` and the token | SSM 端口转发 / SSM port forwarding | 明文 http 的本机地址;用完要停机以免继续计费 / plain http on localhost; stop the instance when done to stop billing |
| Google Cloud GPU VM | 付费结算账号,GPU 配额,IAP 防火墙规则与 IAP-Secured Tunnel User 角色,本机 gcloud / a paid billing account, GPU quota, the IAP firewall rule and IAP-Secured Tunnel User role, local gcloud | 桥接地址 `http://localhost:8787` 与令牌 / bridge address `http://localhost:8787` and the token | IAP TCP 转发 / IAP TCP forwarding | 免费试用账号不能用 GPU;明文 http 的本机地址;空闲 1 小时断开 / trial accounts cannot use GPUs; plain http on localhost; disconnects after 1 h idle |
| Microsoft Azure NC T4 VM | Azure 账号,NCasT4_v3 vCPU 配额(至少 4),公网 IP 与 NSG 规则,或 Bastion Standard / an Azure account, NCasT4_v3 vCPU quota (at least 4), a public IP and NSG rule, or Bastion Standard | 桥接地址 `http://127.0.0.1:8787` 与令牌 / bridge address `http://127.0.0.1:8787` and the token | `ssh -L` 或 Bastion 隧道加 `ssh -L` / `ssh -L`, or Bastion tunnel plus `ssh -L` | NSG 只放行自己的 IP;不要直接隧道 8787;Bastion 按小时计费 / allow only your own IP in the NSG; do not tunnel 8787 directly; Bastion bills hourly |
| LRZ AI Systems | LRZ 账号、AI 启用的 LRZ 项目(master user 或 Servicedesk)、MWN 网络或 VPN、出口管制确认 / an LRZ account, an AI-enabled LRZ project (master user or Servicedesk), MWN network or VPN, export control acknowledgement | 未核实:文档没有给出桥接地址形式 / not verified: the docs give no bridge URL form | 终端 SSH 加 Slurm;网页门户 https://login.ai.lrz.de;计算节点端口转发未文档化 / terminal SSH plus Slurm; web portal https://login.ai.lrz.de; port forwarding to compute nodes undocumented | 先问 LRZ Servicedesk 能否跑常驻服务;系统不主要用于开发,空闲要少 / ask the LRZ Servicedesk whether a resident service is acceptable; the system is not mainly for development, keep idle time low |
| BayernKI | 巴伐利亚州立高校的研究身份(通常经研究组或项目负责人)、BayernKI 申请表、所选中心(LRZ 或 NHR@FAU)的账号 / research status at a state-funded Bavarian university (usually via the research group or PI), the BayernKI application form, an account at the chosen center (LRZ or NHR@FAU) | 未核实 / not verified | 取决于中心;LRZ 见上 / depends on the center; LRZ see above | 每组一份申请;交互服务是否允许未写明,先问中心 / one application per group; interactive services are not addressed, ask the center first |

#### 国内平台 / Platforms in China

| 平台 / Platform | 要准备什么 / What you must prepare | 填进面板 / What you type into the panel | 连接方式 / Connection | 注意 / Caution |
|---|---|---|---|---|
| AutoDL | 账号(实名状态自行确认)、一台已开机的实例、本机 ssh 客户端 / an account (confirm real-name yourself), a powered-on instance, a local ssh client | 桥接地址 `http://127.0.0.1:8787` 和令牌 / bridge address `http://127.0.0.1:8787` and token | SSH 隧道 `ssh -CNg -L 8787:127.0.0.1:8787 root@<host> -p <port>` / SSH tunnel with the same command | 公网自定义服务只给企业认证、仅限科研、禁止分享链接;个人只用隧道 / the public custom service is enterprise only, research only, no link sharing; individuals use the tunnel only |
| 恒源云 Gpushare | 账号、一台已开机的实例、桥接改为监听 0.0.0.0:8080 / an account, a powered-on instance, the bridge set to listen on 0.0.0.0:8080 | 控制台"自定义服务"显示的地址和令牌(地址格式文档未写) / the address shown by the console Custom Service entry and the token (shape not documented) | 厂商自定义服务公网入口 / vendor public Custom Service entry | 协议是 http 还是 https 未核实;https 页面不能调用 http 地址 / scheme unverified; an https page cannot call an http address |
| OpenBayes | 已实名的账号、创建容器时添加端口映射(容器端口 8787) / a real-name-verified account, a port mapping (container port 8787) added when creating the container | `https://{user}-{port_name}.{domain}` 形式的地址和令牌 / an address like `https://{user}-{port_name}.{domain}` and the token | 厂商端口映射(https);或 SSH 隧道 + `http://127.0.0.1:8787` / vendor port mapping (https); or SSH tunnel plus `http://127.0.0.1:8787` | 端口映射需实名且无平台认证,令牌要足够长;当前只列 RTX 5090 / port mapping needs real-name and has no platform auth, use a long token; only RTX 5090 is listed now |
| 趋动云 virtaicloud.com | 不建议使用 / not recommended | 无 / none | 未核实 / not verified | 官网公告称开发、训练、推理功能停服(正文 403,未读) / the site notice says development, training and inference are being discontinued (body 403, not read) |
| 阿里云 PAI-DSW / Alibaba Cloud PAI-DSW | 阿里云账号、DSW 实例(VPC、EIP、NAT 网关、安全组) / an Alibaba Cloud account, a DSW instance (VPC, EIP, NAT gateway, security group) | `http://<EIP>:<端口/port>` 和令牌;或 SSH 转发后 `http://127.0.0.1:8787` / `http://<EIP>:<port>` and token; or `http://127.0.0.1:8787` after an SSH forward | 厂商自定义服务(明文 http)或 SSH 直连 / vendor custom service (plain http) or SSH direct connection | 仅开发测试用途;EIP 与 NAT 网关单独计费;https 页面不能调用 EIP 的 http 地址 / development and testing only; EIP and NAT billed separately; an https page cannot call the EIP's http address |
| 阿里云 GPU ECS / Alibaba Cloud GPU ECS | 实名认证的账号(内地地域)、带公网 IP 的 GPU 实例、安全组放通 22、本机 ssh 客户端 / a real-name-verified account (mainland regions), a GPU instance with a public IP, port 22 in the security group, a local ssh client | 桥接地址 `http://127.0.0.1:8787` 和令牌 / bridge address `http://127.0.0.1:8787` and token | `ssh -L 8787:127.0.0.1:8787 root@<公网IP/public IP>` | 不要为此绑定域名;直接开公网端口只能得到明文 http 且可能触及备案规则 / do not bind a domain for this; a public port gives only plain http and may touch the filing rules |
| 腾讯云 GPU CVM / Tencent Cloud GPU CVM | 实名认证的账号、带公网 IP 的 GPU 实例、安全组放通 22 / a real-name-verified account, a GPU instance with a public IP, port 22 in the security group | `http://127.0.0.1:8787` 和令牌 / `http://127.0.0.1:8787` and token | `ssh -L 8787:127.0.0.1:8787 <user>@<公网IP/public IP>` | 不要把域名解析到该服务器;GPU 价格未核实 / do not point a domain at the server; GPU price not verified |
| 腾讯云 HAI / Tencent Cloud HAI | 实名认证的账号、一台 HAI 实例;先确认有 SSH / a real-name-verified account, an HAI instance; confirm SSH exists first | 若有 SSH:`http://127.0.0.1:8787` 和令牌 / if SSH exists: `http://127.0.0.1:8787` and token | SSH 转发(未核实)或端口规则放通后的 http 公网地址 / SSH forward (not verified) or an http public address after a port rule | 对自建长期服务不明确;未核实 root SSH / unclear for self-built long-lived services; root SSH not verified |
| 华为云 ModelArts Notebook / Huawei Cloud ModelArts Notebook | 不建议 / not recommended | 无 / none | SSH 仅供本地 IDE / SSH for a local IDE only | 官方限制:不支持开放端口对外提供服务,仅开发调测 / vendor constraint: no opening ports for external services, development and debugging only |
| 华为云 GPU ECS / Huawei Cloud GPU ECS | 实名认证的账号、G6 或 Pi2 实例、EIP、安全组放通 22 / a real-name-verified account, a G6 or Pi2 instance, an EIP, port 22 in the security group | `http://127.0.0.1:8787` 和令牌 / `http://127.0.0.1:8787` and token | `ssh -L 8787:127.0.0.1:8787 root@<EIP>` | 华为备案 FAQ 对内地节点最严格(称 IP 访问也要备案);不要开公网端口 / Huawei's filing FAQ is the strictest (says IP access needs filing too); do not open a public port |
| 百度 AI Studio / Baidu AI Studio | 百度账号; 常驻服务需 A 币余额并使用付费"项目服务部署" / Baidu account; a standing service needs an A-coin balance and the paid project service deployment | 桥地址(平台生成的服务 URL, 格式未核实)和令牌 / bridge address (platform-generated service URL, format not verified) and token | 平台公网 API 地址, 端口 8080, 带百度 Access Token / platform public API address, port 8080, with the Baidu Access Token | 免费笔记本不明确, 关浏览器 10 分钟后中止, 只做批量分析; Access Token 与桥令牌是否冲突未核实 / free notebook is unclear and stops 10 minutes after the browser closes, batch analysis only; token collision with the bridge token not verified |
| 天翼云 GPU 云主机 / Ctyun GPU cloud host | 实名账号, 余额大于 100 元, PI2(T4)或 PI7(A10)云主机加弹性 IP, 安全组放行 22 / verified account, balance above 100 CNY, a PI2 (T4) or PI7 (A10) host with an elastic IP, security group open on 22 | `http://127.0.0.1:8787` 和令牌 / `http://127.0.0.1:8787` and the token | `ssh -L 8787:127.0.0.1:8787 用户@弹性IP` / `ssh -L 8787:127.0.0.1:8787 user@elastic-IP` | 不要直接放行 8787 给 https 页面用(只有 http); 80/8080/443/8443 公网开放需备案; 用完要关机并确认计费停止 / do not open 8787 for an https page (http only); 80/8080/443/8443 need ICP filing for public use; shut down when done and check that billing stops |
| 国家超算互联网 SCNet / SCNet | 实名认证账号(身份证 + 人脸), 已充值的现金账户, 一个 Notebook 实例 / real-name verified account (ID card + face), a topped-up cash account, one Notebook instance | 平台给出的自定义服务地址(格式未核实)和令牌;若走 SSH 转发则 `http://127.0.0.1:8787` / the custom-service address the platform shows (format not verified) and the token; with an SSH forward, `http://127.0.0.1:8787` | Notebook "访问自定义服务"(最多三个转发端口); HPC 用 salloc + 登录节点 / Notebook "access custom service" (at most three forwarded ports); HPC via salloc + the login node | 加速卡多为国产卡, KataGo 兼容性未核实; 计算节点不能上网; 禁止反向代理类服务 / accelerators appear to be domestic cards, KataGo compatibility not verified; compute nodes have no internet; reverse-proxy-type services are prohibited |
| 天河国家超算中心 / Tianhe national supercomputing centers | 单位身份、申请表(负责人签字加公章)、机时合同 / institutional affiliation, the application form (signature plus unit seal), a machine-time contract | `http://127.0.0.1:8787` 和令牌(仅在中心书面同意端口转发后) / `http://127.0.0.1:8787` and the token (only after the center agrees in writing to port forwarding) | 登录节点 SSH + 作业分配, 端口转发规则未核实 / SSH to a login node + a job allocation; port-forwarding rules not verified | 申请制, 非自助; 现行规则未读到; 不要在登录节点跑服务; 按批处理对待 / by application, not self-service; current rules not read; no servers on login nodes; treat as batch only |
| 鹏城云脑 / 启智 OpenI / Peng Cheng Cloud Brain and OpenI | 启智账号和算力积分; 鹏城云脑需另行提交资源申请 / an OpenI account and compute points; Cloud Brain needs a separate resource application | 不适用, 未发现可核实的对外端口; 不要填隧道地址 / not applicable, no verified external port; do not enter a tunnel address | 仅任务页 Jupyter 网页 / Jupyter web page on the task page only | 禁止内网穿透工具; 只做批量分析; 官方文档读取时在维护 / intranet-penetration tools are prohibited; batch analysis only; the official docs were under maintenance when read |
| 通用 Slurm 集群 (通用) / Generic Slurm cluster (GENERIC) | 该集群的账号和 GPU 额度, 能 ssh 到计算节点 / an account and GPU allocation on that cluster, and the ability to ssh to compute nodes | `http://127.0.0.1:8787` 和令牌(SSH 转发之后) / `http://127.0.0.1:8787` and the token (after the SSH forward) | `salloc` + `ssh -J 登录节点 -L 8787:127.0.0.1:8787 计算节点` / `salloc` + `ssh -J login-node -L 8787:127.0.0.1:8787 compute-node` | 通用说明, 各站点规则不同; 登录节点不得跑桥; 用完 exit 释放分配 / generic, rules differ per site; never run the bridge on a login node; exit to release the allocation |

### 4.4 逐平台说明 / Platform notes

每个平台的"服务器用途"一行只代表该平台自己的条款或文档的说法;页面没写的写"不明确"或"未核实"。

The "serving allowed" row of each platform reports only what that platform's own terms or docs say; what the pages do not state is marked "unclear" or "not verified".

#### 海外 / Abroad

#### RunPod 平台 / RunPod

RunPod 以容器 Pod 的形式出租 GPU,分 Secure Cloud(T3/T4 数据中心)和 Community Cloud(经审核的个人算力提供者)。价格页(2026-11-01 读取)列出 RTX 3090 约 0.22 到 0.50 美元/小时、RTX 4090 约 0.34 到 0.89 美元/小时、L4 约 0.44 到 0.59 美元/小时(前者为社区云、后者为安全云;工具读取时两列的对应关系不够清楚,以部署界面为准),T4 和 A4000 不在 Pod 价格表里。官方文档明确描述了在 Pod 上暴露 HTTP 端口(最多 10 个)和 TCP 端口,服务条款里没有禁止运行服务的条款(第 2 节要求用户自己负责应用和安全配置,第 12 节允许因过度占用系统资源而暂停账户),所以判定为允许。浏览器连接的官方方式是 HTTP 代理 `https://[POD_ID]-[端口].proxy.runpod.net`,只提供 HTTPS、服务必须监听 0.0.0.0、单次连接最长 100 秒(超时返回 524);另有 Direct TCP(公网 IP 加映射端口,无 TLS,Pod 重置后端口会变)和 SSH。费用按秒计费、无出入流量费,账户是预付余额制,余额至少要够所选配置运行 1 小时,文档说约 10 美元即可开始试用,预付卡单笔最低 100 美元,加密货币付款前要先完成 KYC。要在自己账户里确认:所选 GPU 和云类型的实际价格与库存、模板里能否填写 HTTP 端口 8787、社区云主机是否可信(安全页说条款禁止主机查看 Pod 数据,但社区云的细节没有读到)。

RunPod rents GPUs as container Pods, in Secure Cloud (T3/T4 data centers) and Community Cloud (vetted individual compute providers). The pricing page (read on 2026-11-01) lists about 0.22 to 0.50 USD/hour for an RTX 3090, about 0.34 to 0.89 USD/hour for an RTX 4090 and about 0.44 to 0.59 USD/hour for an L4 (community price first, secure price second; the tool's reading of which column is which was not fully clear, so trust the deploy screen), and T4 and A4000 are not in the Pod price table. The docs explicitly describe exposing HTTP ports (up to 10) and TCP ports on a Pod, and the Terms of Service contain no clause that forbids running a service (Section 2 makes you responsible for your own software and security, Section 12 allows suspension for unduly stressing system resources), so it is classed as allowed. The documented browser route is the HTTP proxy `https://[POD_ID]-[PORT].proxy.runpod.net`: HTTPS only, the service must bind 0.0.0.0, and a connection lives at most 100 seconds (longer returns a 524); there is also Direct TCP (public IP plus a mapped port, no TLS, the port changes when the Pod resets) and SSH. Billing is per second with no ingress or egress fees; the account is prepaid and the balance must cover at least one hour of the chosen configuration, the docs say about 10 USD is enough to start evaluating, prepaid cards need at least 100 USD per transaction, and crypto payment requires KYC first. Confirm in your own account: the real price and stock for the GPU and cloud type you pick, that the template lets you enter HTTP port 8787, and how far to trust Community Cloud hosts (the security page says the terms forbid hosts from inspecting Pod data, but I did not read the Community Cloud details).

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed. 来源 / source: https://docs.runpod.io/pods/configuration/expose-ports (HTTP and TCP exposure documented); https://www.runpod.io/legal/terms-of-service (no ban on services found; Sections 2, 6, 9, 12) |
| 连接方式 / How to connect | 官方 HTTP 代理 `https://[POD_ID]-8787.proxy.runpod.net`(HTTPS,服务需监听 0.0.0.0,100 秒上限);或 Direct TCP 公网 IP:映射端口(http,Connect 菜单里查看);或 SSH(`ssh.runpod.io` 代理式基础 SSH,或经 TCP 22 的完整 SSH,文档页没有给出 `-L` 示例)。 / Official HTTP proxy `https://[POD_ID]-8787.proxy.runpod.net` (HTTPS, service must bind 0.0.0.0, 100 s limit); or Direct TCP public IP:mapped port (http, shown in the Connect menu); or SSH (proxied basic SSH via `ssh.runpod.io`, or full SSH over TCP 22; the doc page shows no `-L` example). Docs: https://docs.runpod.io/pods/configuration/expose-ports , https://docs.runpod.io/pods/configuration/use-ssh |
| 费用 / Cost | 约 0.22 到 0.89 美元/小时(RTX 3090/4090,社区云到安全云),L4 约 0.44 到 0.59 美元/小时,按秒计费,无出入流量费;容器盘约 0.10 美元/GB/月。 / About 0.22 to 0.89 USD/hour (RTX 3090/4090, community to secure), L4 about 0.44 to 0.59 USD/hour, per-second billing, no ingress/egress fees; container disk about 0.10 USD/GB/month (read on 2026-11-01). https://www.runpod.io/pricing , https://docs.runpod.io/pods/pricing , https://docs.runpod.io/accounts-billing/billing.md |

#### Vast.ai 平台 / Vast.ai

Vast.ai 是第三方主机的 GPU 市场,实例是带独占 GPU 的 Docker 容器,启动模式有 SSH、Jupyter 和自定义入口;价格由主机按供需自定,分按需、可中断(通常便宜 50% 以上)和预留,按秒计费,存储费在实例存在期间一直计(停止后也计)。我没能读到各 GPU 的具体当前价格(价格页的实时表格无法读取,3090 和 4090 的价格页显示 "No current offers"),所以价格一栏写未核实。文档详细描述了开放端口(Docker 选项 `-p`)、公网 IP 加随机映射端口、SSH 端口转发和 Instance Portal 隧道,服务条款里没有找到禁止对外提供服务的条款(只禁止用信用卡充值时挖矿等),所以判定为允许。连接方式有三种:SSH 加 `-L`(官方示例 `ssh -p <端口> root@<IP> -L 8080:localhost:8080`,得到 `http://127.0.0.1:8787`,必须先在账户里加 SSH 公钥);公网 IP:映射端口(http,"IP Port Info" 里查看);以及 Instance Portal 创建的 Cloudflare 快速隧道 `https://<四个随机单词>.trycloudflare.com`(https,链接公网可达,启动链接带 token)。账户方面要先充值再开实例,最低充值额没有写;文档说需要验证过的信用卡和邮箱,也支持加密货币,不支持 PayPal,没有提到 KYC;注册年龄:未满 13 岁不能用,未满 18 岁需监护人同意。关于主机可信度:条款没有说明主机能否访问你的数据,安全 FAQ 说个人主机的安全措施可能没那么正式,敏感负载建议用 "Secure Cloud" 过滤、数据先加密、不要把凭据放在实例上,而 bridge 只处理公开的棋谱分析,风险相对小,但 token 仍然不要复用。

Vast.ai is a marketplace of third-party hosts; an instance is a Docker container with exclusive GPU access, launched in SSH, Jupyter or custom-entrypoint mode. Hosts set their own prices by supply and demand (on-demand, interruptible usually 50% or more cheaper, and reserved), billing is per second, and storage is billed for as long as the instance exists, including while stopped. I could not read current per-GPU prices (the live price grid is not readable; the RTX 3090 and RTX 4090 price pages showed "No current offers"), so the price is marked not verified. The docs describe opening ports (Docker option `-p`), a shared public IP with random mapped ports, SSH port forwarding and Instance Portal tunnels, and the Terms contain no ban on offering a service (they only ban things like mining when you pay by card), so it is classed as allowed. There are three ways in: SSH with `-L` (vendor example `ssh -p <port> root@<ip> -L 8080:localhost:8080`, giving `http://127.0.0.1:8787` for the bridge; an SSH public key must be added to the account first); public IP:mapped port (http, shown in the "IP Port Info" pop-up); and a Cloudflare quick tunnel created by the Instance Portal, `https://<four-random-words>.trycloudflare.com` (https, reachable from the internet, launch links carry a token). You must add credit before starting an instance and no minimum deposit is stated; the docs mention a verified credit card and email, crypto payment, no PayPal, and no KYC; users under 13 may not register and users under 18 need a guardian's permission. On host trust: the Terms do not say whether hosts can see your data, and the security FAQ says individual hosts may have less formal security and recommends the "Secure Cloud" filter, encrypting data and keeping credentials off instances; the bridge only analyses public game records, so the risk is small, but do not reuse the token anywhere else.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed. 来源 / source: https://docs.vast.ai/guides/instances/connect/networking.md (port opening documented); https://docs.vast.ai/guides/instances/connect/instance-portal.md (tunnels documented); https://vast.ai/terms (no ban on services found, only a summary was read) |
| 连接方式 / How to connect | SSH `-L`(`ssh -p <port> root@<ip> -L 8787:localhost:8787`,用 `http://127.0.0.1:8787`);或 Docker 选项 `-p 8787:8787` 后用 IP Port Info 里的 `http://<IP>:<映射端口>`(http);或 Instance Portal 的 Cloudflare 隧道 `https://<随机单词>.trycloudflare.com`(https,需要 Vast.ai 提供的镜像带的 portal,"Tunnels" 页可为后启动的应用建隧道,输入 `http://localhost:<port>`)。 / SSH `-L` (`ssh -p <port> root@<ip> -L 8787:localhost:8787`, use `http://127.0.0.1:8787`); or Docker option `-p 8787:8787` then `http://<IP>:<mapped port>` from IP Port Info (http); or the Instance Portal Cloudflare tunnel `https://<random-words>.trycloudflare.com` (https; the portal ships with Vast.ai images, and its "Tunnels" page can create a tunnel for an app started later by entering `http://localhost:<port>`). Docs: https://docs.vast.ai/documentation/instances/connect/ssh , https://docs.vast.ai/guides/instances/connect/networking.md , https://docs.vast.ai/guides/instances/connect/instance-portal.md |
| 费用 / Cost | 未核实 / not verified(市场价,由主机设定;按秒计费;停止的实例仍计存储费;带宽按字节计费)。 / Not verified (market prices set by hosts; per-second billing; stopped instances still pay storage; bandwidth is billed per byte). https://docs.vast.ai/guides/instances/pricing.md , https://vast.ai/pricing (read on 2026-11-01) |

#### Lambda (Lambda Cloud) 平台 / Lambda (Lambda Cloud)

Lambda Cloud 提供按需 GPU 虚拟机,单卡可选的有 Quadro RTX 6000 24GB(约 0.69 美元/小时)、A6000 48GB(约 1.09 美元/小时)、A10 24GB(约 1.29 美元/小时)、A100 40GB(约 1.99 美元/小时)等,没有 T4、L4 或 3090/4090;按分钟计费,无出站流量费,实例通过网页、API 或命令行自助启动,先到先得(价格见 lambda.ai/service/gpu-cloud,2026-11-01 读取,不含税)。官方文档的防火墙页直接说明如何放行自定义 TCP 端口(例如 8787),条款没有禁止提供服务,只禁止挖矿、扫描、DoS,以及开放代理、开放邮件中继等,所以判定为允许(云条款第 2(c) 条引用的 Platform Guidelines 没有读到)。默认只放行 TCP 22 和 ICMP;官方的 SSH 隧道写法是 `ssh -i <密钥> -L <本地端口>:127.0.0.1:<远端端口> ubuntu@<实例IP>`,不用在防火墙里再开端口,得到 `http://127.0.0.1:8787`;如果直接放行 8787,只有 `http://<IP>:8787`,而且文档建议把来源限制到你自己的 IP,不要用 0.0.0.0/0。启动实例前必须先把 SSH 公钥加到工作区;新账户有实例数量上限,按付款情况自动提高,按需实例每周开发票;信用卡或预付要求在已读页面里没有写明。要确认:所需 GPU 在你的区域是否有货、新账户配额、付款方式要求。

Lambda Cloud offers on-demand GPU virtual machines; the single-GPU options include Quadro RTX 6000 24 GB (about 0.69 USD/hour), A6000 48 GB (about 1.09 USD/hour), A10 24 GB (about 1.29 USD/hour) and A100 40 GB (about 1.99 USD/hour), and there is no T4, L4 or 3090/4090; billing is per minute with no egress fees, and instances are self-serve and first come first served from the web UI, API or CLI (prices from lambda.ai/service/gpu-cloud, read on 2026-11-01, before tax). The docs' firewall page directly explains how to open a custom TCP port (for example 8787), and the terms do not forbid offering a service (they ban mining, scanning, DoS, open proxies, open mail relays and similar), so it is classed as allowed (the Platform Guidelines that Cloud Terms Section 2(c) points to were not read). By default only TCP 22 and ICMP are open; the documented SSH tunnel is `ssh -i <key> -L <local port>:127.0.0.1:<remote port> ubuntu@<instance IP>`, which needs no extra firewall port and gives `http://127.0.0.1:8787`; if you open 8787 in the firewall instead you only get `http://<IP>:8787`, and the docs advise restricting the source to your own IP rather than 0.0.0.0/0. An SSH key must be added to the workspace before launch; new accounts have an instance limit that rises as you pay invoices, and on-demand usage is invoiced weekly; a card or prepayment requirement is not stated on the pages I read. Confirm: stock for the GPU in your region, your new-account quota, and the payment method rules.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed. 来源 / source: https://docs.lambda.ai/public-cloud/firewalls/ (how to open Custom TCP 8787); https://lambda.ai/legal/terms-of-service (acceptable use: mining, scanning, DoS, open proxy banned; no ban on services; Platform Guidelines not read) |
| 连接方式 / How to connect | SSH 隧道 `ssh -i '<KEY>' -L 8787:127.0.0.1:8787 ubuntu@<IP>` 后用 `http://127.0.0.1:8787`(推荐);或防火墙放行自定义 TCP 8787,用 `http://<IP>:8787`(只有 http,来源应限制为自己的 IP,规则要在启动实例时附加)。 / SSH tunnel `ssh -i '<KEY>' -L 8787:127.0.0.1:8787 ubuntu@<IP>` then `http://127.0.0.1:8787` (preferred); or open Custom TCP 8787 in the firewall and use `http://<IP>:8787` (http only, restrict the source to your own IP, rulesets must be attached at launch). Docs: https://docs.lambda.ai/public-cloud/on-demand/connecting-instance/ , https://docs.lambda.ai/public-cloud/firewalls/ |
| 费用 / Cost | 约 0.69 到 1.29 美元/小时(Quadro RTX 6000 到 A10 单卡),按分钟计费,无出站流量费。 / About 0.69 to 1.29 USD/hour (single Quadro RTX 6000 to A10), billed per minute, no egress fees (read on 2026-11-01). https://lambda.ai/service/gpu-cloud , https://docs.lambda.ai/public-cloud/billing/ |

#### Paperspace 云平台(DigitalOcean 旗下) / Paperspace (DigitalOcean)

Paperspace 现在属于 DigitalOcean;DigitalOcean 文档里仍列出 Notebooks、Deployments、Machines(Workflows 为私有),paperspace.com 首页仍以 "Gradient" 名义列出 Notebooks、Machines、Deployments,所以老的 Gradient 笔记本产品还在,但旧的 Gradient 和 Core API 已在 2024 年 5 月停用,Windows 模板对新用户停用,NVIDIA GRID 机型已退役。Machines(原 Core 虚拟机)的 GPU 有 A4000 16GB(约 0.76 美元/小时)、A5000 24GB(约 1.38 美元/小时)、A6000、V100、A100、H100 等(H100 需审批),按小时计费、关机后只收存储和公网 IP;免费笔记本 GPU 是 M4000(仅限私有工作区的 Notebooks)。是否允许当服务器:不明确。机器可以分配公网 IP(文档说没有公网 IP 的机器无法从互联网访问),但我读到的文档没有讲端口或防火墙规则,笔记本也没有端口暴露的说明,Paperspace 服务条款(2023-09-19 版)和 DigitalOcean 服务条款都把可接受使用规则指向另一份 AUP,我没有读到。连接方式:Machines 在控制台里复制 SSH 命令(文档没有给出命令格式,也没有提到端口转发),公网 IP 加端口只能是 http;注册要银行卡(DigitalOcean 条款要求有效付款方式,满 18 岁),创建 Core 机器时可能被要求验证账户,新账户有机器数量限制。结论:这不是首选,如要用,先向 Paperspace 支持确认允许对外提供服务,并在自己账户里确认公网 IP 的端口策略。

Paperspace is now part of DigitalOcean. The DigitalOcean docs still list Notebooks, Deployments and Machines (Workflows is private), and the paperspace.com home page still lists Notebooks, Machines and Deployments under the "Gradient" name, so the old Gradient notebook product is still there; however the legacy Gradient and Core APIs were deprecated in May 2024, Windows templates are closed to new users and the NVIDIA GRID machine types are retired. Machines (the former Core VMs) offer GPUs such as A4000 16 GB (about 0.76 USD/hour), A5000 24 GB (about 1.38 USD/hour), A6000, V100, A100 and H100 (H100 needs approval), billed hourly while powered on, with storage and public IP still billed while off; the free notebook GPU is an M4000 (Notebooks in private workspaces only). Whether serving is allowed: unclear. A machine can be given a public IP (the docs say a machine without one is not reachable from the internet), but the pages I read say nothing about ports or firewall rules, notebooks have no documented port exposure, and both the Paperspace Terms (version 9/19/2023) and the DigitalOcean Terms point to a separate Acceptable Use Policy that I could not read. Connection: for Machines you copy an SSH command from the console (the docs do not show the command format and do not mention port forwarding), and a public IP plus port can only be http; signing up needs a card (the DigitalOcean terms require a valid payment method and age 18), you may be asked to verify the account when creating Core machines, and new accounts have machine limits. Verdict: not a first choice; if you want it, ask Paperspace support whether serving is allowed and confirm the port policy of the public IP in your own account.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 不明确 / unclear. 来源 / source: https://docs.digitalocean.com/products/paperspace/machines/how-to/manage-public-ips/ (public IP makes a machine reachable; ports and firewall not covered); https://www.paperspace.com/terms-of-service (points to a separate AUP, not read); https://www.digitalocean.com/legal/terms-of-service-agreement (Section 5 points to AUP, not read) |
| 连接方式 / How to connect | 控制台里复制 SSH 命令(需要先 START 机器);公网 IP(静态或动态)。`ssh -L` 是普通 OpenSSH 功能,但 Paperspace 页面没有给出,需自行确认。 / Copy the SSH command from the console (the machine must be started first); public IP (static or dynamic). `ssh -L` is a plain OpenSSH feature but the Paperspace pages do not show it, so confirm yourself. Docs: https://docs.digitalocean.com/products/paperspace/machines/how-to/connect/ , https://docs.digitalocean.com/products/paperspace/machines/how-to/manage-public-ips/ |
| 费用 / Cost | A4000 约 0.76 美元/小时,A5000 约 1.38 美元/小时,A6000 约 1.89 美元/小时;公网 IP 约 0.0045 美元/小时(每月上限约 3 美元);Free 计划含 M4000 免费笔记本 GPU。 / A4000 about 0.76 USD/hour, A5000 about 1.38 USD/hour, A6000 about 1.89 USD/hour; public IP about 0.0045 USD/hour (capped at about 3 USD/month); the Free plan includes an M4000 notebook GPU (read on 2026-11-01). https://docs.digitalocean.com/products/paperspace/pricing/ |

#### Modal 平台 / Modal

Modal 是无服务器平台,GPU 通过 `gpu=` 参数申请,可选 T4(约 0.59 美元/小时)、L4(约 0.80)、A10(约 1.10)、L40S、A100、H100 等(小时价是我用每秒价乘 3600 算出的,2026-11-01 读取),按秒计费;Starter 计划每月含约 30 美元免费额度,使用 GPU 必须在账户上绑定付款方式。长时间运行的带 GPU 容器和 Web 服务是文档支持的用法:`@app.server()`(监听 0.0.0.0,可带 GPU,部署后有公网 URL)、`@modal.web_server(port)`,以及 `modal.forward(8787)` 隧道(TLS 由 Modal 终止,URL 形如 `https://<随机>.modal.host`,随 `with` 代码块存在,函数超时最长 24 小时,隧道不额外收费)。条款方面,Modal 条款禁止挖矿、P2P、通用文件托管、转售,并限定为客户内部使用、不得让第三方直接访问(第 1.1、1.3、1.5 条),所以只给自己用的 bridge 属于允许范围,但"内部业务使用"的措辞对个人是否适用没有进一步说明。需要注意:Servers 默认要求 Proxy Token(放在 `Authorization: Bearer ...` 或 `Modal-Key`/`Modal-Secret` 头里),会与 bridge 自己的 `Authorization` token 冲突,要用 `unauthenticated=True`(或让 Web Function 保持公开)并只靠 bridge 的 token;容器空闲会缩到零,要用 `min_containers` 保持常驻(会持续计费),否则每次冷启动都要重新加载 KataGo 模型;Web 请求超过 150 秒会走 303 重定向,而重定向不适用于 CORS 请求。

Modal is a serverless platform; GPUs are requested with the `gpu=` argument and include T4 (about 0.59 USD/hour), L4 (about 0.80), A10 (about 1.10), L40S, A100 and H100 (hourly figures are my own per-second price times 3600, read on 2026-11-01), billed per second; the Starter plan includes about 30 USD of free compute per month, and using a GPU requires a payment method on file. A long-lived GPU container with a web server is a documented use: `@app.server()` (binds 0.0.0.0, can use GPUs, gets a public URL once deployed), `@modal.web_server(port)`, and `modal.forward(8787)` tunnels (TLS is terminated by Modal, the URL looks like `https://<random>.modal.host`, it lives for the `with` block, the function timeout can be up to 24 hours, and tunnels cost nothing extra). On terms, Modal forbids mining, peer-to-peer, general file hosting and resale, and limits use to the customer's internal use with no direct third-party access (Sections 1.1, 1.3, 1.5), so a bridge for your own use is within bounds, although the "internal business" wording is not explained for individuals. Watch out: Servers require a Proxy Token by default (sent as `Authorization: Bearer ...` or `Modal-Key`/`Modal-Secret` headers), which collides with the bridge's own `Authorization` token, so use `unauthenticated=True` (or keep the Web Function public) and rely on the bridge token alone; idle containers scale to zero, so use `min_containers` to keep one running (billed continuously) or accept a KataGo model reload on every cold start; web requests longer than 150 seconds are redirected with a 303, and redirects do not work with CORS requests.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed (仅限自己使用 / own use only). 来源 / source: https://modal.com/docs/guide/servers.md , https://modal.com/docs/guide/webhooks , https://modal.com/docs/guide/tunnels (all document serving); https://modal.com/legal/terms (Sections 1.1, 1.3, 1.5: internal use, no third-party access, no mining or file hosting) |
| 连接方式 / How to connect | 已部署的 Web Function 的 HTTPS 地址 `https://<workspace>--<app>-<function>.modal.run`;`@app.server()` 的地址用 `modal.Server.get_url()` 取得(格式文档未给出);或 `modal.forward(8787)` 返回的 `tunnel.url`(`https://<随机>.modal.host`)。 / The HTTPS address of a deployed Web Function `https://<workspace>--<app>-<function>.modal.run`; for `@app.server()` the address comes from `modal.Server.get_url()` (format not given in the docs); or the `tunnel.url` returned by `modal.forward(8787)` (`https://<random>.modal.host`). Docs: https://modal.com/docs/guide/webhooks , https://modal.com/docs/guide/tunnels , https://modal.com/docs/guide/webhook-proxy-auth |
| 费用 / Cost | T4 约 0.59、L4 约 0.80、A10 约 1.10 美元/小时(按秒计费);Starter 计划每月含约 30 美元额度;GPU 需绑定付款方式。 / T4 about 0.59, L4 about 0.80, A10 about 1.10 USD/hour (per-second billing); the Starter plan includes about 30 USD/month of compute; a GPU needs a payment method on file (read on 2026-11-01). https://modal.com/pricing , https://modal.com/docs/guide/gpu , https://modal.com/docs/guide/billing.md |

#### Hugging Face Jobs 平台 / Hugging Face Jobs

先说结论:Jobs 的设计用途是批处理(一条命令加一个 Docker 镜像加一个硬件规格,默认 30 分钟超时),但是现行文档确实提供了让 Job 暴露端口的功能,所以它能当一个临时服务器用,并不是"只能批处理"。GPU 规格有 T4 small(约 0.40 美元/小时)、T4 medium(约 0.60)、L4(约 0.80)、A10G small(约 1.00)、A100 large(约 2.50)等,按分钟计费,只在启动和运行时计费,暴露端口另加约 0.01 美元/小时(2026-11-01 读取)。官方连接方式有两种:一是 Jobs 代理 `https://<job_id>--<端口>.hf.jobs`(HTTPS),默认要求带有该命名空间读权限的 HF token(放在 `Authorization: Bearer` 头里),用 `--expose-public 8787` 则不要 HF 认证、任何人拿到 URL 都能访问;二是给 Job 加 `--ssh`,文档给出 `ssh -L 6006:localhost:6006 <job_id>@ssh.hf.jobs` 形式的端口转发(Job 需带 SSH 公钥并有写权限)。因为私有暴露要用 `Authorization` 头放 HF token,会与 bridge 的 token 头冲突,浏览器的跨域预检请求也不会带它(代理如何处理未核实),所以实际可行的是 `--expose-public` 加 bridge 自己的 token,或者 SSH 转发;不要把 HF token 填进网页。账号要求:任何有正余额的用户或组织都能用 Jobs,不一定要 PRO;钱要预付并绑信用卡(文档说不支持印度发行的信用卡);超时用 `--timeout` 设置(文档示例到 1 天,最大值没有写)。条款:Hugging Face 服务条款本身没有谈计算服务,补充条款和内容政策我没有读到,所以判定为"按文档允许,补充条款未核实"。另外还有实验性的 Sandboxes(建在 Jobs 上,可选 GPU,用 `proxy_url_for` 访问内部服务,但需要带认证头,最长存活 24 小时)。

The short answer: Jobs are designed for batch work (one command, one Docker image, one hardware flavor, a 30-minute default timeout), but the current docs do provide a way for a Job to expose a port, so it can act as a temporary server and is not "batch only". GPU flavors include T4 small (about 0.40 USD/hour), T4 medium (about 0.60), L4 (about 0.80), A10G small (about 1.00) and A100 large (about 2.50), billed per minute and only while starting or running, with exposed ports adding about 0.01 USD/hour (read on 2026-11-01). The documented ways in are two: the Jobs proxy `https://<job_id>--<port>.hf.jobs` (HTTPS) which by default needs an HF token with read access to the namespace in the `Authorization: Bearer` header, while `--expose-public 8787` drops HF authentication so anyone with the URL can reach it; or `--ssh` on the Job, where the docs show port forwarding in the form `ssh -L 6006:localhost:6006 <job_id>@ssh.hf.jobs` (needs a registered SSH public key and write access). Because private exposure puts the HF token in the `Authorization` header, which collides with the bridge's own token header, and browser CORS preflight requests do not carry it (how the proxy treats them is not verified), the practical choices are `--expose-public` plus the bridge's own token, or SSH forwarding; never put an HF token into the web page. Account: any user or organization with a positive credit balance can run Jobs, PRO is not required; credits are prepaid and need a credit card (the docs say cards issued in India are not supported); set the timeout with `--timeout` (docs examples go up to 1 day, the maximum is not stated). Terms: the Hugging Face Terms of Service do not discuss compute services and I did not read the Supplemental Terms or Content Policy, so the status is "allowed as documented, supplemental terms not verified". There is also an experimental Sandboxes feature built on Jobs (GPU possible, reached through `proxy_url_for`, but needs auth headers and has a hard 24-hour lifetime).

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed (按文档;补充条款未核实 / as documented; supplemental terms not verified). 来源 / source: https://huggingface.co/docs/hub/jobs-configuration (Expose Ports and SSH sections); https://huggingface.co/docs/hub/jobs-pricing (exposed ports billed); https://huggingface.co/terms-of-service (silent on compute) |
| 连接方式 / How to connect | `hf jobs run --flavor t4-small --timeout 3h --expose-public 8787 <镜像> <命令>`,地址 `https://<job_id>--8787.hf.jobs`(HTTPS,服务监听 0.0.0.0,公开);或 `--ssh` 后 `ssh -L 8787:localhost:8787 <job_id>@ssh.hf.jobs`,用 `http://127.0.0.1:8787`。 / `hf jobs run --flavor t4-small --timeout 3h --expose-public 8787 <image> <command>`, address `https://<job_id>--8787.hf.jobs` (HTTPS, service bound to 0.0.0.0, public); or `--ssh` then `ssh -L 8787:localhost:8787 <job_id>@ssh.hf.jobs` and use `http://127.0.0.1:8787`. Docs: https://huggingface.co/docs/hub/jobs-configuration , https://huggingface.co/docs/huggingface_hub/guides/jobs |
| 费用 / Cost | T4 small 约 0.40、T4 medium 约 0.60、L4 约 0.80、A10G small 约 1.00 美元/小时,暴露端口另加约 0.01 美元/小时,按分钟计费;需正余额。 / T4 small about 0.40, T4 medium about 0.60, L4 about 0.80, A10G small about 1.00 USD/hour, plus about 0.01 USD/hour for exposed ports, billed per minute; a positive credit balance is required (read on 2026-11-01). https://huggingface.co/docs/hub/jobs-pricing , https://huggingface.co/pricing |

#### Lightning AI 平台 / Lightning AI

Lightning AI 的 Studio 是一个持久的云工作区,默认运行在免费 CPU 上,需要时用 GPU 切换器换到 GPU(价格页:T4 约 0.55、L4 约 0.79、L40S 约 3.54 美元/小时,按秒计费,2026-11-01 读取;没有列出 A10G)。免费版含一个 CPU Studio,价格页写最多 30 个免费积分(约 80 个可中断 GPU 小时),注册送 5 个、加卡再送 25 个,FAQ 要求用真实(非虚拟)手机号,积分只能给一个账号。文档确实描述了把 Studio 里的服务端口发布出去:"API builder" 插件(以及 ports 插件)可以把监听端口的服务器(文档说 FastAPI 也可以)变成公网可访问的 API,并提供 token 认证或基本认证,但同一页称这是原型用途,生产应使用 Job;公开 URL 的格式、是否 HTTPS、哪个套餐可用,文档里都没有写。Studio 超过 10 分钟没有活动会自动休眠,开了 auto start 才会在收到请求时唤醒,唤醒有数分钟冷启动,所以不适合需要常驻的 bridge。SSH 访问有官方说明(终端插件里复制 "Connect via SSH" 命令),但页面没有给出 `-L` 示例。服务条款我没有读到(几个常见地址都返回 404),所以是否允许长期提供服务只能判定为不明确;使用前要自己读条款并在账户里确认 API builder 的 URL 和是否 HTTPS。

A Lightning AI Studio is a persistent cloud workspace that starts on a free CPU and switches to a GPU with the GPU switcher when needed (pricing page: T4 about 0.55, L4 about 0.79, L40S about 3.54 USD/hour, billed per second, read on 2026-11-01; no A10G is listed). The free plan includes one CPU Studio, the pricing page says up to 30 free credits (about 80 interruptible GPU hours), 5 on registration and 25 more after adding a card, the FAQ requires a real (non-virtual) phone number, and credits can only be claimed for one account. The docs do describe publishing a Studio port: the "API builder" plugin (and a ports plugin) can turn a server listening on a port (the docs say FastAPI works too) into an API reachable from the internet, with token or basic authentication, but the same pages frame this as prototyping and say production should use a Job; the URL format, whether it is HTTPS and which plan includes it are not stated. A Studio sleeps automatically after more than 10 minutes without activity and only wakes on a request if auto start is on, with a cold start of a few minutes, so it is a poor fit for a bridge that must stay up. SSH access is documented (copy the "Connect via SSH" command from the Terminal plugin) but the page shows no `-L` example. I could not read the Terms of Service (several likely addresses returned 404), so whether long-lived serving is allowed can only be classed as unclear; read the terms yourself and confirm the API builder URL and HTTPS in your account before relying on it.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 不明确 / unclear (文档把它当原型功能描述,服务条款未能读取 / the docs describe it as a prototyping feature, the Terms could not be read). 来源 / source: https://lightning.ai/docs/platform/build/ai-studio/deploy-on-public-ports.md ; https://lightning.ai/docs/platform/inference/batch-jobs/prototype-server-api.md ; https://lightning.ai/docs/platform/build/host-web-apps.md |
| 连接方式 / How to connect | API builder 插件给出的公网地址(格式、HTTPS 未核实,可选 token 认证);或终端插件的 "Connect via SSH" 命令(页面无 `-L` 示例)。 / The public address given by the API builder plugin (format and HTTPS not verified, token authentication optional); or the "Connect via SSH" command from the Terminal plugin (no `-L` example on the page). Docs: https://lightning.ai/docs/platform/build/ai-studio/deploy-on-public-ports.md , https://lightning.ai/docs/platform/build/ai-studio/ssh-access.md |
| 费用 / Cost | T4 约 0.55、L4 约 0.79 美元/小时(按秒计费);免费版有一次性积分,需要手机号验证。 / T4 about 0.55, L4 about 0.79 USD/hour (billed per second); the free plan has one-off credits and needs phone verification (read on 2026-11-01). https://lightning.ai/pricing , https://lightning.ai/docs/platform/overview/faq.md |

#### Google Colab (免费与付费 / free and paid)

Colab 是浏览器里的笔记本服务,GPU 型号随时间变化且不保证(FAQ 没有列出具体型号),付费方案按"计算单元"计费。官方 FAQ 把"与 Colab 交互计算无关的文件托管、媒体服务或其他网络服务"以及"连接远程代理"列为所有托管运行时都禁止的行为;没有正的计算单元余额的免费运行时还禁止 SSH、远程桌面,以及绕过笔记本界面、主要通过网页界面交互。桥接服务器是供外部网页调用的网络服务,落在上述禁止范围内,隧道、代理和保活脚本同样不能用,所以判定为禁止,Colab 只适合批处理分析(见 docs/COMPUTE-PLATFORMS.md)。我没有找到任何官方文档化的、让外部浏览器连到笔记本里 8787 端口的方式。付费方案只在页面列出的国家和地区提供(列表含德国,不含中国大陆)。

Colab is a browser notebook service. GPU models vary over time and are not guaranteed (the FAQ names no model), and paid plans are metered in compute units. The official FAQ lists file hosting, media serving and other web services unrelated to interactive compute with Colab as disallowed on all managed runtimes, and it also bans "connecting to remote proxies". Free runtimes without a positive compute unit balance additionally may not use SSH shells, remote desktops, or bypass the notebook UI to work mainly through a web UI. The bridge is a network service for an external web page, so it falls inside the prohibited area; tunnels, proxies and keep-alive scripts are not acceptable either. The verdict is forbidden for serving: use Colab for batch analysis only (see docs/COMPUTE-PLATFORMS.md). I found no officially documented way for an outside browser to reach port 8787 inside a notebook. Paid plans are sold only in the countries listed on the pricing page (Germany is listed, mainland China is not).

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 禁止 / forbidden. 来源 / source: https://research.google.com/colaboratory/faq.html (section on restricted activities) |
| 连接方式 / How to connect | 无合规方式 / no compliant route. 文档没有给出入站端口或 HTTPS 代理地址,FAQ 禁止远程代理 / the docs give no inbound port or HTTPS proxy URL and the FAQ bans remote proxies |
| 费用 / Cost | Colab Pro 约 11.01 欧元/月(100 计算单元);Pro+ 约 50.28 欧元/月(600 计算单元,运行中的笔记本关闭浏览器后最长可持续 24 小时);按量付费约 11.01 欧元买 100 单元、约 50.28 欧元买 500 单元;单元 90 天过期;免费版单次最长 12 小时且 GPU 受严格限制。 / Pro about 11.01 EUR per month (100 units); Pro+ about 50.28 EUR per month (600 units, up to 24 h background execution); pay as you go about 11.01 EUR per 100 units and 50.28 EUR per 500; units expire after 90 days; free notebooks run at most 12 h with heavily limited GPUs (read on 2026-11-01). 来源 / source: https://colab.research.google.com/signup?hl=en |

#### Kaggle Notebooks (仅批处理 / batch only)

Kaggle 免费提供一块 P100 或两块 T4(T4 x2),文档给出的每周 GPU 配额是 30 小时(需求和资源允许时有时更高)。会话最长 12 小时(TPU 为 9 小时),"Save & Run All"也必须在 12 小时内跑完,交互编辑会话空闲 20 分钟就会结束。可接受使用政策禁止滥用资源进行挖矿、DDoS、"服务器农场"和"与机器学习数据科学无关的活动",也禁止规避或干扰服务的任何环节。条款没有逐字写"禁止开 HTTP 服务",但笔记本只有交互编辑和批量运行两种模式,文档中没有任何入站网络路径,所以我的判定是仅批处理,不要拿它当桥接服务器。文档里实验性的"Kaggle Jupyter Server"是把 Colab 或 VS Code 接到 Kaggle 会话,不是向浏览器开放 8787 端口,不能当作服务方案。

Kaggle gives one P100 or two T4 GPUs (T4 x2) for free, and the docs state a weekly GPU quota of 30 hours (sometimes higher depending on demand and resources). A session runs at most 12 hours (9 for TPU), "Save & Run All" must also finish inside 12 hours, and an interactive editing session ends after 20 minutes idle. The acceptable use policy forbids abusing resources for cryptomining, DDoS, server farming and activity unrelated to ML data science, and also forbids disabling, interfering with or circumventing any part of the service. The terms do not literally say "no HTTP servers", but notebooks only offer interactive editing and batch runs, the docs describe no inbound network path, so the verdict is batch only: do not use it as the bridge host. The experimental "Kaggle Jupyter Server" in the docs connects Colab or VS Code to a Kaggle session; it does not open port 8787 to a browser and is not a serving option.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 仅批处理 / batch only. 来源 / source: https://www.kaggle.com/aup (cryptomining, server farming, activity unrelated to ML data science, circumvention) and https://www.kaggle.com/terms (cryptomining clause); session model in https://www.kaggle.com/docs/notebooks |
| 连接方式 / How to connect | 无文档化的入站路径 / no documented inbound route |
| 费用 / Cost | 免费;P100 或 T4 x2;每周 GPU 配额 30 小时或更高;单次 12 小时。 / Free; P100 or T4 x2; weekly GPU quota 30 h or more; 12 h per session (read on 2026-11-01). 来源 / source: https://www.kaggle.com/docs/efficient-gpu-usage and https://www.kaggle.com/docs/notebooks. 账号要求(手机验证等)未在所读页面核实 / account requirements such as phone verification not verified on the pages read |

#### AWS EC2 (g4dn, g5, g6) 平台 / AWS EC2 (g4dn, g5, g6)

g4dn 用 NVIDIA T4(g4dn.xlarge:1 块 GPU、4 vCPU、16 GiB 内存),g5 用 NVIDIA A10G(g5.xlarge:24 GB 显存),g6 用 NVIDIA L4(g6.xlarge:24 GB 显存),都是以 EC2 虚拟机方式启动,Deep Learning AMI 预装了 CUDA 和 cuDNN。AWS 可接受使用政策只列出违法、侵权、攻击、垃圾信息等类别,没有提到 Web 或 API 服务,所以自用的小型 API 服务属于允许。官方文档化的连接方式是 Systems Manager Session Manager 端口转发(`aws ssm start-session --target <实例ID> --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["8787"],"localPortNumber":["8787"]}'`),之后浏览器访问明文 http 的 `http://127.0.0.1:8787`,不是 https。这条路线不需要公网 IP 和入站安全组规则,但实例必须能经 443 出站访问 ssm、ssmmessages、ec2messages 端点,并挂带 AmazonSSMManagedInstanceCore 的实例配置文件,本机要装 AWS CLI 和 Session Manager 插件。关键门槛是配额:"Running On-Demand G and VT instances"默认值为 0 vCPU,可调整,至少要申请 4 vCPU 才能开 xlarge 规格。

g4dn uses the NVIDIA T4 (g4dn.xlarge: 1 GPU, 4 vCPU, 16 GiB), g5 uses the NVIDIA A10G (g5.xlarge: 24 GB GPU memory), g6 uses the NVIDIA L4 (g6.xlarge: 24 GB GPU memory); all start as EC2 virtual machines, and the Deep Learning AMI ships with CUDA and cuDNN. The AWS acceptable use policy lists only categories such as illegal use, rights violations, attacks and spam and does not mention web or API servers, so a small personal API server is allowed. The documented connection is Systems Manager Session Manager port forwarding (`aws ssm start-session --target <instance-id> --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["8787"],"localPortNumber":["8787"]}'`), after which the browser uses plain http at `http://127.0.0.1:8787`, not https. This route needs no public IP and no inbound security group rule, but the instance must reach the ssm, ssmmessages and ec2messages endpoints over outbound 443 and carry an instance profile with the AmazonSSMManagedInstanceCore policy, and the local machine needs the AWS CLI plus the Session Manager plugin. The main hurdle is quota: "Running On-Demand G and VT instances" defaults to 0 vCPUs and is adjustable, so request at least 4 vCPUs to launch an xlarge size.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed. 来源 / source: https://aws.amazon.com/aup/ (the policy does not mention servers; only the listed categories are banned) |
| 连接方式 / How to connect | SSM 端口转发,本地地址 `http://127.0.0.1:8787`(http,非 https) / SSM port forwarding, local address `http://127.0.0.1:8787` (http, not https). 来源 / source: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html ; prerequisites: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-prerequisites.html ; instance profile: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-getting-started-instance-profile.html. 安全组只放行规则允许的流量 / a security group only lets in traffic its rules allow: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html |
| 费用 / Cost | Linux 按需,美东(弗吉尼亚北部) / Linux on-demand, US East (N. Virginia): g4dn.xlarge 约 0.526 USD/h,g5.xlarge 约 1.006 USD/h,g6.xlarge 约 0.805 USD/h。欧洲(法兰克福) / EU (Frankfurt): g4dn.xlarge 约 0.658 USD/h,g5.xlarge 约 1.258 USD/h,g6.xlarge 约 1.006 USD/h。不含存储与流量 / storage and traffic excluded (price data file published 2026-10-29, read on 2026-11-01). 来源 / source: AWS pricing data feed for the EC2 on-demand pricing page, https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/EU%20(Frankfurt)/Linux/index.json (US East uses the same path with "US%20East%20(N.%20Virginia)"). 账号 / account: AWS Free 页面写新账号可得 100 美元,另可再赚最多 100 美元,共 6 个月内;该页没有说明额度能否用于 GPU 实例,也没有提到信用卡或手机验证 / the AWS Free page says new accounts get 100 USD plus up to 100 USD more over 6 months; it does not say whether credits cover GPU instances and does not mention a card or phone check: https://aws.amazon.com/free/ |
| GPU 配额 / GPU quota | G 与 VT 实例默认 0 vCPU,可调整;xlarge 规格需要 4 vCPU;配额按区域。 / G and VT default 0 vCPUs, adjustable; xlarge sizes need 4 vCPUs; quotas are per Region. https://docs.aws.amazon.com/ec2/latest/instancetypes/ec2-instance-quotas.html |

#### 谷歌云 Compute Engine (L4, T4) / Google Cloud Compute Engine (L4, T4)

L4 挂在 G2 机型上且已预挂接(例如 g2-standard-4:1 块 L4、4 vCPU、16 GiB 内存),T4 通过 N1 机型挂接,文档同时提示 T4 与 P4 将在 2027-08-01 结束支持。Compute Engine 是 IaaS,Google Cloud 可接受使用政策只列出违法、攻击、垃圾信息等类别,没有提到 Web 或 API 服务,所以自用小服务属于允许。门槛在账号:不可结算的免费试用账号不能给虚拟机加 GPU,也不能申请提高配额,必须升级为付费结算账号;GPU 配额按型号和区域计,另有全局的"GPUs (all regions)"配额,需要在控制台配额页申请。文档化的连接方式是 IAP TCP 转发:`gcloud compute start-iap-tunnel <实例名> 8787 --local-host-port=localhost:8787 --zone=<可用区>`,浏览器访问明文 http 的 `http://localhost:8787`;需要一条放行来源 35.235.240.0/20 到目标 TCP 端口的入站防火墙规则,并授予 IAP-Secured Tunnel User 角色,虚拟机不需要公网 IP,官方说明 IAP 转发不适合大批量数据传输,空闲一小时会断开(gcloud 会尝试重连)。

L4 attaches through G2 machine types with the GPU pre-attached (for example g2-standard-4: 1 L4, 4 vCPU, 16 GiB), T4 attaches to N1 machines, and the docs note that T4 and P4 reach end of support on 2027-08-01. Compute Engine is IaaS and the Google Cloud acceptable use policy lists only categories such as illegal use, attacks and spam without mentioning web or API servers, so a small personal service is allowed. The hurdle is the account: a non-billable free-trial billing account cannot add GPUs to VMs or request quota increases, so you must upgrade to a paid billing account; GPU quota is counted per model and region, plus a global "GPUs (all regions)" quota, requested on the console Quotas page. The documented connection is IAP TCP forwarding: `gcloud compute start-iap-tunnel <instance> 8787 --local-host-port=localhost:8787 --zone=<zone>`, and the browser then uses plain http at `http://localhost:8787`; it needs an ingress firewall rule allowing source 35.235.240.0/20 to the target TCP port and the IAP-Secured Tunnel User role, the VM needs no public IP, and the docs say IAP forwarding is not meant for bulk data transfer and drops sessions after one hour of inactivity (gcloud tries to reconnect).

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed. 来源 / source: https://cloud.google.com/terms/aup (no mention of servers; only the listed categories are banned) |
| 连接方式 / How to connect | IAP TCP 转发到 `http://localhost:8787`(http,非 https) / IAP TCP forwarding to `http://localhost:8787` (http, not https). 来源 / source: https://docs.cloud.google.com/iap/docs/using-tcp-forwarding |
| 费用 / Cost | g2-standard-4(1 块 L4)按需约 0.707 USD/h,Spot 约 0.423 USD/h(Iowa,us-central1);T4 挂接约 0.35 USD/h(us-central1,不含 N1 虚拟机本身的价格),磁盘另计。 / g2-standard-4 (1 L4) on-demand about 0.707 USD/h, Spot about 0.423 USD/h (Iowa, us-central1); a T4 attachment about 0.35 USD/h in us-central1 excluding the N1 VM itself; disks extra (read on 2026-11-01). 来源 / source: https://cloud.google.com/products/compute/pricing/accelerator-optimized . 账号 / account: 免费试用为 300 美元赠金、90 天,注册需要信用卡或其他付款方式;试用账号不能加 GPU / the free trial is 300 USD credit for 90 days and sign-up needs a credit card or other payment method; trial accounts cannot add GPUs: https://docs.cloud.google.com/free/docs/free-cloud-features |
| GPU 配额 / GPU quota | 每个型号按区域有配额,另有全局"GPUs (all regions)";T4 配额名 NVIDIA_T4_GPUS,L4 为 GPU_FAMILY:NVIDIA_L4。 / per-model regional quotas plus the global "GPUs (all regions)"; T4 quota name NVIDIA_T4_GPUS, L4 is GPU_FAMILY:NVIDIA_L4. https://docs.cloud.google.com/compute/resource-usage |

#### 微软 Azure (NC, ND, NV) / Microsoft Azure (NC, ND, NV)

NCasT4_v3 系列使用 NVIDIA Tesla T4(每块 16 GB),Standard_NC4as_T4_v3 是 1 块 T4、4 vCPU、28 GiB 内存,文档说 Azure NVIDIA GPU 驱动扩展会安装 CUDA 驱动。Microsoft 在线服务的可接受使用政策禁止违法、未授权访问、垃圾信息、挖矿、抓取等,没有提到 Web 或 API 服务,所以自用小服务属于允许(我读到的是页面内容的摘要,完整政策全文未逐条核对)。Azure 的 NSG 默认拒绝来自互联网的入站流量(DenyAllInbound),所以文档化的方式有两种:一是公网 IP 加只放行你自己公网 IP 的 NSG 规则,再用 OpenSSH `ssh -L 8787:127.0.0.1:8787` 转发(NSG 页面描述规则,`-L` 这一步是标准 OpenSSH 用法,Azure 文档没有为这个场景写出);二是 Azure Bastion 原生客户端,需要 Standard 或更高 SKU 并勾选 Native Client Support,用 `az network bastion tunnel` 转发 SSH 端口 22 再在其上做 `ssh -L`。Bastion 文档说明隧道命令用于 SSH 或 RDP,"The bastion tunnel doesn't relay web servers or hosts",功能表还写明隧道命令不支持自定义端口,所以不要直接隧道 8787。vCPU 配额按区域和 VM 系列分两层,在门户"My quotas"页申请,文档说通常几分钟内处理,不成功再开支持工单;NCasT4_v3 的默认配额未核实。

The NCasT4_v3 series uses the NVIDIA Tesla T4 (16 GB each); Standard_NC4as_T4_v3 is 1 T4, 4 vCPU and 28 GiB, and the docs say the Azure NVIDIA GPU driver extension installs the CUDA drivers. The Microsoft Online Services acceptable use policy bans illegal use, unauthorized access, spam, mining, scraping and similar, and does not mention web or API servers, so a small personal service is allowed (I read a summary of the page, not every clause of the full policy). Azure NSGs deny inbound internet traffic by default (DenyAllInbound), so there are two documented ways in: a public IP plus an NSG rule that only allows your own public IP, then OpenSSH `ssh -L 8787:127.0.0.1:8787` (the NSG page describes the rule; the `-L` step is standard OpenSSH and Azure's docs do not spell it out for this case), or the Azure Bastion native client, which needs the Standard or Premium SKU with Native Client Support enabled and uses `az network bastion tunnel` to forward SSH port 22, with `ssh -L` layered on top. The Bastion docs say the tunnel command is for SSH or RDP, "The bastion tunnel doesn't relay web servers or hosts", and the feature table lists no custom-port support for the tunnel command, so do not tunnel 8787 directly. vCPU quotas are two-tier per region and per VM family, requested under "My quotas" in the portal, usually handled within minutes, with a support request as fallback; the default quota for NCasT4_v3 was not verified.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed. 来源 / source: https://www.microsoft.com/licensing/terms/product/ForOnlineServices/all (Acceptable Use Policy; no mention of servers) |
| 连接方式 / How to connect | 方式一 / option 1: 公网 IP + NSG 只放行自己的 IP + `ssh -L`,地址 `http://127.0.0.1:8787`(http) / public IP + NSG allowing only your IP + `ssh -L`, address `http://127.0.0.1:8787` (http). NSG: https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview . 方式二 / option 2: Bastion 原生客户端隧道到 22,再 `ssh -L` / Bastion native client tunnel to port 22, then `ssh -L`: https://learn.microsoft.com/en-us/azure/bastion/native-client and https://learn.microsoft.com/en-us/azure/bastion/connect-vm-native-client-linux |
| 费用 / Cost | Standard_NC4as_T4_v3 Linux 按需约 0.658 USD/h(West Europe 与 Germany West Central)、约 0.526 USD/h(East US);Spot 约 0.322 / 0.196 / 0.164 USD/h(同样三个区域,生效日 2026-11-01)。Bastion Standard 网关约 0.29 USD/h(Germany West Central),按小时从部署起计费,Basic 约 0.19 USD/h 但不支持原生客户端;标准静态公网 IPv4 约 0.005 USD/h。 / Standard_NC4as_T4_v3 Linux pay as you go about 0.658 USD/h (West Europe, Germany West Central) and about 0.526 USD/h (East US); Spot about 0.322 / 0.196 / 0.164 USD/h (same three regions, effective 2026-11-01). Bastion Standard gateway about 0.29 USD/h (Germany West Central), billed hourly from deployment; Basic about 0.19 USD/h but no native client; Standard static public IPv4 about 0.005 USD/h (read on 2026-11-01). 来源 / source: Azure Retail Prices API, https://prices.azure.com/api/retail/prices (queried with filters for the SKU and regions). 账号 / account: 免费账号页写 200 美元赠金、30 天内使用,注册需要手机号、非预付信用卡或借记卡、Microsoft 或 GitHub 账号 / the free account page says 200 USD credit usable within 30 days, and sign-up needs a phone number, a non-prepaid credit or debit card and a Microsoft or GitHub account: https://azure.microsoft.com/en-us/free/ |
| GPU 配额 / GPU quota | vCPU 配额按区域和 VM 系列两层;在门户"My quotas"申请,通常几分钟 / two-tier vCPU quota per region and VM family; request in the portal under My quotas, usually minutes. https://learn.microsoft.com/en-us/azure/quotas/per-vm-quota-requests |

#### 莱布尼茨计算中心 LRZ AI Systems / LRZ AI Systems (Leibniz-Rechenzentrum)

LRZ AI Systems 是慕尼黑 LRZ 的 AI 集群,主要由 BayernKI 资助,文档写明目前处于试运行阶段。GPU 有 P100、V100、A100(40 或 80 GB)和 H100(94 GB),例如默认分区 lrz-v100x2(每节点 2 块 V100)和 lrz-hgx-h100-94x4(每节点 4 块 H100),没有 T4 或消费级显卡;通过 Slurm 使用,`salloc -p <分区> --gres=gpu:1` 申请交互分配,默认时限 1 小时,最长 2 天,也可以在 https://login.ai.lrz.de 的网页门户里启动 Jupyter、RStudio、TensorBoard 会话(最长 48 小时)。在计算节点上跑自己写的常驻服务器进程:使用政策、Slurm 页和交互作业页都没有规定也没有提到端口转发或服务;政策只写明系统不主要用于开发、原型和调试,开发测试应保持最少,并尽量缩短空闲时间,长时间空闲占用 GPU 的桥接服务与这一精神不符,所以判定为不明确(倾向不适合),需先问 LRZ Servicedesk。SSH 登录 login.ai.lrz.de 要求设备在慕尼黑科学网络(MWN),AI 项目组成员资格附带 MWN 的 VPN 访问;AI Systems 文档没有描述到计算节点的端口转发,LRZ 通用的 Jupyter FAQ 描述了 `ssh -L` 到计算节点,但它只适用于 CoolMUC-4 和 SuperMUC-NG,不能直接套用,网页门户是否支持自定义端口也未说明。申请条件:需要 LRZ 账号并关联到"AI 启用"的 LRZ 项目(由项目 master user 加人,或通过 LRZ Servicedesk 申请启用已有项目,或申请新项目,或走 BayernKI),要说明明确的研究目的,项目一年到期需续期,并受出口管制和 LRZ 使用规则约束。

The LRZ AI Systems are the Leibniz-Rechenzentrum AI cluster in Munich, funded mainly by BayernKI, and the docs say it is currently in pilot operation. GPUs are P100, V100, A100 (40 or 80 GB) and H100 (94 GB), for example the default partition lrz-v100x2 (2 V100 per node) and lrz-hgx-h100-94x4 (4 H100 per node); there is no T4 or consumer card. It is used through Slurm: `salloc -p <partition> --gres=gpu:1` for interactive allocations (default time limit 1 hour, maximum 2 days), or Jupyter, RStudio and TensorBoard sessions launched in the web portal at https://login.ai.lrz.de (up to 48 hours). Whether a self-written long-lived server process may run on a compute node is not addressed: the usage policies, the Slurm page and the interactive jobs page say nothing about services or port forwarding; the policies only say the systems are not primarily for development, prototyping or debugging, that interactive development should be kept to the minimum and idle time minimized. A mostly idle bridge holding a GPU does not fit that spirit, so the verdict is unclear (leaning unsuitable) and you must ask the LRZ Servicedesk first. SSH to login.ai.lrz.de needs the device to be on the Munich Scientific Network (MWN), and membership of the AI project group includes VPN access to the MWN; the AI Systems docs describe no port forwarding to compute nodes, the general LRZ Jupyter FAQ describes `ssh -L` to a compute node but only for CoolMUC-4 and SuperMUC-NG, so it cannot be applied directly, and whether the web portal supports custom ports is not stated. Who may apply: you need an LRZ account linked to an AI-enabled LRZ project (the project master user adds you, or a master user asks the LRZ Servicedesk to enable an existing project, or you apply for a new project, or you go through BayernKI), you must show a clear research purpose, projects expire after a year and need renewal, and access is subject to export control and the LRZ usage regulations.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 不明确 / unclear. 门户中的 Jupyter、RStudio、TensorBoard 是文档化的交互网页服务;自定义 Python HTTP 服务未被提及;政策强调最少交互开发、尽量缩短空闲 / the Jupyter, RStudio and TensorBoard apps in the portal are documented interactive web services; a custom Python HTTP server is not mentioned; the policy stresses minimal interactive development and minimal idle time. 来源 / source: https://doku.lrz.de/1-2-usage-policies-2763063391.html , https://doku.lrz.de/6-interactive-apps-10746644.html , https://doku.lrz.de/5-slurm-1897076524.html |
| 连接方式 / How to connect | 终端 / terminal: `ssh login.ai.lrz.de -l <用户名>`,需要在 MWN 内(项目组成员有 MWN 的 VPN) / needs the MWN (project members get MWN VPN). 网页 / web: https://login.ai.lrz.de (https). 到计算节点的端口转发未在 AI Systems 文档中说明 / port forwarding to compute nodes is not described in the AI Systems docs. 来源 / source: https://doku.lrz.de/1-1-ai-systems-login-2498299908.html , https://doku.lrz.de/1-access-10746642.html ; 通用 Jupyter FAQ(不含 AI Systems) / generic Jupyter FAQ (does not cover AI Systems): https://doku.lrz.de/faq-jupyter-on-hpc-systems-10746056.html |
| 费用 / Cost | 所读 LRZ 页面没有标价;BayernKI 资源对符合条件的研究者免费(见下一节)。 / The LRZ pages read show no price; BayernKI resources are free for eligible researchers (see next section). 读取日期 / read on 2026-11-01 |

#### BayernKI 平台 / BayernKI

BayernKI 是巴伐利亚州面向科研和教学的统一 AI 基础设施,由 LRZ(Garching)和 NHR@FAU(Erlangen)联合运营,由巴伐利亚州资助。LRZ 的新闻稿称核心是约 300 块 NVIDIA H100(每块 94 GB),计划在 2026 年秋季扩展到超过 250 块 GB200 芯片。使用对象是巴伐利亚州立大学和应用科学大学(HAW、TH、FH)的研究人员,CPU 与 GPU 资源免费;非 FAU 申请人在官方表单里选择 LRZ 或 NHR@FAU 作为首选中心,提交简短的项目说明,官方页面写通常数日内获批,每个研究组只受理一份申请,项目简介可能被公开。BayernKI 的官方页面(主页、Access、FAQ)没有写交互式服务是否允许,也没有写资源上限、时长或学生能否自己申请,这些要看所选中心的规则:在 LRZ 即上一节的 AI Systems 规则,所以判定为不明确。NHR@FAU 一侧的交互使用规则我没有读,未核实。

BayernKI is Bavaria's central AI infrastructure for research and teaching, operated jointly by LRZ (Garching) and NHR@FAU (Erlangen) and funded by the Free State of Bavaria. An LRZ news item says the core is about 300 NVIDIA H100 GPUs (94 GB each), with an expansion to more than 250 GB200 chips planned for autumn 2026. Researchers at state-funded Bavarian universities and universities of applied sciences (HAW, TH, FH) can use the CPU and GPU resources free of charge; applicants outside FAU choose LRZ or NHR@FAU as the preferred center in the official form and submit a short project outline, the official page says access is typically granted within days, only one application per research group is accepted, and the project description may be published. The official BayernKI pages (home, Access, FAQ) do not say whether interactive services are allowed, and they give no resource limits, durations or rules on student applications; those depend on the chosen center, which at LRZ means the AI Systems rules in the previous section, so the verdict is unclear. I did not read the NHR@FAU interactive-use rules; that point is not verified.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 不明确 / unclear. BayernKI 页面未涉及,取决于所选中心 / BayernKI pages do not address it, it depends on the chosen center. 来源 / source: https://www.ki-in-bayern.de/access/ , https://www.ki-in-bayern.de/faqs/ , https://www.kib.cms.rrze.net/ |
| 连接方式 / How to connect | 与所选中心相同(LRZ 见上) / same as the chosen center (see LRZ above). 申请 / application: https://www.ki-in-bayern.de/de/registration-for-bayernki-access/ ; NHR@FAU 说明 / NHR@FAU notes: https://doc.nhr.fau.de/bayernki-application/ ; LRZ 新闻 / LRZ news: https://www.lrz.de/en/news/detail/one-year-of-bayernki |
| 费用 / Cost | 对符合条件的研究者免费 / free for eligible researchers (read on 2026-11-01). 来源 / source: https://www.ki-in-bayern.de/access/ |

#### 国内 / China

一个先决说明 / A naming note: 用户清单里的"趋动云 OpenBayes (openbayes.com)"其实是两个不同的平台。openbayes.com 是 OpenBayes(贝式计算),趋动云是 virtaicloud.com。下面分开写。 / The brief's "趋动云 OpenBayes (openbayes.com)" is two different platforms: openbayes.com is OpenBayes, 趋动云 is virtaicloud.com. They are covered separately below.

#### AutoDL (autodl.com) 平台 / AutoDL (autodl.com)

AutoDL 出租的是容器实例,GPU 型号见官方 GPU 选型页,例如 RTX 3090、RTX 4090、V100、A40、A100,页面没有写 T4。官方给个人用户的办法是 SSH 隧道:`ssh -CNg -L 6006:127.0.0.1:6006 root@<主机> -p <端口>`,命令保持运行,然后在本机浏览器打开 `http://127.0.0.1:6006`,本项目只需把 6006 换成 8787。公网"自定义服务"只映射实例的 6006 和 6008 两个端口,开放端口页写明需要企业认证,个人用户请用 SSH 隧道;自定义服务补充协议还规定它只能用于科研、只能本人使用、不得把链接分享给第三方,并且必须先完成实名认证。文档里没有 GPU 单价(价格在算力市场页,我的工具读不到),计费按秒、开机即计费,无卡模式为 0.1 元/小时。需要自己确认:账号实名状态、目标地区是否有空闲 GPU、实例关机连续 15 天会被释放。

AutoDL rents container instances. The GPU selection page lists cards such as RTX 3090, RTX 4090, V100, A40 and A100, and does not mention T4. For individual users the vendor's documented route is an SSH tunnel: `ssh -CNg -L 6006:127.0.0.1:6006 root@<host> -p <port>`, keep it running, then open `http://127.0.0.1:6006` locally; for this project swap 6006 for 8787. The public "custom service" maps only ports 6006 and 6008 of an instance, the open-ports page says it needs enterprise certification and tells individuals to use the SSH tunnel, and the custom-service supplementary agreement limits it to research use, personal use only, no sharing of the link with third parties, and requires real-name verification first. The docs give no GPU price (prices sit on the marketplace page, which my tool could not read); billing is per second from power-on, and no-GPU mode costs 0.1 CNY per hour. Confirm yourself: your real-name status, whether a free GPU exists in your region, and that an instance powered off for 15 consecutive days is released.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed, 方式限定 / with limits: SSH 隧道是文档推荐给个人用户的做法 / the SSH tunnel is the documented route for individuals. 公网自定义服务 / public custom service: 仅企业认证,仅限科研,仅本人使用 / enterprise certification only, research only, personal only. 来源 / source: https://www.autodl.com/docs/port/ ; https://www.autodl.com/docs/service_agreement/ ; https://www.autodl.com/docs/ssh_proxy/ |
| 连接方式 / How to connect | 本地转发(SSH) / SSH local forward: `ssh -CNg -L 8787:127.0.0.1:8787 root@<主机/host> -p <端口/port>` (官方示例用 6006,8787 是按同一格式的替换 / the vendor example uses 6006, 8787 is my substitution in the same form). 登录命令在控制台实例的 SSH 登录处,实例需先开机 / the login command is in the console, the instance must be powered on first: https://www.autodl.com/docs/ssh/ . 得到 http 回环地址,不是 https / result is an http loopback address, not https. Windows 提示:粘贴密码可能失败,请手动输入 / on Windows, pasting the password may fail, type it by hand (https://www.autodl.com/docs/ssh_proxy/). 公网映射示例地址为 https 加 8443 端口,但需要企业认证 / the public mapping example is an https address on port 8443 but needs enterprise certification (https://www.autodl.com/docs/port/). 长任务建议用 screen/tmux / use screen or tmux for long jobs. |
| 费用 / Cost | GPU 单价未核实;按秒计费,开机即计费(https://www.autodl.com/docs/price/);无卡模式约 0.1 元/小时,每个主账号一台(https://www.autodl.com/docs/save_money/);数据盘等另计;最低充值文档未写(读取于 2026-11-01)。 / GPU prices not verified; per-second billing from power-on (https://www.autodl.com/docs/price/); no-GPU mode about 0.1 CNY per hour, one such instance per main account (https://www.autodl.com/docs/save_money/); extra disks billed separately; the minimum top-up is not stated (read on 2026-11-01). |
| GPU | RTX 3090, RTX 4090, V100, A40, A100 SXM4, RTX A5000 等 / and others; 无 T4 描述 / no T4 mentioned: https://www.autodl.com/docs/gpu/ |
| 实名认证 / Real-name | 自定义服务必须实名 / required for the custom service (service agreement URL above). 个人可用身份证加人脸视频,或银行卡,或护照等 / individuals can use ID card plus face video, bank card, or passport etc.: https://www.autodl.com/docs/real_name_cert/ . 仅租 GPU 是否必须,文档没写 / whether renting a GPU alone needs it is not stated. |
| 备案 / ICP filing | 自定义服务协议和服务协议均未提备案 / neither the custom-service agreement nor the service agreement mentions filing. SSH 隧道不涉及域名或公网端口 / an SSH tunnel involves no domain and no public port. |
| 需确认 / To confirm | 实名状态;所选区域的空闲 GPU;企业认证规则是否仍有效(页面无日期) / real-name status; free GPUs in your region; whether the enterprise-certification rule is current (the page is undated). |

#### 恒源云 Gpushare (gpushare.com)

恒源云的实例通过 SSH 登录,文档示例是 `ssh -p <端口> root@i-1.gpushare.com`(示例主机名)。公网访问走控制台"我的实例"里的"自定义服务":文档要求项目监听 `0.0.0.0:8080`,不能是 127.0.0.1;页面没有写公网地址的格式、是 http 还是 https,也没提实名或备案。服务协议禁止挖矿和恶意扫描,没有关于对外服务的专门条款,所以我判断为允许(官方自己提供这个功能),但这是"未见禁止"而不是明文许可。"如何选卡"页列出 T4、V100、A10、A100、RTX 3090 等,并给出带会员折扣的价格表,例如最高会员档下 T4 16GB 约 1.7 元、RTX 3090 24GB 约 1.53 元(单位页面未写,按小时推断,日期未写)。按量计费按秒、整点结算,关机后实例 10 天后删除。官方文档没有写 SSH 端口转发,`ssh -L` 是否可用我未核实。

Gpushare instances are reached over SSH; the doc example is `ssh -p <port> root@i-1.gpushare.com` (example host). Public access uses the console's "Custom Service" under My Instances: the doc requires the project to listen on `0.0.0.0:8080`, not 127.0.0.1; the page does not give the public address shape, whether it is http or https, nor any real-name or filing rule. The service agreement forbids mining and malicious scanning and has no dedicated clause on serving, so I rate it allowed (the vendor offers the feature itself), but that means "no prohibition found", not an explicit permission. The "how to choose a card" page lists T4, V100, A10, A100, RTX 3090 and more, with a member-discount price table; at the top member tier a T4 16GB is about 1.7 CNY and an RTX 3090 24GB about 1.53 CNY (the unit is not written, I infer per hour; the page has no date). Pay-as-you-go is billed per second and settled on the hour; a shut-down instance is deleted after 10 days. The docs do not describe SSH port forwarding, so I have not verified that `ssh -L` works.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed (功能由官方提供,协议未见禁止 / feature offered by the vendor, agreement shows no prohibition). 来源 / source: https://gpushare.com/docs/best_practices/custom/ ; https://gpushare.com/docs/product/agreement/ |
| 连接方式 / How to connect | 厂商"自定义服务"公网入口,服务须监听 `0.0.0.0:8080`,桥接需改用 8080 端口并绑定 0.0.0.0 / vendor "Custom Service" public entry; the service must listen on `0.0.0.0:8080`, so run the bridge on port 8080 bound to 0.0.0.0: https://gpushare.com/docs/best_practices/custom/ . 公网地址格式与协议未核实 / public address shape and scheme not verified. SSH 登录见 / SSH login: https://gpushare.com/docs/getting-started/login_instance/ ; 端口转发未见文档 / port forwarding is not documented. |
| 费用 / Cost | T4 16GB 约 1.7 元,RTX 3090 24GB 约 1.53 元,V100 16GB 约 1.27 元,A100 40GB 约 2.72 元(最高会员档,单位推断为每小时,页面无日期 / top member tier, unit inferred per hour, page undated): https://gpushare.com/docs/getting-started/car/ . 计费规则 / billing rules: https://gpushare.com/docs/product/price/ (按量按秒,整点结算;未充值时 1 实例 1 卡;关机 10 天后删除 / per second, hourly settlement; 1 instance with 1 GPU without a top-up; deleted 10 days after shutdown). 最低充值未写 / minimum top-up not stated. (read on 2026-11-01) |
| GPU | T4, V100, A10, A100, RTX 3090 等 / and others: https://gpushare.com/docs/getting-started/car/ |
| 实名认证 / Real-name | 文档未提 / not mentioned in the docs I read. 注册用手机号 / registration uses a mobile phone number: https://gpushare.com/docs/getting-started/quickstart/ ; 协议要求提供真实有效信息 / the agreement requires true and valid information: https://gpushare.com/docs/product/agreement/ |
| 备案 / ICP filing | 服务协议和自定义服务页均未提备案 / neither the agreement nor the custom-service page mentions filing. |
| 需确认 / To confirm | 自定义服务的实际 URL 和协议;是否只能用 8080;SSH 能否端口转发;当前价格 / the real URL and scheme of the custom service; whether only 8080 works; whether SSH forwarding works; current prices. |

#### OpenBayes (openbayes.com) 平台 / OpenBayes (openbayes.com)

OpenBayes 的"算力容器 Gear"有两条官方连接路线。一是自定义端口映射:需要实名认证,创建容器时在"端口映射"里填名称和容器端口,每个容器最多 5 个,保留端口是 22、80、5901、6006、6637、7088、8888(8787 不在其中),容器运行后得到 HTTPS 地址 `https://{user}-{port_name}.{domain}`(示例域名 gear-c1.openbayes.net),支持 HTTP 和 WebSocket,平台不加认证,所以桥接的令牌是唯一防线。二是 SSH 隧道:不需要实名,例如 `ssh -N -L localhost:7860:localhost:7860 root@ssh.openbayes.com -p31552`,SSH 只对运行中的 Jupyter 工作空间可用。定价页现在只列 RTX 5090(32GB,约 2.9 元/小时)、RTX PRO 6000(约 8 元/小时起)和 CPU(约 0.3 元/小时起),没有 T4 或 3090。服务条款禁止挖矿,并说平台可能检查容器以发现挖矿和恶意扫描;条款没有谈对外服务,但平台自己提供端口映射,所以我判断为允许。需要确认:实名流程和是否需要,免费试用额度(页面未写数额)。

OpenBayes "Gear" compute containers have two documented routes. First, custom port mapping: it needs real-name verification; you add a name and a container port under "port mapping" when creating the container, up to 5 per container, reserved ports are 22, 80, 5901, 6006, 6637, 7088 and 8888 (8787 is not reserved); once the container runs you get an HTTPS address `https://{user}-{port_name}.{domain}` (example domain gear-c1.openbayes.net), HTTP and WebSocket are supported, and the platform adds no authentication, so the bridge token is the only protection. Second, an SSH tunnel: no real-name needed, for example `ssh -N -L localhost:7860:localhost:7860 root@ssh.openbayes.com -p31552`, and SSH works only for a running Jupyter workspace. The pricing page currently lists only RTX 5090 (32GB, about 2.9 CNY per hour), RTX PRO 6000 (about 8 CNY per hour and up) and CPU (about 0.3 CNY per hour and up), with no T4 or 3090. The terms forbid mining and say the platform may inspect containers to detect mining and malicious scanning; they say nothing about serving, but the platform itself offers port mapping, so I rate it allowed. Confirm: the real-name procedure, and the free-trial amount (the page gives no number).

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed (端口映射由官方提供,服务条款禁止挖矿和恶意扫描,未谈对外服务 / port mapping is offered by the vendor, terms forbid mining and malicious scanning and are silent on serving). 来源 / source: https://openbayes.com/docs/gear/expose-service ; https://openbayes.com/tos |
| 连接方式 / How to connect | (a) 端口映射,https / port mapping, https: `https://{user}-{port_name}.{domain}` 或 / or `https://{user}-{jobid}-{port_number}.{domain}`, 需实名 / needs real-name: https://openbayes.com/docs/gear/expose-service . (b) SSH 隧道,http 回环 / SSH tunnel, http loopback: `ssh -N -L localhost:8787:localhost:8787 root@ssh.openbayes.com -p<端口/port>` (官方示例用 7860,8787 是我的替换 / the vendor example uses 7860, 8787 is my substitution): https://openbayes.com/docs/gear/ssh-tunnel ; SSH 仅限运行中的 Jupyter 工作空间 / SSH only for a running Jupyter workspace: https://openbayes.com/docs/gear/ssh |
| 费用 / Cost | RTX 5090 约 2.9 元/小时;RTX PRO 6000 约 8 元/小时起;CPU 约 0.3 元/小时起;页面有"免费试用"和"满 10 元赠 10 元券"的促销,额度未写 / RTX 5090 about 2.9 CNY per hour; RTX PRO 6000 from about 8; CPU from about 0.3; the page shows a free trial and a "spend 10, get a 10 coupon" promotion without amounts: https://openbayes.com/pricing . 按量按小时计费,也有包日/周/月 / hourly pay-as-you-go plus day/week/month plans: https://openbayes.com/docs/payment-methods (read on 2026-11-01) |
| GPU | RTX 5090, RTX PRO 6000 (定价页 / pricing page). 其他型号未核实 / other models not verified. |
| 实名认证 / Real-name | 端口映射需要 / needed for port mapping; SSH 隧道不需要 / not needed for the SSH tunnel (https://openbayes.com/docs/gear/expose-service ; https://openbayes.com/docs/gear/ssh-tunnel). 流程未读 / procedure not read. |
| 备案 / ICP filing | 服务条款和端口映射页均未提 / neither the terms nor the port-mapping page mentions filing. |
| 需确认 / To confirm | 实名流程;免费额度数额;容器空闲与自动清理规则(算力容器无执行时会被清理,Jupyter 工作空间有空闲关机规则,见 https://openbayes.com/docs/gear/limitation 和 https://openbayes.com/docs/gear/faq ) / the real-name procedure; free quota amount; container idle and cleanup rules (see the two URLs). |

#### 趋动云 (virtaicloud.com) - 不是 OpenBayes / not OpenBayes

趋动云的首页(运营方页脚写 virtaitech.com)挂着一则公告,标题说"开发、训练、推理等功能(模型广场除外)停止服务"。公告正文网址返回 403,我读不到日期和细节。因此我没有继续查它的 GPU、价格和端口,也不建议把它当作桥接的运行平台。使用前请自己在其官网确认这则公告的内容。

The 趋动云 home page (the footer names virtaitech.com as the operator) shows a notice whose title says that the development, training and inference functions (model marketplace excepted) are being discontinued. The notice body URL returned 403, so I could not read dates or details. I therefore did not pursue its GPUs, prices or ports, and do not recommend it as a bridge host. Check the notice yourself on its site before any use.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 不明确 / unclear (开发、训练、推理功能的停服公告,正文未读 / a notice about discontinuing development, training and inference, body not read). 来源 / source: https://www.virtaicloud.com/ |
| 连接方式 / How to connect | 未核实 / not verified |
| 费用 / Cost | 未核实 / not verified |

#### 阿里云 PAI-DSW (交互式建模) / Alibaba Cloud PAI-DSW

PAI-DSW 是阿里云的交互式建模实例(Notebook、WebIDE、Terminal)。公共资源按量付费,示例规格是 `ecs.gn7i-c8g1.2xlarge`(1 张 A10,8 vCPU,30 GiB),每个主账号每个地域最多 2 张 GPU 卡,免费试用抵扣包只覆盖三种规格(`ecs.g6.xlarge`、`ecs.gn7i-c8g1.2xlarge`、`ecs.gn6v-c8g1.2xlarge`)。官方有"自定义服务"公网访问功能,但定位是开发测试(生产请用 PAI-EAS):需要 VPC、EIP、NAT 网关(DNAT)和安全组入站规则,每实例最多 5 个服务,地址形如 `EIP:端口`,官方示例用 http,没有 TLS 说明,也没有内置认证;NAT 网关和 EIP 单独计费,实例停止后仍继续收费。SSH 直连需要内网 DNS 解析、安全组放通 22,公网访问同样要 DNAT 加 EIP,官方只提供 root 登录;`ssh -L` 官方页没写。免费试用实例默认有闲置自动停止(CPU 和 GPU 连续约 3 小时低于阈值)。GPU 单价和免费额度数额页面没写,实名认证页面没列为通用前提,但新账号可能被风控拒绝。

PAI-DSW is Alibaba Cloud's interactive modelling instance (Notebook, WebIDE, Terminal). Public resources are pay-as-you-go; the example spec is `ecs.gn7i-c8g1.2xlarge` (1 A10, 8 vCPU, 30 GiB), each main account gets at most 2 GPU cards per region, and the free-trial deduction package covers only three specs (`ecs.g6.xlarge`, `ecs.gn7i-c8g1.2xlarge`, `ecs.gn6v-c8g1.2xlarge`). There is an official "custom service" public-access feature, but it is positioned for development and testing (use PAI-EAS for production): it needs a VPC, an EIP, a NAT gateway (DNAT) and a security-group inbound rule, allows up to 5 services per instance, the address looks like `EIP:port`, the official examples use http with no TLS guidance and no built-in authentication; the NAT gateway and EIP are billed separately and keep billing after the instance stops. SSH direct connection needs intranet DNS resolution and port 22 in the security group, public access again needs DNAT plus EIP, and only root login is offered; the official page does not mention `ssh -L`. Free-trial instances have an idle auto-stop by default (CPU and GPU below a threshold for about 3 hours). The pages give no GPU unit price or free-quota amount; real-name verification is not listed as a general prerequisite, but a new unverified account may be rejected by risk control.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed, 仅限开发测试 / development and testing only (官方说生产请用 PAI-EAS / the vendor says use PAI-EAS for production). 来源 / source: https://help.aliyun.com/zh/pai/custom-services-access-configurations |
| 连接方式 / How to connect | (a) 自定义服务 `http://<EIP>:<端口/port>` (EIP + NAT 网关 + 安全组;明文 http,https 页面不能调用 / plain http, an https page cannot call it): https://help.aliyun.com/zh/pai/custom-services-access-configurations . (b) SSH 直连 `ssh root@<公网IP/public IP> -p <端口/port>`, 公网需 DNAT + EIP / public access needs DNAT plus EIP: https://help.aliyun.com/zh/pai/dsw-direct-connection ; 再用通用 OpenSSH `-L` 转发到 `http://127.0.0.1:8787`,该页未写转发,sshd 是否允许 TCP 转发未核实 / then a generic OpenSSH `-L` forward to `http://127.0.0.1:8787`; the page does not describe forwarding and whether sshd allows TCP forwarding is not verified. |
| 费用 / Cost | GPU 单价只在控制台购买页,未核实 / GPU unit price only on the console purchase page, not verified: https://help.aliyun.com/zh/pai/product-overview/dsw-billing-description . 按分钟计费、每小时出账;运行中即使闲置也计费;NAT 网关和 EIP 另计,实例停止后仍计费;扩容系统盘停止后仍计费 / billed per minute, billed hourly; a running idle instance is billed; NAT gateway and EIP are billed separately and keep billing after stop; an expanded system disk keeps billing after stop. 公共资源停止后环境保留 15 天,之后释放 / a stopped public-resource instance keeps its environment for 15 days: https://help.aliyun.com/zh/pai/access-dsw-instance (read on 2026-11-01) |
| GPU | `ecs.gn7i-c8g1.2xlarge` (A10), `ecs.gn6v-c8g1.2xlarge`, 另有其他规格,各地域库存未列 / other specs exist, stock per region not listed: https://help.aliyun.com/zh/pai/create-and-manage-dsw-instances |
| 实名认证 / Real-name | 页面未列为通用前提;建议在创建被风控拒绝时确认实名 / not listed as a general prerequisite; the page suggests confirming it if creation is rejected by risk control: https://help.aliyun.com/zh/pai/create-and-manage-dsw-instances |
| 备案 / ICP filing | 自定义服务页未提备案或实名 / the custom-services page mentions neither filing nor real-name. 阿里云备案一般规则见下文"阿里云 GPU ECS" / see the general Alibaba Cloud filing rules under "Alibaba Cloud GPU ECS" below. |
| 需确认 / To confirm | 地域与规格库存、GPU 配额;是否愿意为 EIP 和 NAT 网关付费;sshd 是否允许端口转发;闲置自动停止的设置(见 https://help.aliyun.com/zh/pai/faq-about-dsw ) / region and spec stock, GPU quota; willingness to pay for EIP and NAT; whether sshd allows forwarding; the idle auto-stop setting. |

#### 阿里云 GPU ECS / Alibaba Cloud GPU ECS

GPU ECS 是完整的虚拟机。官方规格族页列出 gn6i(T4 16GB,最小 `ecs.gn6i-c4g1.xlarge`)、gn7i(A10 24GB,`ecs.gn7i-c8g1.2xlarge`)、gn6v(V100 16GB)、gn6e(V100 32GB)、gn8is(L20 48GB,限地域)等。购买中国内地地域的实例必须先完成实名认证,按量付费时账户现金加代金券至少 100 元;香港节点不需要这项实名登记。公网 IP 在购买时勾选并选带宽计费方式;安全组默认只放行 22、3389 和 ICMP,其他端口要自己加入站规则,TCP 25 默认受限。备案:阿里云备案 FAQ 说只买云服务器、不使用域名,不需要备案;备案义务跟"域名解析到内地服务器并开通 Web 服务"挂钩,带域名用 8080 等非标准端口访问内地服务器仍需备案;我没有找到官方页面专门说"只用 IP、非 Web 端口"。所以最稳妥的做法是安全组只开 22,用 `ssh -L` 转发,不开公网端口。GPU 价格我没能读到官方数字。

GPU ECS is a full virtual machine. The official instance-family page lists gn6i (T4 16GB, smallest `ecs.gn6i-c4g1.xlarge`), gn7i (A10 24GB, `ecs.gn7i-c8g1.2xlarge`), gn6v (V100 16GB), gn6e (V100 32GB), gn8is (L20 48GB, limited regions) and more. Buying in a mainland-China region requires real-name verification first, and for pay-as-you-go the cash balance plus vouchers must be at least 100 CNY; Hong Kong nodes do not need this real-name registration. A public IP is ticked at purchase with a bandwidth billing mode; the default security group opens only 22, 3389 and ICMP, other ports need your own inbound rule, and TCP 25 is restricted by default. Filing: the Alibaba Cloud filing FAQ says buying only a cloud server without using a domain needs no filing; the obligation is tied to a domain resolving to a mainland server with a web service, and a domain reaching a mainland server on a non-standard port such as 8080 still needs filing; I found no official page that addresses "IP only, non-web port" directly. The safest setup is therefore a security group with only port 22 open and an `ssh -L` forward, with no public port. I could not read an official GPU price.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed (通用虚拟机,官方文档本身就讲在实例上托管网站 / a general-purpose VM, the official docs themselves cover hosting a website on an instance; 未逐条读阿里云总服务条款 / I did not read the general service terms clause by clause). 来源 / source: https://help.aliyun.com/en/ecs/support/what-do-i-do-if-i-cannot-access-a-website-hosted-on-an-instance |
| 连接方式 / How to connect | SSH 端口转发 / SSH local forward: `ssh -L 8787:127.0.0.1:8787 root@<公网IP/public IP>`,安全组只需放行 22 / the security group only needs port 22 (官方页讲安全组和公网 IP,`-L` 是通用 OpenSSH 用法,官方页未写 / the official pages cover security groups and public IP, `-L` is generic OpenSSH usage not described there): https://help.aliyun.com/zh/ecs/user-guide/security-group-rules ; https://help.aliyun.com/zh/ecs/user-guide/public-ip-address . 直接公网 / direct public: 入站规则放通 TCP 8787 并限制源 IP,地址 `http://<公网IP>:8787` 是明文 http,https 页面不能调用 / add an inbound TCP 8787 rule restricted by source IP; `http://<public IP>:8787` is plain http and an https page cannot call it. 固定公网 IP 可能丢失,economical 模式停机会回收公网 IP / the fixed public IP can be lost and an economical-mode stop reclaims it: https://help.aliyun.com/zh/ecs/user-guide/public-ip-address |
| 费用 / Cost | 官方 GPU 价格未核实(价格页重定向或需脚本渲染) / official GPU prices not verified (price pages redirect or need scripts). 按量付费按秒计费 / pay-as-you-go is per second: https://help.aliyun.com/zh/ecs/user-guide/create-an-instance-by-using-the-wizard . 公网只收出方向带宽或流量 / public network charges only outbound bandwidth or traffic. (read on 2026-11-01) |
| GPU | gn6i (T4), gn7i (A10), gn6v/gn6e (V100), gn7e (80GB), gn8is (L20, 限地域 / limited regions): https://help.aliyun.com/zh/ecs/user-guide/gpu-accelerated-compute-optimized-and-vgpu-accelerated-instance-families-1 . 各地域可购规格见 / per-region availability: https://help.aliyun.com/zh/ecs/user-guide/regions-and-zones |
| 实名认证 / Real-name | 中国内地地域必须 / required for mainland regions: https://help.aliyun.com/zh/ecs/user-guide/create-an-instance-by-using-the-wizard . 国际站账号需做"实名登记"(护照或驾照,不接受身份证原件) / an international-site account needs "real-name registration" (passport or driver's license, an ID card original is not accepted); 香港节点免登记 / Hong Kong nodes are exempt: https://help.aliyun.com/zh/user-center/real-name-registration-for-purchasing-an-ecs-instance-in-the-chinese-mainland |
| 备案 / ICP filing | 只买服务器、不用域名:不需要 / server only, no domain: not needed: https://help.aliyun.com/zh/icp-filing/basic-icp-service/product-overview/faq-about-icp-filing-applications-in-different-scenarios . 域名解析到内地服务器并开通 Web 服务:需要;非标准端口不改变义务 / a domain resolving to a mainland server with a web service: needed; a non-standard port does not change the obligation: https://help.aliyun.com/zh/icp-filing/basic-icp-service/user-guide/icp-filing-server-access-information-check . "仅 IP、非 Web 端口"官方页面未写 / "IP only, non-web port" is not addressed by the pages I read. |
| 需确认 / To confirm | 官方 GPU 价格、地域库存、GPU 配额;控制台里实例是否分配了公网 IP / official GPU price, region stock, GPU quota; whether the instance got a public IP in your console. |

#### 腾讯云 GPU 云服务器 (CVM) / Tencent Cloud GPU CVM

腾讯云 GPU 云服务器是完整虚拟机。官方在售的计算型有 PNV4(A10)、GT4(A100)、GN10Xp 和 GN10X(V100)、GN7(T4)、GI3X(T4,推理型),以及较老的 GN8(P40)和 GN6/GN6S(P4);部分型号地域有限。购买前必须完成实名认证;公网 IP 是可选项,创建时分配或之后配置弹性公网 IP,带宽按带宽或按流量计费;安全组是必选项,没有规则时默认拒绝所有入站和出站,购买页提示要确保放通 22。GPU 机型支持按量计费,并有关机不收费政策,但具体适用条件在另一份 CVM 文档里,我没读到。备案:腾讯云备案 FAQ 说不使用域名、只有一台云服务器时不需要备案,仅用公网 IP 测试可暂不备案,但域名解析到内地 CVM 而未备案会被监测系统阻断。官方 GPU 单价我没读到。建议同样只开 22,用 `ssh -L` 转发。

Tencent Cloud GPU CVM is a full virtual machine. The compute types currently on sale are PNV4 (A10), GT4 (A100), GN10Xp and GN10X (V100), GN7 (T4) and GI3X (T4, inference), plus older GN8 (P40) and GN6/GN6S (P4); some models are limited to a few regions. Real-name verification is required before buying; a public IP is optional (assigned at creation or an elastic IP attached later) with bandwidth or traffic billing; a security group is mandatory, an empty one denies all inbound and outbound traffic, and the purchase page reminds you to keep port 22 open. GPU instances support pay-as-you-go and a shutdown-no-charge policy, but its conditions are in another CVM document I did not read. Filing: the Tencent Cloud filing FAQ says a cloud server with no domain pointing at it needs no filing, testing through the public IP can wait, but a domain resolving to a mainland CVM without filing is blocked by the monitoring system. I did not read an official GPU unit price. I again suggest opening only port 22 and using an `ssh -L` forward.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed (通用虚拟机,官方文档讲开放端口和安全组 / a general-purpose VM, the official docs cover opening ports and security groups; 未读腾讯云总服务条款 / the general service terms were not read). 来源 / source: https://cloud.tencent.com/document/product/213/15377 |
| 连接方式 / How to connect | SSH 本地转发 `ssh -L 8787:127.0.0.1:8787 <用户/user>@<公网IP/public IP>`,安全组放通 22(`-L` 是通用 OpenSSH 用法,官方页未写 / generic OpenSSH usage, not described by the vendor page): https://cloud.tencent.com/document/product/213/10517 . 直接公网 / direct public: 安全组入站放通 TCP 8787,明文 http,https 页面不能调用 / open inbound TCP 8787, plain http, an https page cannot call it: https://cloud.tencent.com/document/product/213/15377 |
| 费用 / Cost | 官方 GPU 价格未核实 / official GPU prices not verified (https://cloud.tencent.com/document/product/213/2176 no GPU prices; https://cloud.tencent.com/document/product/560/8025 no price table). 计费方式 / billing modes: 包年包月、按量计费、竞价实例、包销 / subscription, pay-as-you-go, spot, committed (https://cloud.tencent.com/document/product/560/8025 ). (read on 2026-11-01) |
| GPU | PNV4 (A10), GT4 (A100), GN10Xp/GN10X (V100), GN7 (T4), GI3X (T4), GN8 (P40), GN6/GN6S (P4); PNV5b/PNV6 等需白名单 / need an allow-list: https://cloud.tencent.com/document/product/560/30130 |
| 实名认证 / Real-name | 必须 / required: https://cloud.tencent.com/document/product/213/10517 |
| 备案 / ICP filing | 不用域名:不需要;域名解析到内地 CVM:先备案,否则被阻断;香港服务器无需备案 / no domain: not needed; a domain pointing to a mainland CVM: file first or it is blocked; Hong Kong servers need no filing: https://cloud.tencent.com/document/product/243/19630 . 该页未谈"仅 IP 的非经营性服务" / that page does not discuss IP-only non-commercial services. |
| 需确认 / To confirm | 官方价格和地域库存;GPU 配额;关机不收费的适用条件 / official price and region stock; GPU quota; conditions of shutdown-no-charge. |

#### 腾讯云 HAI (高性能应用服务,GPU 应用服务) / Tencent Cloud HAI

HAI 是预装环境的 GPU 应用实例,官方称它面向开发、调试和单实例工作负载,访问入口有 JupyterLab、WebUI、终端。算力套餐在官方特惠页列了两档:GPU 基础型(16GB 显存,8+ TFlops,8 核 32GB,约 1.2 元/小时起)和 GPU 进阶型(32GB 显存,15+ TFlops,8 到 10 核 40GB,约 3.6 元/小时起),页面没有写 GPU 型号名。官方默认端口页列出 SSH 22、JupyterLab 6888、Ollama 6399 等,并说可用端口规则控制公网和私网访问,但"编辑端口规则"页我没读到,自定义 TCP 端口的细节未核实。按量计费精确到秒,关机不计算力费用但云盘照收,每个套餐含 80GB 云盘、每月 500GB 出方向流量和 10 Mbps 带宽,超出部分约 0.8 元/GB。购买前必须完成实名认证。HAI 是否允许自建长期服务、是否有 root SSH,官方页面没有直接回答,所以我判断为不明确。

HAI is a pre-configured GPU application instance; the vendor describes it as aimed at development, debugging and single-instance workloads, with JupyterLab, WebUI and terminal as entry points. The promotion page lists two compute packages: GPU Basic (16GB VRAM, 8+ TFlops, 8 cores and 32GB, from about 1.2 CNY per hour) and GPU Advanced (32GB VRAM, 15+ TFlops, 8 to 10 cores and 40GB, from about 3.6 CNY per hour); the page gives no GPU model name. The default-ports page lists SSH 22, JupyterLab 6888, Ollama 6399 and others, and says port rules control public and private access, but I did not read the "edit port rules" page, so custom TCP port details are not verified. Pay-as-you-go is per second; shutdown stops compute charges but the disk keeps billing; each package includes an 80GB disk, 500GB of outbound traffic per month and 10 Mbps bandwidth, with overage about 0.8 CNY per GB. Real-name verification is required before buying. Whether HAI allows a self-built long-lived service and whether it gives root SSH is not answered directly by the pages I read, so I rate it unclear.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 不明确 / unclear (官方定位是开发调试和单实例负载,未见对自建长期服务的明文说明 / positioned for development and debugging, no explicit statement about self-built long-lived services). 来源 / source: https://cloud.tencent.com/document/product/1721/101024 |
| 连接方式 / How to connect | 端口规则可放通公网访问,默认端口含 SSH 22 / port rules can allow public access, default ports include SSH 22: https://cloud.tencent.com/document/product/1721/102531 . 若确认有 SSH,则 `ssh -L 8787:127.0.0.1:8787` 后用 `http://127.0.0.1:8787`;SSH 与 root 登录未核实 / if SSH is confirmed, `ssh -L 8787:127.0.0.1:8787` then `http://127.0.0.1:8787`; SSH and root login are not verified. 直接公网为明文 http / direct public access would be plain http. |
| 费用 / Cost | 基础型约 1.2 元/小时起;进阶型约 3.6 元/小时起 / Basic from about 1.2 CNY per hour; Advanced from about 3.6: https://cloud.tencent.com/act/pro/hai . 计费规则 / billing rules: https://cloud.tencent.com/document/product/1721/101029 . 页面另有体验券,价格显示为空 / vouchers exist, their prices are blank on the page. (read on 2026-11-01) |
| GPU | 16GB 或 32GB 显存套餐,型号名未写 / 16GB or 32GB VRAM packages, model names not given: https://cloud.tencent.com/act/pro/hai |
| 实名认证 / Real-name | 必须 / required: https://cloud.tencent.com/document/product/1721/101030 |
| 备案 / ICP filing | HAI 文档没有提到,通用规则见腾讯云 GPU CVM 一节。 / HAI docs do not mention it; the general rule is in the Tencent Cloud GPU CVM section. |
| 需确认 / To confirm | 是否提供 root SSH 和自定义 TCP 端口;GPU 型号;服务条款对自建服务的态度 / whether root SSH and custom TCP ports exist; the GPU model; the terms' stance on self-built services. |

#### 华为云 ModelArts Notebook / Huawei Cloud ModelArts Notebook

官方限制写得很清楚:Notebook 不支持开放端口对外提供服务;新版页面还说 Notebook 主要用于代码开发和业务调测,不支持长时间稳定运行,不得用于生产业务。所以它不适合当桥接的运行平台,我判定为禁止对外服务。Notebook 支持 SSH 远程开发(需创建时开启、选密钥对,OpenSSH 8.0 以上,建议连接数不超过 10,SSH 开关一旦打开不能关闭),这是给本地 IDE 用的;SSH 端口转发在官方 SSH 页没有提到。华为自己的快速入门用 Gradio 示例,通过 `https://authoring-modelarts.{region}.huaweicloud.com/{instance_id}/proxy/7890/` 之类的 `/proxy/<端口>/` 路径在控制台会话里查看页面,但那个示例用的是昇腾 NPU 不是 GPU,而且与上面的限制并存,所以我不建议拿它来给外部网页提供服务。公共资源池可选 GPU,但具体型号和单价我没读到;计费按 Notebook 运行时长。

The official restriction is explicit: Notebook does not support opening ports for external services; the newer page adds that Notebook is mainly for code development and debugging, does not support long-term stable running, and must not be used for production. It is therefore not suitable as a bridge host, and I rate external serving as forbidden. Notebook supports SSH remote development (enabled at creation with a key pair, OpenSSH 8.0 or later, at most about 10 connections, and the SSH switch cannot be turned off once on); this is meant for a local IDE, and the official SSH page does not mention SSH port forwarding. Huawei's own quickstart uses a Gradio demo reached through a `/proxy/<port>/` path such as `https://authoring-modelarts.{region}.huaweicloud.com/{instance_id}/proxy/7890/` to view the page from the console session, but that demo uses Ascend NPUs rather than GPUs and sits beside the restriction above, so I do not recommend using it to serve an outside web page. Public resource pools offer GPUs, but I did not read the models or unit prices; billing is by Notebook run time.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 禁止 / forbidden for external serving; 仅开发调测 / development and debugging only. 来源 / source: https://support.huaweicloud.com/intl/es-us/usermanual-standard-modelarts/devtool-modelarts_0004.html (限制章节 / constraints section); https://support.huaweicloud.com/devtool-modelarts/devtool-modelarts_0002.html (开发调测,不支持长时间稳定运行 / development and debugging, no long-term stable running) |
| 连接方式 / How to connect | 不建议 / not recommended. SSH 仅用于本地 IDE,地址在实例基本信息里 / SSH is for a local IDE, the address is in the instance's basic info: https://support.huaweicloud.com/devtool-modelarts/devtool-modelarts_0021.html . 厂商示例的代理路径 / the vendor demo's proxy path: https://support.huaweicloud.com/qs-modelarts/modelarts_06_0034.html |
| 费用 / Cost | 价格未核实 / prices not verified. 公共资源池按 Notebook 运行时长按量计费 / public pool pay-as-you-go by run time: https://support.huaweicloud.com/qs-modelarts/modelarts_06_0034.html . 自动停止可能延迟 2 到 5 分钟且延迟期间计费;停止后仅 `/home/ma-user/work` 和 `/data` 下动态挂载目录的数据保留 / auto-stop can lag 2 to 5 minutes and the lag is billed; after stop only `/home/ma-user/work` and dynamically mounted directories under `/data` are kept: https://support.huaweicloud.com/devtool-modelarts/devtool-modelarts_0006.html . (read on 2026-11-01) |
| GPU | 公共资源池可选 CPU 或 GPU,型号取决于镜像;专属池规格例如 `modelarts.vm.gpu._tnt004u8` / public pools offer CPU or GPU depending on the image; a dedicated-pool example is `modelarts.vm.gpu._tnt004u8`: https://support.huaweicloud.com/intl/es-us/usermanual-standard-modelarts/devtool-modelarts_0004.html |
| 实名认证 / Real-name | 使用中国内地地域资源需要 / required for mainland-region resources (账号 FAQ 未单独点名 ModelArts / the FAQ does not name ModelArts): https://support.huaweicloud.com/intl/zh-cn/account_faq/zh-cn_topic_0142752673.html |
| 备案 / ICP filing | 见下一节 / see the next section. |
| 需确认 / To confirm | 如仍要尝试:是否允许来自另一站点的跨域请求并只凭令牌访问(代理路径可能要求控制台登录,文档未写) / if you still try: whether the proxy path accepts cross-origin calls with only the bridge token (it may require the console login, not documented). 我的建议是不要用 Notebook 当桥接 / my recommendation is not to use Notebook as the bridge host. |

#### 华为云 GPU ECS / Huawei Cloud GPU ECS

华为云 GPU 加速型 ECS 是完整虚拟机。官方规格页把 G6(T4,`g6.xlarge.4`,16GiB 显存)、Pi2(T4,`pi2.2xlarge.4`)和 P2s(V100 32GiB,`p2s.2xlarge.8`)标为主售;停机的 GPU 实例不收 vCPU、内存、镜像和 GPU 的费用,但系统盘照收,且停机后资源可能被回收导致无法再启动。华为官方最佳实践用 `pi2.2xlarge.4` 加弹性公网 IP,在安全组放通 TCP 8000(来源 0.0.0.0/0)部署 Stable Diffusion WebUI,说明在 ECS 上开放端口运行服务是官方做法。使用中国内地地域资源需要实名认证。备案:华为云备案 FAQ 比较严格,说只要使用中国大陆节点服务器开办网站或 App 就要备案,并明确回答"只用 IP 访问也需要",该 FAQ 针对网站和 App,对"自用 API"没有说;香港和境外节点不需要备案。因此同样建议只开 22,用 `ssh -L` 转发。GPU 价格我没读到。

Huawei Cloud GPU-accelerated ECS is a full virtual machine. The official flavor page marks G6 (T4, `g6.xlarge.4`, 16GiB VRAM), Pi2 (T4, `pi2.2xlarge.4`) and P2s (V100 32GiB, `p2s.2xlarge.8`) as main-sale families; a stopped GPU instance is not billed for vCPU, memory, image or GPU, but the system disk still is, and a stopped instance may lose its resources and fail to restart. Huawei's own best practice deploys a Stable Diffusion WebUI on `pi2.2xlarge.4` with an elastic public IP and a security-group rule opening TCP 8000 (source 0.0.0.0/0), so exposing a port on an ECS is the documented way. Real-name verification is required for mainland-region resources. Filing: the Huawei Cloud filing FAQ is strict: any website or app on a mainland node needs filing, and it explicitly answers that IP-only access needs it too; the FAQ is written for websites and apps and does not discuss a private API; Hong Kong and overseas nodes need no filing. I again suggest opening only port 22 and using an `ssh -L` forward. I did not read a GPU price.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed (官方最佳实践在 GPU ECS 上开放端口运行 WebUI / the official best practice runs a WebUI on a GPU ECS with an open port; 未读华为云总服务条款 / the general service terms were not read). 来源 / source: https://support.huaweicloud.com/bestpractice-ecs/ecs_bp_6019.html |
| 连接方式 / How to connect | 本地转发:`ssh -L 8787:127.0.0.1:8787 root@<EIP>`(通用 OpenSSH 用法,官方页没有写),安全组放通 22;直接公网:EIP 加安全组放通 TCP 8787,地址 `http://<EIP>:8787` 是明文 http;参考 https://support.huaweicloud.com/bestpractice-ecs/ecs_bp_6019.html。 / Local forward: `ssh -L 8787:127.0.0.1:8787 root@<EIP>` (generic OpenSSH usage, not described by the vendor page), with port 22 open in the security group; direct public: an EIP plus an inbound TCP 8787 rule, `http://<EIP>:8787` is plain http; see https://support.huaweicloud.com/bestpractice-ecs/ecs_bp_6019.html. |
| 费用 / Cost | GPU 价格未核实 / GPU prices not verified (https://www.huaweicloud.com/product/gpu.html 只列计费模式:按需、包周期、竞价 / lists only the billing modes: on-demand, subscription, spot). 停机 GPU 实例不收 GPU 费但系统盘照收 / a stopped GPU instance has no GPU charge but the system disk is billed: https://support.huaweicloud.com/productdesc-ecs/ecs_01_0045.html . EIP 示例为按流量计费、带宽 300 Mbit/s / the EIP in the example is traffic-billed at 300 Mbit/s. (read on 2026-11-01) |
| GPU | 型号 / Models: G6 (T4), Pi2 (T4), P2s (V100 32GiB), P2v (V100 16GiB), G5 (V100), P1 (P100), Pi1 (P4): https://support.huaweicloud.com/productdesc-ecs/ecs_01_0045.html |
| 实名认证 / Real-name | 购买或使用中国内地地域资源需要 / required for resources in mainland regions: https://support.huaweicloud.com/intl/zh-cn/account_faq/zh-cn_topic_0142752673.html . 个人可用支付宝、银行卡、人脸或证件 / individuals can use Alipay, bank card, face recognition or documents: https://support.huaweicloud.com/usermanual-account/account_auth_00001.html (该页仅来自搜索摘要,未抓取全文 / seen only as a search snippet, not fetched in full) |
| 备案 / ICP filing | FAQ 称使用中国大陆节点服务器开办网站或 App 需要备案,并明确说 IP 访问也需要;香港和境外节点不需要 / the FAQ says a website or app on a mainland node needs filing and explicitly says IP access needs it too; Hong Kong and overseas nodes do not: https://support.huaweicloud.com/icp_faq/icp_05_0145.html . 对非网站用途(例如私人 API)未作说明 / non-website use such as a private API is not addressed. |
| 需确认 / To confirm | 价格、配额、地域库存;是否愿意只靠 SSH 转发而不开公网端口;若需要公网端口,先向华为云客服确认自用 API 是否算"网站或 App" / price, quota, region stock; whether you accept SSH forwarding with no public port; if you need a public port, ask Huawei Cloud whether a private API counts as a "website or app". |

#### 跨平台规则 / Cross-platform rules

实名认证:腾讯云、华为云(内地地域)和阿里云(内地地域)买服务器前必须实名认证;AutoDL 对自定义服务必须实名,并要求公网端口映射用企业认证;OpenBayes 的端口映射必须实名,SSH 隧道不必;恒源云和阿里云 PAI-DSW 的页面没有把实名列为前提(未核实,不等于不需要)。

Real-name: Tencent Cloud, Huawei Cloud (mainland regions) and Alibaba Cloud (mainland regions) require it before buying a server; AutoDL requires it for the custom service and enterprise certification for the public port mapping; OpenBayes requires it for port mapping but not for the SSH tunnel; the Gpushare and PAI-DSW pages I read do not list it as a prerequisite (not verified, which is not the same as not needed).

备案:三家公有云的说法不完全一致。阿里云和腾讯云的 FAQ 都写"只买服务器、不用域名,不需要备案",问题出在把域名解析到内地服务器并开通 Web 服务,以及非标准端口也不免除;华为云的 FAQ 更严,明确说只用 IP 访问也要备案,但针对的是网站和 App。三家都没有明文谈"只有自己用的非网站端口"。凡是用 SSH 转发、不开公网端口、不绑域名的方案,不触及这些文字;这是我的推断,不是厂商原话。香港节点(阿里云、腾讯云、华为云)按各自 FAQ 不要求 ICP 备案,但我没有核实香港是否有合适的 GPU 库存。

Filing: the three public clouds do not word it the same way. The Alibaba Cloud and Tencent Cloud FAQs both say that buying only a server without a domain needs no filing, and the trouble starts when a domain resolves to a mainland server with a web service, where non-standard ports do not exempt you; the Huawei Cloud FAQ is stricter and says IP-only access needs filing too, but it speaks about websites and apps. None of them discusses a private non-web port used only by its owner. Setups that use an SSH forward, open no public port and bind no domain do not touch these texts; that is my inference, not the vendors' words. Hong Kong nodes (Alibaba Cloud, Tencent Cloud, Huawei Cloud) need no ICP filing according to each FAQ, but I did not verify GPU stock in Hong Kong.

https 与 http:所有"公网 IP + 端口"的做法(阿里云 DSW 的 EIP、各家 ECS/CVM 的公网端口、腾讯云 HAI 端口规则、恒源云未核实)官方文档示例都是明文 http,https 页面不能调用。只有 OpenBayes 端口映射(https)和 AutoDL 企业认证后的示例地址(https,端口 8443)是 https。SSH 转发给出的 `http://127.0.0.1:8787` 属于浏览器对回环地址的例外,这是通用浏览器行为,不是厂商文档的内容,Safari 和较新 Chrome 的本地网络提示我没有核实。

Http versus https: every "public IP plus port" route (PAI-DSW EIP, public ports on ECS/CVM, Tencent HAI port rules, Gpushare unverified) is shown with plain http in the official examples, so an https page cannot call it. Only the OpenBayes port mapping (https) and the AutoDL example address after enterprise certification (https, port 8443) are https. The `http://127.0.0.1:8787` that an SSH forward gives relies on the browser's loopback exception; that is general browser behaviour, not vendor documentation, and I did not verify Safari or the newer Chrome local-network prompts.

#### 读法与两条通用提示 / How to read this, and two general points

中文: "服务器用途"一栏只代表该平台自己的条款或文档的说法,页面没写的一律写"不明确"或"未核实"。第一条通用提示:https 页面不能调用普通 http 地址。W3C 的混合内容规范把 XMLHttpRequest 这类请求列为可拦截内容,fetch 也一样不会被自动升级到 https;只有"潜在可信"的地址例外,MDN 列出的可信主机包括 localhost、*.localhost、127.0.0.0/8 和 ::1。所以凡是平台只给出 http 公网地址的情况,面板里填 `http://127.0.0.1:8787` 并配合 SSH 转发,是不需要自备证书的做法;各浏览器对回环地址的具体表现(例如 Safari)本次未核实。第二条:凡是平台条款禁止隧道、代理或内网穿透的地方,本文不给任何绕过办法,只写平台自己文档里的路线,或者建议只做批量分析(见 docs/COMPUTE-PLATFORMS.md)。

English: The "Serving allowed" row only reports what each platform's own terms or docs say; anything the pages do not state is marked "unclear" or "not verified". General point one: an https page cannot call a plain http address. The W3C mixed-content spec lists XMLHttpRequest-type requests as blockable and does not auto-upgrade them; the exception is a "potentially trustworthy" URL, and MDN lists localhost, *.localhost, 127.0.0.0/8 and ::1 as trustworthy. So wherever a platform only offers a public http address, typing `http://127.0.0.1:8787` into the panel together with an SSH forward is the route that needs no certificate of your own; how each browser treats loopback in practice (for example Safari) was not verified. General point two: where a platform's terms forbid tunnels, proxies or intranet-penetration tools, this file gives no workaround. It only describes the platform's own documented route, or recommends batch analysis only (see docs/COMPUTE-PLATFORMS.md).

#### 百度 AI Studio / Baidu AI Studio

中文: GPU:官方"算力卡"文档(页面更新日期 2024-03-20)写明 Notebook 项目使用国产 DCU、Tesla V100 和 A100;每点算力卡可用 V100 16GB 2 小时或 V100 32GB 1 小时,每天运行项目送 8 点(约 16 小时 V100 16GB)。关闭浏览器后资源再运行 10 分钟就被中止,而用户协议禁止在未登录时运行或启动进程(条款 2(7)),并写明只支持飞桨框架,运行平台不支持的项目或框架可能被停止(条款 1),所以把免费笔记本当常驻 KataGo 桥属于"不明确",不要这样用,免费额度只做批量分析。平台自己文档里的服务路线是"项目服务部署"(页面更新 2025-07-01):把 Notebook 项目发布成公网可调用的 API,服务必须监听 0.0.0.0:8080,独占一台机器、按使用时长用 A 币计费,账户余额须大于运行 0.5 小时所需的 A 币,调用需要百度 Access Token,且只有创建者本人能调用;开发测试阶段的地址是 Codelab 项目链接加 `/api_serving/{端口}`。该服务地址是否为 https、令牌放在哪个请求头、是否会与桥自己的 Authorization 令牌冲突、浏览器的跨域预检请求能否通过,文档都没写,未核实。费用:A 币单价只在订单页显示,而 aistudio.baidu.com 对本次抓取返回 403,所以未核实。资格:需要百度账号,协议要求个人或非商业使用、每人一个账号、不得代第三方使用;协议文本没有写实名或年龄要求,但页面导航里有"未实名"标记,实名是否影响算力未核实。

English: GPU: the official compute-card doc (page dated 2024-03-20) says Notebook projects run on domestic DCU, Tesla V100 and A100; one point buys 2 hours of V100 16GB or 1 hour of V100 32GB, and running a project gives 8 points per day (about 16 hours of V100 16GB). After you close the browser the resources keep running for 10 more minutes and are then stopped, and the user agreement forbids running or starting processes while not logged in (clause 2(7)) and says only PaddlePaddle is supported, with unsupported projects or frameworks liable to be stopped (clause 1). A free notebook as a permanent KataGo bridge is therefore "unclear": do not use it that way, and use the free quota for batch analysis only. The platform's own serving route is "project service deployment" (page dated 2025-07-01): it publishes a Notebook project as an API callable over the public internet; the service must listen on 0.0.0.0:8080, takes one whole machine billed by usage time in A-coins (balance must exceed the A-coin cost of 0.5 hours), calls need the Baidu Access Token, and only the creator can call it; during development the test address is the Codelab project link plus `/api_serving/{port}`. Whether that service address is https, which header carries the token, whether it collides with the bridge's own Authorization token, and whether a browser CORS preflight passes are not stated, so not verified. Cost: A-coin prices are shown only on order pages and aistudio.baidu.com returned 403 to the fetch tool, so not verified. Eligibility: a Baidu account is needed; the agreement asks for personal or non-commercial use, one account per person, no use on behalf of third parties; it states no real-name or age rule, but the site navigation shows an "unverified (未实名)" badge, so whether real-name status affects compute is not verified.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 免费 Codelab 笔记本: 不明确 / unclear. 付费"项目服务部署": 允许 / allowed (官方功能). 来源 / source: https://ai.baidu.com/ai-doc/AISTUDIO/Blopive5g , https://ai.baidu.com/ai-doc/AISTUDIO/3k39vrahw , https://ai.baidu.com/ai-doc/AISTUDIO/nk39v9kec |
| 连接方式 / How to connect | 平台生成的公网 API 地址(开发测试: Codelab 链接 + /api_serving/8080;正式部署的地址格式文档只放在图片里,未核实),调用要带 Access Token,服务端口固定为 8080,不是 SSH 转发。 / A platform-generated public API address (development test: Codelab link + /api_serving/8080; the deployed-service address format appears only in images on the doc page, not verified), calls carry the Access Token, the service port is fixed at 8080, no SSH forward. Source: https://ai.baidu.com/ai-doc/AISTUDIO/Blopive5g |
| 费用 / Cost | 免费: 每天运行项目送 8 点算力卡, 约 16 小时 V100 16GB (页面日期 2024-03-20). 付费: A 币, 单价未核实, 服务部署另需余额大于运行 0.5 小时的 A 币. / Free: 8 points per day for running a project, about 16 hours of V100 16GB (page dated 2024-03-20). Paid: A-coins, unit price not verified; service deployment also needs a balance above the cost of 0.5 hours. (read on 2026-11-01) |
| 资格 / Eligibility | 百度账号; 个人或非商业用途; 每人一个账号; 无需高校身份(协议未写). / Baidu account; personal or non-commercial use; one account per person; no university affiliation required (none stated). Source: https://ai.baidu.com/ai-doc/AISTUDIO/3k39vrahw |
| 自行确认 / To confirm | 服务部署的实际 URL 与协议, Access Token 放哪个请求头, 是否放行跨域预检, KataGo 二进制能否在该环境运行 (无 apt-get, 仅支持飞桨), 当前 A 币价格, 实名要求. / Actual deployed URL and scheme, which header carries the Access Token, CORS preflight, whether a KataGo binary runs in that environment (no apt-get, PaddlePaddle only), current A-coin prices, real-name requirement. |

#### 天翼云 GPU 云主机 / Ctyun (China Telecom Cloud) GPU cloud host

中文: GPU:价格页(页面更新 2026-10-15)列出 NVIDIA 直通型 PI2(T4 16GB,pi2.2xlarge.4: 8 vCPU / 32GB / 1 卡,按需约 7.32 元/小时,包月约 3515 元)、PI7(A10 24GB,pi7.4xlarge.4: 约 9.27 元/小时)、P2V(V100 32GB,p2v.2xlarge.4: 约 15.37 元/小时)、P8A(A100 PCIE 40GB,p8a.6xlarge.4: 约 21.3 元/小时),另有按 1/4、1/2 张卡切分的 vGPU 图形型 G6/G7(例如 g6.xlarge.4 约 2.445 元/小时)。产品页写明 PI2/PI7 是 GPU 直通,凡使用 CUDA 的应用都能运行;vGPU 图形型能否跑 CUDA 未核实,所以选 PI2 或 PI7。启动方式是云主机(虚拟机):在控制中心选"GPU 加速/AI 加速"规格,选带 NVIDIA 550.90.07 驱动的公共镜像(如 Ubuntu Server 22.04),绑定弹性 IP,安全组放行 TCP 22。服务:这是通用云主机,用户协议(版本 2025-06-20)没有禁止自建应用服务,只禁止运行与服务无关或大量耗费资源的程序(6.2.7)和容易遭受攻击的反向代理类服务(6.2.8);另外 80、8080、443、8443 端口对公网开放前必须完成 ICP 备案,其他端口默认开放。自用的 KataGo 桥不在这些禁止项里,所以判为"允许",但协议没有专门写 API 服务这一用途。连接:推荐 `ssh -L 8787:127.0.0.1:8787 用户@弹性IP`,面板填 `http://127.0.0.1:8787`;如果在安全组里直接放行 TCP 8787,得到的是明文 `http://弹性IP:8787`,https 页面不能调用它,而要 https 就得自备域名和证书并占用 443,大陆云主机的 443 需要备案,所以不推荐。费用:按需 GPU 云主机要求账户余额加通用代金券大于 100 元(且大于当前与将开通的按需资源一小时的费用);欠费后实例被冻结并关机,保留期最长 15 天,之后云硬盘和弹性 IP 被释放、数据不可恢复。资格:必须先实名认证才能下单、试用或充值(协议 3.3.3),主体须是中国大陆合法注册的组织或完全民事行为能力的自然人(3.1.1),平台可要求人脸核验(3.7);不要求高校身份;没有大陆证件的用户能否注册未核实。

English: GPU: the price page (updated 2026-10-15) lists NVIDIA passthrough families PI2 (T4 16GB, pi2.2xlarge.4: 8 vCPU / 32GB / 1 card, about 7.32 CNY per hour on demand, about 3515 CNY per month), PI7 (A10 24GB, pi7.4xlarge.4: about 9.27 CNY per hour), P2V (V100 32GB, p2v.2xlarge.4: about 15.37 CNY per hour), P8A (A100 PCIE 40GB, p8a.6xlarge.4: about 21.3 CNY per hour), plus graphics-oriented vGPU families G6/G7 sliced into 1/4 or 1/2 cards (for example g6.xlarge.4 at about 2.445 CNY per hour). The product page says PI2/PI7 use GPU passthrough and run any CUDA application; whether the vGPU graphics families run CUDA is not verified, so pick PI2 or PI7. It starts as a cloud host (virtual machine): choose a "GPU-accelerated/AI-accelerated" spec in the control center, a public image with the NVIDIA 550.90.07 driver (for example Ubuntu Server 22.04), bind an elastic IP, and open TCP 22 in the security group. Serving: this is a general-purpose cloud host; the user agreement (version 2025-06-20) does not forbid running your own application service, and only bans programs unrelated to the service or heavy resource-hogging code (6.2.7) and reverse-proxy-type services that invite attacks (6.2.8); in addition, ports 80, 8080, 443 and 8443 need ICP filing before they are opened to the internet, while other ports are open by default. A personal KataGo bridge is not among the banned items, so the label is "allowed", but the agreement does not name API servers as a use case. Connection: recommended is `ssh -L 8787:127.0.0.1:8787 user@elastic-IP` with `http://127.0.0.1:8787` in the panel; opening TCP 8787 in the security group instead gives plain `http://elastic-IP:8787`, which an https page cannot call, and getting https means your own domain and certificate on 443, which needs ICP filing on a mainland host, so that is not recommended. Cost: on-demand GPU hosts need account balance plus general vouchers above 100 CNY (and above the one-hour cost of current and new on-demand resources); on arrears the instance is frozen and shut down, kept for up to 15 days, then disks and elastic IPs are released and the data cannot be recovered. Eligibility: real-name verification is required before ordering, trials or top-ups (clause 3.3.3); the holder must be a legally registered organization in mainland China or a natural person with full civil capacity (3.1.1); face verification may be requested (3.7); no university affiliation is needed; whether someone without mainland documents can register is not verified.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 允许 / allowed (通用云主机, 协议未禁止自建应用; 80/8080/443/8443 公网开放需备案; 禁止反向代理类服务). 来源 / source: https://www.ctyun.cn/portal/protocol/10144340 , https://www.ctyun.cn/document/10026730/10030802 |
| 连接方式 / How to connect | 弹性 IP + 安全组放行 TCP 22, 然后 `ssh -L 8787:127.0.0.1:8787 用户@弹性IP`, 面板填 `http://127.0.0.1:8787`. 直接放行 8787 只得到 http. / Elastic IP + security group opening TCP 22, then `ssh -L 8787:127.0.0.1:8787 user@elastic-IP`, panel gets `http://127.0.0.1:8787`. Opening 8787 directly gives http only. 来源 / source: https://ctyun.cn/document/10029787/10195732 (弹性 IP, 安全组, 22 端口; ssh -L 本身是 OpenSSH 功能, 天翼云文档未专门写 / the doc covers elastic IP, security group and port 22; ssh -L is a plain OpenSSH feature that the Ctyun doc does not mention) |
| 费用 / Cost | PI2 T4: 约 7.32 元/小时 (1 卡); PI7 A10: 约 9.27 元/小时; P2V V100: 约 15.37 元/小时; 余额+代金券须大于 100 元; 弹性 IP/带宽另计, 单价未核实. / PI2 T4: about 7.32 CNY/hour (1 card); PI7 A10: about 9.27 CNY/hour; P2V V100: about 15.37 CNY/hour; balance plus vouchers above 100 CNY; elastic IP and bandwidth billed separately, price not verified. (read on 2026-11-01; price page updated 2026-10-15) 来源 / source: https://www.ctyun.cn/document/10029787/10047957 , https://www.ctyun.cn/document/10026730/10030879 |
| 资格 / Eligibility | 实名认证(必需, 可能要求人脸核验); 大陆合法注册组织或完全民事行为能力自然人; 无需高校身份. / Real-name verification (required, face check possible); mainland-registered organization or natural person with full civil capacity; no university affiliation needed. Source: https://www.ctyun.cn/portal/protocol/10144340 |
| 自行确认 / To confirm | 你所在区域/资源池是否有 PI2 或 PI7 库存, 是否支持按需(不同页面说法不一), CUDA 和驱动版本是否满足所用 KataGo 版本, 弹性 IP 与带宽单价, 公网放行非标准端口 8787 是否会被视为未备案, 境外下载 KataGo 与权重的速度. / Whether your region or resource pool has PI2 or PI7 in stock, whether on-demand is offered there (pages differ), whether the CUDA and driver versions fit your KataGo build, elastic IP and bandwidth prices, whether exposing the non-standard port 8787 publicly counts as unfiled, and download speed for KataGo and weights from outside China. |

#### 国家超算互联网 SCNet / SCNet (National Supercomputing Internet)

中文: 平台:scnet.cn 的 AI 服务(Notebook、模型训练、模型部署)、容器服务(容器实例)、高性能计算服务(Slurm 作业)和裸金属服务器。Notebook 创建时选区域、加速卡型号与数量和开发镜像,然后进 JupyterLab,也可以 SSH 登录(文档只写密码登录,命令形如 `ssh -p 端口 root@ssh.scnet.tech`,实际值在实例页复制,镜像需预装 SSH)。文档只写"异构加速卡"(国产加速卡),核心节点页面称是国产 GPGPU,都没有给出型号,也没有说有没有 NVIDIA 卡,所以 KataGo 能否在上面运行未核实。服务:Notebook 的"访问自定义服务"是官方功能,在容器里监听 0.0.0.0 上的端口(文档示例是 1116),在实例页填入端口后启动;FAQ 说最多三个转发端口(Jupyter、TensorBoard 和一个自定义端口),因为容器运行在 K8s Pod 里,流量由平台代理。对外地址格式、是否 https、是否有鉴权文档都没写,未核实;用户协议没有禁止对外服务,但把挖矿软件、反向代理类服务和恶意占用资源列为禁止(3.2.1、3.2.3),所以只用平台自己的自定义服务端口,不要自建隧道。HPC 作业区是另一条路:不要在登录节点长时间运行程序,用 salloc(交互)或 sbatch(批处理),没有作业就不能 ssh 到计算节点,计算节点不能上网(华中一区手册的说法;KataGo 和权重要先在登录节点准备好),文档没写 ssh -L 是否允许。费用:AI 服务后付费,先充值到现金账户,费用等于运行时长乘以加速卡单价再乘以卡数,从容器真正开始运行算起,每整点和关机时扣费;价目表不在该页,未核实;"快速体验"活动写有 100 卡时、500GB 存储、1000 万 tokens,抓到的邀测计划页面期限是 2026-02-05 至 2026-04-30,今天是否仍有效未核实。资格:协议允许有完全民事行为能力的自然人、法人或其他组织注册,不要求高校身份(协议没写);帮助中心写明使用全部功能需要实名认证:填姓名和身份证号,经官方库核验后用支付宝、微信或手机浏览器扫码做人脸识别,没有大陆身份证的用户能否通过未核实。

English: Platform: scnet.cn offers AI services (Notebook, model training, model deployment), container service (container instances), high-performance computing (Slurm jobs) and bare-metal servers. When creating a Notebook you choose a region, accelerator card model and count, and a development image, then open JupyterLab; SSH login is also supported (the doc describes password login only, with a command of the form `ssh -p PORT root@ssh.scnet.tech` copied from the instance page, and the image must have SSH preinstalled). The docs only say "heterogeneous accelerator cards" (domestic accelerators); the core-node page says domestic GPGPU; none gives a model name or says whether NVIDIA cards exist, so whether KataGo runs there is not verified. Serving: the Notebook "access custom service" feature is official: listen on a port on 0.0.0.0 inside the container (the doc example uses 1116), enter the port on the instance page, then start; the FAQ says at most three forwarded ports (Jupyter, TensorBoard and one custom port), because the container runs in a K8s Pod and the platform proxies the traffic. The public address format, whether it is https, and any authentication are not documented, so not verified; the user agreement does not forbid external services but lists mining software, reverse-proxy-type services and malicious resource occupation as prohibited (3.2.1, 3.2.3), so use only the platform's own custom service port and build no tunnel of your own. The HPC job area is a different route: do not run programs on login nodes for long, use salloc (interactive) or sbatch (batch), you cannot ssh to a compute node without a job there, compute nodes have no internet (per the Central China zone manual; prepare KataGo and weights on the login node first), and the docs do not say whether ssh -L is allowed. Cost: AI services are post-paid from a topped-up cash account, charge equals running time times accelerator unit price times number of cards, counted from when the container actually runs, deducted at each full hour and at shutdown; the price table is not on that page, so not verified; the "quick test" activity mentions 100 card-hours, 500GB storage and 10 million tokens, but the beta-plan page I fetched showed a period of 2026-02-05 to 2026-04-30, so whether it is still available today is not verified. Eligibility: the agreement lets natural persons, legal entities and other organizations with full civil capacity register and states no university requirement; the help center says real-name verification is required for all platform features (name and ID number checked against an official database, then face recognition by scanning a QR code with Alipay, WeChat or a phone browser); whether users without a mainland ID card can pass is not verified.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | Notebook/容器的"自定义服务端口": 允许 / allowed (官方功能). HPC 作业区: 不明确 / unclear. 协议禁止反向代理类服务与挖矿软件. 来源 / source: https://www.scnet.cn/help/docs/mainsite/ai/notebook/function-introduction/service-port/index.html , https://www.scnet.cn/help/docs/mainsite/ai/faq/index.html , https://www.scnet.cn/sso/registeragreement |
| 连接方式 / How to connect | 平台代理的自定义服务地址(格式与是否 https 未核实); 或 Notebook SSH (`ssh -p 端口 root@ssh.scnet.tech`, 密码登录, ssh -L 是否允许未核实); HPC: 登录节点 + salloc + `ssh 节点名`. / Platform-proxied custom-service address (format and https not verified); or Notebook SSH (`ssh -p PORT root@ssh.scnet.tech`, password login, ssh -L not verified); HPC: login node + salloc + `ssh nodename`. 来源 / source: https://www.scnet.cn/help/docs/mainsite/ai/notebook/function-introduction/SSH/index.html , https://www.scnet.cn/help/docs/mainsite/hpc/cmd/skills/index.html |
| 费用 / Cost | AI 服务按 运行时长 x 卡单价 x 卡数 后付费, 价目表未核实 (页面只举例 2 元/卡时); 活动额度 100 卡时 (期限未核实). / AI services post-paid as runtime x card price x cards, price table not verified (the page only uses 2 CNY per card-hour as an example); activity quota 100 card-hours (validity not verified). (read on 2026-11-01) 来源 / source: https://www.scnet.cn/help/docs/mainsite/ai/bill/index.html , https://www.scnet.cn/help/docs/mainsite/activity/invite/quick-test/index.html , https://www.scnet.cn/ycjh/index.html |
| 资格 / Eligibility | 注册: 完全民事行为能力的自然人/法人/其他组织, 未成年人不可; 使用全部功能需实名认证(身份证 + 人脸). 无需高校身份(未写). / Registration: natural person, legal entity or other organization with full civil capacity, no minors; real-name verification (ID card + face) needed for all features. No university affiliation required (none stated). 来源 / source: https://www.scnet.cn/sso/registeragreement , https://www.scnet.cn/help/docs/mainsite/console/personal/index.html |
| 自行确认 / To confirm | Notebook 里实际可选的加速卡型号与 KataGo 兼容性, 自定义服务的公网 URL 格式/协议/鉴权, 是否允许 ssh -L, 当前价目表与免费活动是否仍有效, 非大陆用户能否通过实名. / Which accelerator models you can actually pick in Notebook and KataGo compatibility, the custom-service public URL format, scheme and authentication, whether ssh -L is allowed, the current price table and whether free activities still run, whether non-mainland users can pass real-name verification. |

#### 天河系列国家超算中心(天津、广州、长沙) / Tianhe national supercomputing centers (Tianjin, Guangzhou, Changsha)

中文: 天河系统由国家超算天津、广州、长沙中心运营,三者都是申请制。长沙中心的"上机申请"页面(页面日期 2018-04-16)写明:先电话咨询,下载《用户上机告知书和申请表》,由负责人签字并加盖单位公章后发邮件,5 个工作日内答复,通常先免费试用约一周,再签机时服务合同、开通账号,按实际使用付费并开发票,费率在咨询时商定、页面不公开。广州中心的官网页面本次连接被拒绝,只看到搜索摘要,描述的流程相同(申请表要课题组负责人签名和单位公章,试用后签协议付费);天津中心官网的搜索摘要称服务对象是科研院所、大学和重点企业,页面本次抓取失败,注册步骤未核实。所以高校或研究所成员应通过本单位的课题组和机时合同申请;个人爱好者能否直接申请未核实。使用方式:公开的"天河二号简明使用手册"(广州中心,V1.4,2016-03-24,托管在第三方 GitHub 仓库)用 yh 前缀的命令(据第三方教程的搜索摘要,它们是 Slurm 命令的改名版本,未核实):yhrun(交互)、yhbatch(批处理,手册推荐)、yhalloc(预分配);不要在登录节点直接运行程序,计算节点必须先分配才能登录,当时还要先建 VPN。新一代天河系统的现行手册、GPU 配置、端口转发和长时间服务的规定本次都没读到,未核实。结论:服务器用途不明确;没有中心书面同意,不要在登录节点或计算节点上开长期服务,稳妥做法是按作业提交批量分析。

English: The Tianhe systems are run by the national supercomputing centers in Tianjin, Guangzhou and Changsha, and all three work by application. The Changsha "apply for machine time" page (dated 2018-04-16) says: phone the center first, download the user notice and application form, have the responsible person sign it and stamp it with the unit seal, email it, expect a reply within 5 working days, usually get a free trial of about a week, then sign a machine-time service contract and have the account opened, pay by actual usage and receive an invoice; rates are agreed in the consultation and not published on the page. The Guangzhou site refused the connection, so only search snippets were seen, describing the same flow (the form needs the group leader's signature and the unit seal, then an agreement and payment after the trial); the Tianjin site's search snippet says it serves research institutes, universities and key enterprises, the page itself could not be fetched, and the registration steps are not verified. So university or institute members should apply through their group and a machine-time contract; whether an individual hobbyist can apply directly is not verified. Usage: the public "Tianhe-2 concise user manual" (Guangzhou center, V1.4, 2016-03-24, hosted in a third-party GitHub repository) uses commands with a yh prefix (a third-party tutorial snippet says they are renamed Slurm commands, not verified): yhrun (interactive), yhbatch (batch, the manual's recommendation), yhalloc (pre-allocation); do not run programs directly on login nodes, compute nodes can only be logged into after allocating one, and at that time a VPN had to be set up first. The current manuals for the new-generation Tianhe systems, their GPU configuration, port-forwarding rules and rules for long-running services were not read, so not verified. Conclusion: serving is unclear; without written consent from the center do not start a long-running service on a login or compute node, and submit batch analysis as jobs instead.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 不明确 / unclear (现行文档未读到; 实际按作业运行, 稳妥起见按 仅批处理 / batch only 对待). 来源 / source: https://nscc.hnu.edu.cn/info/1080/1104.htm , https://github.com/JiangLiNSCC/TH2-demos/blob/master/Manual.MD (第三方托管 / third-party host) |
| 连接方式 / How to connect | SSH 登录节点 (旧手册: 先 VPN), 作业内 yhalloc/yhrun; 端口转发: 文档未写. / SSH to a login node (old manual: VPN first), yhalloc/yhrun inside a job; port forwarding: not documented. |
| 费用 / Cost | 按机时服务合同, 按实际使用付费, 费率咨询时商定, 公开页面无价格, 未核实. / Under a machine-time service contract, paid by actual usage, rates agreed in consultation, no public price, not verified. (read on 2026-11-01) 来源 / source: https://nscc.hnu.edu.cn/info/1080/1104.htm |
| 资格 / Eligibility | 申请表需负责人签字和单位公章(长沙; 广州按搜索摘要同样), 需合同; 个人能否申请未核实. / Application form needs the responsible person's signature and the unit seal (Changsha; Guangzhou per search snippet), plus a contract; whether individuals can apply is not verified. |
| 自行确认 / To confirm | 向目标中心书面确认: 谁可以申请、GPU 型号与数量、是否允许交互作业和端口转发、登录节点规则、计费. / Ask the target center in writing: who may apply, GPU model and count, whether interactive jobs and port forwarding are allowed, login-node rules, billing. 联系方式(搜索摘要, 未核实) / contacts (search snippets, not verified): 广州 020-37106026, service.nscc@nscc-gz.cn; 长沙 0731-88664163. |

#### 鹏城云脑与启智社区 OpenI / Peng Cheng Cloud Brain and the OpenI (QiZhi) community

中文: 要分开两个入口。鹏城云脑(cloudbrain.pcl.ac.cn)是鹏城实验室的平台,首页有"资源申请"栏目,但没有写申请条件和步骤,也没有写谁可以使用,联系邮箱 cloudbrain@pcl.ac.cn,首页能力清单包含数据处理、模型开发与分布式训练、模型管理和模型部署(在线和批量服务)。启智社区 OpenI(openi.pcl.ac.cn)是面向开发者的在线 AI 协作平台,按社区教程(搜索摘要,未逐页核对)的说法,在项目的"云脑"里新建"调试任务"即可得到 Jupyter 环境,消耗算力积分(教程称每天最多获得 100 分,另一来源写 50 分,数字冲突);官方帮助文档首页(openi.pcl.ac.cn/docs/index.html)本次读取时显示维护页,所以 GPU 型号、调试任务时长、在线推理等官方细节未核实,搜索摘要称有 A100、V100、T4 和 4 小时的调试任务限制,均未核实。服务:启智社区使用协议在 2024 年 1 月更新,平台页面公告明确写着禁止使用内网穿透工具,因此不得用 frp、ngrok、反向 SSH 隧道之类把调试任务里的桥暴露出来;文档没有写调试任务能否开放自定义端口,所以判为"不明确",只用来做批量分析。连接:只有任务页提供的 Jupyter 网页入口,没有已核实的 SSH 或端口映射。费用:算力积分可以获得也可以购买,价格因算力中心而定,未核实。资格:启智的注册页对所有人开放,所读页面没有写实名或单位要求,未核实;鹏城云脑本身是否对个人开放未核实。

English: There are two separate entry points. Peng Cheng Cloud Brain (cloudbrain.pcl.ac.cn) is Peng Cheng Laboratory's platform; its landing page has a "resource application" section but gives no conditions or steps and does not say who may use it, with contact cloudbrain@pcl.ac.cn, and its capability list covers data processing, model development and distributed training, model management and model deployment (online and batch services). The OpenI community (openi.pcl.ac.cn) is an online AI collaboration platform for developers; according to community tutorials (seen as search snippets, not checked page by page), creating a "debug task" under a project's "Cloudbrain" tab gives a Jupyter environment and consumes compute points (a tutorial says up to 100 points can be earned per day, another source says 50, so the figures conflict). The official help-doc index (openi.pcl.ac.cn/docs/index.html) showed a maintenance page when read, so GPU models, debug-task duration and the online inference feature are not verified from official pages; search snippets mention A100, V100, T4 and a 4-hour debug-task limit, all not verified. Serving: the OpenI usage agreement was updated in January 2024 and the notice shown on the platform's pages states that intranet-penetration tools are prohibited, so do not use frp, ngrok, a reverse SSH tunnel or the like to expose a bridge inside a debug task; the docs do not say whether a debug task can open a custom port, so the label is "unclear" and the platform should be used for batch analysis only. Connection: only the Jupyter web entry on the task page; no verified SSH or port mapping. Cost: compute points can be earned or bought, with prices depending on the compute center; not verified. Eligibility: OpenI's sign-up page is open to anyone, the pages read state no real-name or institution requirement (not verified); whether Peng Cheng Cloud Brain itself is open to individuals is not verified.

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 不明确 / unclear; 内网穿透工具: 禁止 / forbidden; 按 仅批处理 / batch only 对待. 来源 / source: https://openi.pcl.ac.cn/OpenI/aiforge/wiki/user_guide (协议公告 / agreement notice), https://openi.pcl.ac.cn/zeizei/OpenI_Learning (社区教程仓库 / community tutorial repo, not official) |
| 连接方式 / How to connect | 任务页的 Jupyter 网页入口; 未发现已核实的 SSH/端口映射; 不得使用隧道. / The Jupyter web entry on the task page; no verified SSH or port mapping; no tunnels allowed. |
| 费用 / Cost | 算力积分(获得或购买), 价格因算力中心而定, 未核实. / Compute points (earned or bought), price depends on the compute center, not verified. (read on 2026-11-01) 来源 / source: https://openi.pcl.ac.cn/zeizei/OpenI_Learning/src/branch/master/Tutorial/FAQ.md (社区文档, 非官方 / community doc, not official) |
| 资格 / Eligibility | 启智: 公开注册, 要求未核实; 鹏城云脑: "资源申请"栏目, 条件未写. / OpenI: open sign-up, requirements not verified; Cloud Brain: a "resource application" section, conditions not stated. 来源 / source: https://cloudbrain.pcl.ac.cn/ |
| 自行确认 / To confirm | 官方帮助文档恢复后核对: GPU 型号, 调试任务时长, 积分规则, 在线推理是否可用及其地址, 实名要求, 协议原文关于"内网穿透"的范围. / Once the official docs are back, check GPU models, debug-task duration, points rules, whether online inference is usable and its address, real-name requirement, and the agreement's exact scope of "intranet penetration". |

#### 通用 Slurm 集群 (通用, 不是某个具体平台) / Generic Slurm clusters (GENERIC, not any one platform)

中文: 本节是通用说明,不代表上面任何一个平台;每个集群的具体规则以其管理员文档为准。通用流程是:在登录节点用 `salloc --gres=gpu:1 --time=02:00:00`(或 `srun --gres=gpu:1 --time=02:00:00 --pty bash`)申请一块 GPU 和时限,在得到的计算节点上启动桥(默认监听 127.0.0.1:8787),再在自己的电脑上建立 SSH 转发,面板填 `http://127.0.0.1:8787`。转发有两种写法:一是 ProxyJump,`ssh -N -J 用户@登录节点 -L 8787:127.0.0.1:8787 用户@计算节点`,转发终点是计算节点自己的回环地址,所以桥保持默认的 127.0.0.1 即可;二是经登录节点的 `ssh -N -L 8787:计算节点主机名:8787 用户@登录节点`,此时连接由登录节点发往计算节点,桥必须监听计算节点的网络地址,不能只听 127.0.0.1(这一点是按 ssh 手册中 -L 目标地址在远端解析的定义推出来的,不是某个集群的文档)。常见限制:管理员常用 pam_slurm_adopt,只有在该节点上有运行中的作业时才允许 ssh 到该节点;有的站点禁止 TCP 转发或不开放计算节点 SSH;作业到达 `--time` 时限后任务会收到 SIGTERM 再 SIGKILL,桥随之结束。登录节点规则:多个站点的文档都说登录节点只用于编辑和提交作业,在上面跑 Jupyter、VS Code 服务或长时间大内存程序是最常见的错误,会被管理员杀掉;LRZ 的文档还提醒不要让交互会话空占计算节点,可以改用 sbatch 作业启动桥并配合隧道。是否允许这种交互式长时间服务取决于站点政策,所以标为"不明确";先问管理员,不要为了绕过限制而在登录节点上跑桥。费用:取决于站点,通常按分配的 GPU 时间计,用完执行 exit 释放分配并用 squeue 确认没有残留作业。

English: This section is generic and does not describe any platform above; each cluster's own administrator documentation decides. The generic flow: on a login node, request one GPU and a time limit with `salloc --gres=gpu:1 --time=02:00:00` (or `srun --gres=gpu:1 --time=02:00:00 --pty bash`), start the bridge on the compute node you receive (it listens on 127.0.0.1:8787 by default), then open an SSH forward from your own computer and type `http://127.0.0.1:8787` into the panel. There are two ways to write the forward. One is ProxyJump: `ssh -N -J user@login-node -L 8787:127.0.0.1:8787 user@compute-node`; the forward ends at the compute node's own loopback, so the bridge can keep its default 127.0.0.1 bind. The other goes through the login node: `ssh -N -L 8787:compute-node-hostname:8787 user@login-node`; here the connection is made from the login node to the compute node, so the bridge must listen on the compute node's network address and not only on 127.0.0.1 (this point is derived from the ssh manual's definition that the -L target is resolved on the remote side, it is not from any cluster's docs). Usual limits: administrators often use pam_slurm_adopt, which allows ssh to a node only while you have a running job there; some sites forbid TCP forwarding or do not allow SSH to compute nodes at all; when the job reaches its `--time` limit the tasks get SIGTERM and then SIGKILL, so the bridge ends. Login-node rules: several sites' docs say login nodes are for editing and job submission only, running Jupyter or VS Code servers or long, memory-heavy programs there is the most common mistake and administrators kill such processes; the LRZ doc also warns against idling a compute node in an interactive session and offers an sbatch job that starts the server plus a tunnel instead. Whether such a long-lived interactive service is allowed is site policy, so the label is "unclear": ask the administrators first, and never run the bridge on a login node to get around a limit. Cost: depends on the site, usually per allocated GPU time; when done run exit to release the allocation and confirm with squeue that no job is left.

```
# 登录节点上 / on the login node
salloc --gres=gpu:1 --cpus-per-task=4 --time=02:00:00
# 得到的计算节点上启动桥 (见 docs/ENGINE-SETUP.md) / on the compute node: start the bridge (see docs/ENGINE-SETUP.md), default 127.0.0.1:8787

# 你自己的电脑上 (ProxyJump: 转发终点是计算节点的回环地址) / on your own computer (ProxyJump: the forward ends at the compute node's loopback)
ssh -N -J user@login.example.org -L 8787:127.0.0.1:8787 user@computenode
# 面板里填 / panel: http://127.0.0.1:8787  +  token
```

| 项目 / Item | 内容 / Content |
|---|---|
| 服务器用途 / Serving allowed | 不明确 / unclear (取决于站点; 登录节点上长时间服务通常被禁止). 来源 / source: https://ccl.cse.nd.edu/blog/2026/interactive-computing/ , https://doku.lrz.de/faq-jupyter-on-hpc-systems-10746056.html (单个站点的文档, 仅作示例 / single-site docs, examples only) |
| 连接方式 / How to connect | `salloc` 或 `srun --pty` 取得计算节点, 然后 `ssh -J` / `ssh -L` 转发. / `salloc` or `srun --pty` to get a compute node, then `ssh -J` / `ssh -L` forwarding. 来源 / source: https://slurm.schedmd.com/salloc.html , https://slurm.schedmd.com/srun.html , https://man.openbsd.org/ssh , https://slurm.schedmd.com/pam_slurm_adopt.html |
| 费用 / Cost | 取决于站点. / Depends on the site. (read on 2026-11-01) |
| 资格 / Eligibility | 取决于站点(通常需要单位账号和分配额度). / Depends on the site (usually an institutional account and an allocation). |
| 自行确认 / To confirm | 是否允许 ssh 到计算节点、是否允许 TCP 转发、交互作业时限、GPU 型号、计算节点是否能上网. / Whether ssh to compute nodes and TCP forwarding are allowed, interactive time limits, GPU model, whether compute nodes have internet access. |

## 5. 面板怎么用 / How the panel works

卡片出现在右侧栏、讲解卡片的下面,不会盖住棋盘(窄窗口里它排在棋盘下方)。一条变化走到终点(没有后续)时自动显示,标题是"这条变化到此为止?用 KataGo 继续推演";在任何一手上,也可以点棋盘下方的「推演」按钮把它调出来或收起。

The card sits in the right column below the commentary cards and never covers the board (in a narrow window it is placed under the board). At the end of a variation (no continuation) it shows up by itself, titled "这条变化到此为止?用 KataGo 继续推演"; on any move the small "推演" button under the board brings it up or folds it away.

| 控件 / Control | 作用 / What it does |
|---|---|
| 状态行 / Status line | 算力来源、网络、后端、状态(空闲、连接中、搜索中 N 次、已暂停、已完成、出错) / compute source, network, backend and state (idle, connecting, searching N visits, paused, done, error) |
| 开始 / 暂停 / 继续 / 停止 | 开始:新开一次搜索。暂停:真的让 KataGo 停下来(桥执行 `terminate`,GPU 立即空闲),保留当前结果。继续:对同一局面重新搜索。停止:终止并清除本次的实时结果,回到缓存数据 / Start: begin a new search. Pause: really stops KataGo (the bridge runs `terminate`, the GPU is free at once) and keeps the current result. Resume: searches the same position again. Stop: ends the search and clears this live result, back to the cached data |
| 算力 / Compute source | 缓存(不联网)、本机、远程 GPU;与左侧「算力」是同一个设置 / cache (no network), local, remote GPU; the same setting as the "算力" fold-out on the left |
| 网络 / Network | 填入桥允许的网络(`/models`),当前使用的带"(当前)"标记;换网络时桥会重启 KataGo 并显示进度,新网络加载失败会自动恢复原来的 / the networks the bridge allows (`/models`), the active one marked "(active)"; switching restarts KataGo with progress, and a network that fails to load is rolled back automatically |
| 次数上限 / Visits cap | 200、1000、5000 次,或「直到停止」;「直到停止」其实是桥自己的上限(默认 20000 次或 900 秒),不会无限运行 / 200, 1000, 5000 visits, or "until stopped"; "until stopped" is really the bridge's own ceiling (default 20000 visits or 900 seconds), it never runs without end |
| 只搜讲解区域 / Region only | 默认勾选,与视频讲解区域一致;取消后候选点可能在当前视野之外 / on by default, same as the teaching region; unchecked, candidates may lie outside the current view |
| 显示最佳线 / Show best line | 把当前最佳变化作为带编号的预览画在棋盘上,候选点圆圈仍然保留;你点了别的预览或固定了某条线时不会覆盖 / draws the current best line as a numbered preview, the candidate dots stay; it does not overwrite a preview you clicked or a line you pinned |
| 候选表 / Candidate table | 着手、比局部最优差几目、搜索次数、变化(芯片);鼠标移到某一行,棋盘就像悬停那个候选点一样只显示它的这一条线;带 `*` 的是老师的着法,单独评估 / move, points worse than the local best, visits, the line as chips; hovering a row shows only that line on the board exactly like hovering its dot; a `*` marks a teacher move that was evaluated separately |
| 走 / Play | 把这个候选作为临时的一手下到棋盘上(与点击棋盘空点相同:先检查区域和自杀),它不会进入变化树;如果刚才在搜索,约 0.3 秒后在新局面继续搜索 / plays that candidate as a temporary move (the same as clicking an empty point: region and suicide are checked), it never enters the variation tree; if a search was active, it continues in the new position after about 0.3 seconds |
| 采用这条线 / Adopt this line | 把当前局面加上最佳线复制成 SGF 到剪贴板,不联网;浏览器拒绝自动复制时会显示一个文本框供手动复制 / copies the current position plus the best line as SGF to the clipboard, no network; if the browser refuses the automatic copy, a text box is shown for manual copying |
| 网络活动 / Network activity | 本页自己发出的每个请求:时间、主机、路径、用途、字节、状态 / every request this page made: time, host, path, purpose, bytes, status |

画法完全沿用查看器已有的规则,因为用的就是同一批函数:半透明棋子是候选点,颜色是行棋方;圈的颜色和数字是比局部最优差几目(最优为 0,绿色表示不低于 -0.3);蓝色虚线圈加序号是老师在视频里走的变化;变化线从 1 开始编号,从行棋方起交替;悬停某个候选点时只显示它自己的线并隐藏其他一切;不显示全盘胜率,只有局部搜索和目数差;KataGo 返回的黑方视角分数会先换算成行棋方视角。实时结果存在节点的内存里(不进库),换到别的局面时正在运行的搜索会立刻被取消。

The drawing follows the viewer's existing rules exactly, because it uses the same functions: translucent stones are candidates, coloured as the side to move; the ring colour and number are the points lost against the local best (0 is best, green is -0.3 or better); blue dashed rings with a number are the teacher's moves from the video; variation lines are numbered from 1 and alternate starting with the side to move; hovering a candidate shows only its own line and hides everything else; no whole-board win rate is shown, only local search and point loss; the Black perspective scores that KataGo reports are converted to the side to move first. Live results live in the node's memory (never in the library), and moving to another position cancels a running search at once.

在有老师后续着法的节点上,搜索结束后会像单次分析一样,对搜索次数不够的老师着法再做一次强制评估(这一步要在整次搜索结束后进行)。

On a node that has teacher continuations, after the search ends the teacher moves with too few visits are evaluated once more by force, just like the single-shot analysis (this step happens after the whole search has finished).

## 6. 出错了怎么办 / Troubleshooting

面板里的错误信息都是一句话加一条修法,对应下面这些情况。

Every error in the panel is one sentence plus one fix; these are the cases.

| 面板显示 / The panel says | 原因 / Cause | 修法 / Fix |
|---|---|---|
| 无法连接(桥没启动、地址错、或来源未放行) / cannot connect | 桥没启动,地址或端口不对,或浏览器因 CORS 拦截(浏览器不会告诉页面具体是哪一种) / the bridge is not running, wrong address or port, or the browser blocked it by CORS (the browser does not tell the page which) | 确认桥已启动且地址端口正确;页面来源不在允许列表里就加 `--allow-origin <来源>` / make sure the bridge runs and the address and port are right; add `--allow-origin <origin>` if the page origin is not allowed |
| 浏览器拦截了:https 页面不能访问 http 地址 / blocked: an https page cannot call an http address | 混合内容 / mixed content | 改用 https 地址,或用 SSH 转发后填 `http://127.0.0.1:8787` / use an https address, or an SSH forward and `http://127.0.0.1:8787` |
| 无法连接(桥没启动,或桥不接受 file:// 页面) / cannot connect (bridge not running, or it does not accept file:// pages) | 双击打开的页面来源是 `null` / a double-clicked page has the origin `null` | 启动桥时加 `--allow-file-origin`,或改从 `http://localhost:8765` 打开页面 / start the bridge with `--allow-file-origin`, or open the page from `http://localhost:8765` |
| token 不对 / wrong token | HTTP 401 | 重新复制桥启动时打印的 token / copy the token the bridge printed again |
| 桥拒绝了这个页面的来源 / the bridge refused this page's origin | HTTP 403 | 启动桥时加 `--allow-origin <来源>` / start the bridge with `--allow-origin <origin>` |
| 找不到接口,这可能不是本项目的桥 / endpoint not found | HTTP 404,或桥版本太旧(没有 `/stream`) / HTTP 404, or the bridge is too old (no `/stream`) | 检查地址;把 `remote/katago_bridge.py` 更新到 v2 / check the address; update `remote/katago_bridge.py` to v2 |
| 桥正忙(并发已满)或桥正在切换网络 / the bridge is busy or switching | HTTP 429 或 409 / HTTP 429 or 409 | 等一会儿再试 / try again in a moment |
| 桥正在加载网络 / the bridge is loading a network | HTTP 503 | 等几秒再开始;第一次使用 OpenCL 时调优可能要几分钟 / wait a few seconds; first-time OpenCL tuning can take minutes |
| 响应没有声明黑方视角,已拒绝 / the response did not declare Black's perspective, refused | 连到的不是本项目的桥,或版本不匹配 / not this project's bridge, or a version mismatch | 为避免视角错误,页面不会使用这样的结果;确认连的是 `katago_bridge.py` / the page will not use such a result to avoid perspective errors; make sure you connect to `katago_bridge.py` |
| 连接中断 / connection lost | 搜索中途连接断了(桥退出、网络断、代理超时,比如 RunPod 的 100 秒单次连接限制) / the connection dropped during a search (bridge exited, network lost, a proxy timeout such as RunPod's 100 second limit) | 检查网络和桥,然后重新开始 / check the network and the bridge, then start again |

## 7. 来源 / Sources

下面是本文各处引用的页面;平台调研的每一条事实都在对应平台名下给出了网址。官方页面的措辞和价格会变,以你登录后在控制台看到的为准。

These are the pages cited above; every platform fact is listed under its platform name with the address. Wording and prices on official pages change, trust what you see in your own console.

### 本机 KataGo / Local KataGo

- KataGo 发布页和发布说明(v1.18.1、v1.18.2,2026-11-01 通过 GitHub 接口读取) / KataGo releases and release notes (v1.18.1, v1.18.2, read through the GitHub API on 2026-11-01): <https://github.com/lightvector/KataGo/releases>
- KataGo 自述文件(上手、benchmark、genconfig、分析引擎、Homebrew) / the KataGo README (getting started, benchmark, genconfig, analysis engine, Homebrew): <https://github.com/lightvector/KataGo>
- KataGo 分析引擎协议(`reportDuringSearchEvery`、`isDuringSearch`、`terminate`) / the KataGo analysis engine protocol (`reportDuringSearchEvery`, `isDuringSearch`, `terminate`): <https://github.com/lightvector/KataGo/blob/master/docs/Analysis_Engine.md>
- `katago version` 输出里的 "Using ... backend" 行(`main.cpp` 源码) / the "Using ... backend" line of the `katago version` output (source of `main.cpp`): <https://github.com/lightvector/KataGo/blob/master/cpp/main.cpp>
- KataGo 官方网络页面 / the official KataGo networks page: <https://katagotraining.org/networks/>
- Homebrew 公式数据(预编译包平台) / the Homebrew formula data (bottle platforms): <https://formulae.brew.sh/api/formula/katago.json>

<!-- bilingual-check: off -->

### 海外平台 / Abroad platforms

所有页面读取日期均为 2026-11-01。 / All pages were read on 2026-11-01.

#### RunPod 平台 / RunPod
- https://docs.runpod.io/pods/configuration/expose-ports (Expose ports on Pods; HTTP proxy URL, TCP, 100 s limit)
- https://docs.runpod.io/pods/pricing (Pod pricing; billing model, minimum credit, storage)
- https://www.runpod.io/pricing (Pricing; GPU hourly prices)
- https://www.runpod.io/legal/terms-of-service (Terms of Service)
- https://docs.runpod.io/pods/configuration/use-ssh (Connect to a Pod with SSH)
- https://docs.runpod.io/pods/overview (Pods overview; Secure vs Community Cloud)
- https://docs.runpod.io/pods/connect-to-a-pod.md (Connection options)
- https://docs.runpod.io/references/security-and-compliance.md (Data security and legal compliance)
- https://docs.runpod.io/accounts-billing/billing.md (Billing overview; credits, minimums, payment methods)
- https://docs.runpod.io/llms.txt (documentation index)
- https://docs.runpod.io/references/faq (FAQ; no relevant content for this task)

#### Vast.ai 平台 / Vast.ai
- https://docs.vast.ai/instances (Instances overview)
- https://docs.vast.ai/documentation/instances/connect/ssh (SSH; `-L` example, direct vs proxy SSH)
- https://docs.vast.ai/guides/instances/connect/networking.md (Networking and ports)
- https://docs.vast.ai/guides/instances/connect/instance-portal.md (Instance Portal; Cloudflare tunnels, PORTAL_CONFIG)
- https://docs.vast.ai/guides/instances/connect/jupyter.md (Jupyter launch mode)
- https://docs.vast.ai/guides/instances/connect/overview.md (Connection methods overview)
- https://docs.vast.ai/guides/instances/pricing.md (Instance pricing and billing)
- https://docs.vast.ai/guides/reference/faq/security.md (Security FAQ; host trust, Secure Cloud)
- https://docs.vast.ai/guides/reference/faq/billing.md (Billing FAQ; payment methods)
- https://docs.vast.ai/guides/reference/faq (FAQ index)
- https://docs.vast.ai/llms.txt (documentation index)
- https://vast.ai/terms (Terms of Service)
- https://vast.ai/pricing (Pricing; price types)
- https://vast.ai/pricing/gpu/RTX-3090 and https://vast.ai/pricing/gpu/RTX-4090 (GPU price pages; showed "No current offers")

#### Lambda 平台 / Lambda
- https://lambda.ai/service/gpu-cloud (GPU Cloud; instance types and prices)
- https://docs.lambda.ai/public-cloud/firewalls/ (Firewalls)
- https://docs.lambda.ai/public-cloud/on-demand/ (On-demand cloud overview)
- https://docs.lambda.ai/public-cloud/on-demand/connecting-instance/ (Connecting to an instance; SSH tunnel)
- https://docs.lambda.ai/public-cloud/access-security/ (Access and security)
- https://docs.lambda.ai/public-cloud/billing/ (Billing)
- https://docs.lambda.ai/public-cloud/on-demand/creating-managing-instances/ (Creating and managing instances)
- https://lambda.ai/legal/terms-of-service (Terms of Service, including cloud terms and acceptable use; read in two parts)

#### Paperspace 云平台(DigitalOcean 旗下) / Paperspace (DigitalOcean)
- https://www.paperspace.com/ (home page)
- https://www.paperspace.com/pricing (pricing page; used only as a clue, its text was inconsistent with the DigitalOcean docs)
- https://www.paperspace.com/terms-of-service (Terms of Service, updated 9/19/2023)
- https://docs.digitalocean.com/products/paperspace/ (Paperspace docs home; announcements)
- https://docs.digitalocean.com/products/paperspace/machines/ (Machines)
- https://docs.digitalocean.com/products/paperspace/machines/details/machine-types/ (Machine types)
- https://docs.digitalocean.com/products/paperspace/machines/details/availability/ (Availability by region)
- https://docs.digitalocean.com/products/paperspace/machines/details/features/ (Machine features; networking)
- https://docs.digitalocean.com/products/paperspace/machines/details/limits/ (Machine limits; H100 approval)
- https://docs.digitalocean.com/products/paperspace/machines/details/pricing/ (Machines pricing page; no figures)
- https://docs.digitalocean.com/products/paperspace/machines/how-to/ (How-to index)
- https://docs.digitalocean.com/products/paperspace/machines/how-to/manage-public-ips/ (Manage public IP addresses)
- https://docs.digitalocean.com/products/paperspace/machines/how-to/connect/ (Connect to machines)
- https://docs.digitalocean.com/products/paperspace/pricing/ (Paperspace pricing; GPU rates, plans, public IP)
- https://docs.digitalocean.com/products/paperspace/notebooks/ (Notebooks)
- https://docs.digitalocean.com/products/paperspace/notebooks/details/limits/ (Notebook limits; storage only)
- https://docs.digitalocean.com/products/paperspace/accounts-and-teams/index.html.md (Accounts and teams)
- https://www.digitalocean.com/legal/terms-of-service-agreement (DigitalOcean Terms of Service)

#### Modal 平台 / Modal
- https://modal.com/docs/guide/webhooks (Web endpoints / Web Functions)
- https://modal.com/docs/guide/web-endpoints (web_server overview)
- https://modal.com/docs/guide/servers.md (Servers)
- https://modal.com/docs/guide/tunnels (Tunnels, `modal.forward`)
- https://modal.com/docs/guide/webhook-proxy-auth (Proxy tokens)
- https://modal.com/docs/guide/webhook-timeouts (Request timeouts)
- https://modal.com/docs/guide/timeouts (Function timeouts)
- https://modal.com/docs/guide/scale (Autoscaling settings)
- https://modal.com/docs/guide/sandboxes.md (Sandboxes)
- https://modal.com/docs/guide/gpu (GPU acceleration)
- https://modal.com/docs/guide/billing.md (Billing)
- https://modal.com/pricing (Pricing)
- https://modal.com/legal/terms (Terms)
- https://modal.com/docs/llms.txt (documentation index)

#### Hugging Face Jobs 平台 / Hugging Face Jobs
- https://huggingface.co/docs/huggingface_hub/guides/jobs (Run and manage Jobs; Python client)
- https://huggingface.co/docs/hub/jobs (Jobs contents)
- https://huggingface.co/docs/hub/jobs-overview (Jobs overview)
- https://huggingface.co/docs/hub/jobs-configuration (Jobs configuration; Expose Ports, SSH, timeout)
- https://huggingface.co/docs/hub/jobs-pricing (Jobs pricing and billing)
- https://huggingface.co/docs/hub/jobs-reference (Jobs reference)
- https://huggingface.co/docs/hub/jobs-quickstart (Jobs quickstart)
- https://huggingface.co/pricing (Pricing)
- https://huggingface.co/docs/hub/billing (Billing; credits, payment methods)
- https://huggingface.co/terms-of-service (Terms of Service)
- https://huggingface.co/docs/huggingface_hub/guides/sandbox (Sandboxes, experimental)

#### Lightning AI 平台 / Lightning AI
- https://lightning.ai/pricing (Pricing)
- https://lightning.ai/llms.txt (documentation index)
- https://lightning.ai/docs/manifests/platform.json (documentation manifest)
- https://lightning.ai/docs/platform/build/host-web-apps.md (Host web apps)
- https://lightning.ai/docs/platform/build/host-web-apps/streamlit-apps.md (Streamlit apps; ports plugin mention)
- https://lightning.ai/docs/platform/build/ai-studio.md (AI Studio)
- https://lightning.ai/docs/platform/build/ai-studio/deploy-on-public-ports.md (Deploy on public ports)
- https://lightning.ai/docs/platform/build/ai-studio/ssh-access.md (SSH access)
- https://lightning.ai/docs/platform/build/ai-studio/plugins.md (Plugins)
- https://lightning.ai/docs/platform/inference/batch-jobs/prototype-server-api.md (Prototype server APIs)
- https://lightning.ai/docs/platform/overview/faq.md (FAQ)
- https://lightning.ai/docs/platform/overview/faq/billing.md (Billing FAQ)
- 读取失败(404) / failed (404): https://lightning.ai/terms-of-use , https://lightning.ai/pages/terms-of-service/ , https://lightning.ai/terms-of-service , https://lightning.ai/pages/wp-json/wp/v2/pages/5648480

All read on 2026-11-01. 读取日期均为 2026-11-01。

Colab
- Colab FAQ (restricted activities, limits): https://research.google.com/colaboratory/faq.html
- Colab Paid Services Pricing (plans, units, countries): https://colab.research.google.com/signup?hl=en

Kaggle
- Kaggle Acceptable Use Policy (version effective 2025-06-22): https://www.kaggle.com/aup
- Kaggle Terms of Use (cryptomining clause, AUP reference): https://www.kaggle.com/terms
- Kaggle Notebooks documentation (GPU types, 12 h sessions, 20 min idle, Kaggle Jupyter Server): https://www.kaggle.com/docs/notebooks
- Kaggle Efficient GPU Usage (weekly quota): https://www.kaggle.com/docs/efficient-gpu-usage

AWS
- AWS Acceptable Use Policy: https://aws.amazon.com/aup/
- EC2 G4 instance types (T4): https://aws.amazon.com/ec2/instance-types/g4/
- EC2 G5 instance types (A10G): https://aws.amazon.com/ec2/instance-types/g5/
- EC2 G6 instance types (L4): https://aws.amazon.com/ec2/instance-types/g6/
- EC2 on-demand price data (published 2026-10-29): https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-ondemand-without-sec-sel/EU%20(Frankfurt)/Linux/index.json and the "US%20East%20(N.%20Virginia)" variant
- EC2 instance type quotas: https://docs.aws.amazon.com/ec2/latest/instancetypes/ec2-instance-quotas.html
- Session Manager, start a session (port forwarding): https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html
- Session Manager prerequisites: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-prerequisites.html
- Session Manager instance permissions: https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-getting-started-instance-profile.html
- EC2 security groups: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html
- AWS Deep Learning AMI overview: https://docs.aws.amazon.com/dlami/latest/devguide/what-is-dlami.html
- AWS Free Tier: https://aws.amazon.com/free/

Google Cloud
- Google Cloud Acceptable Use Policy: https://cloud.google.com/terms/aup
- IAP TCP forwarding: https://docs.cloud.google.com/iap/docs/using-tcp-forwarding
- GPU platforms on Compute Engine: https://docs.cloud.google.com/compute/docs/gpus
- Resource usage and GPU quotas: https://docs.cloud.google.com/compute/resource-usage
- Accelerator-optimized and GPU attachment pricing: https://cloud.google.com/products/compute/pricing/accelerator-optimized
- Free program features (trial limits, sign-up): https://docs.cloud.google.com/free/docs/free-cloud-features

Azure
- NCasT4_v3 size series: https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/ncast4v3-series
- Bastion native client configuration: https://learn.microsoft.com/en-us/azure/bastion/native-client
- Bastion Linux native client and tunnel command: https://learn.microsoft.com/en-us/azure/bastion/connect-vm-native-client-linux
- Network security groups overview: https://learn.microsoft.com/en-us/azure/virtual-network/network-security-groups-overview
- Increase VM-family vCPU quotas: https://learn.microsoft.com/en-us/azure/quotas/per-vm-quota-requests
- Universal License Terms for Online Services (acceptable use): https://www.microsoft.com/licensing/terms/product/ForOnlineServices/all
- Azure Retail Prices API: https://prices.azure.com/api/retail/prices
- Azure free account: https://azure.microsoft.com/en-us/free/

LRZ and BayernKI
- LRZ AI Systems overview: https://doku.lrz.de/lrz-ai-systems-11484278.html
- 1. Access: https://doku.lrz.de/1-access-10746642.html
- 1.1 AI Systems Login: https://doku.lrz.de/1-1-ai-systems-login-2498299908.html
- 1.2 Usage Policies: https://doku.lrz.de/1-2-usage-policies-2763063391.html
- 1. General Description and Resources (partitions): https://doku.lrz.de/1-general-description-and-resources-10746641.html
- 3. Access and getting started: https://doku.lrz.de/3-access-and-getting-started-10746642.html
- 5. Slurm: https://doku.lrz.de/5-slurm-1897076524.html
- 5.1 Slurm Interactive Jobs: https://doku.lrz.de/5-1-slurm-interactive-jobs-1898974515.html
- 6. Interactive Apps: https://doku.lrz.de/6-interactive-apps-10746644.html
- FAQ: Jupyter on HPC Systems (CoolMUC-4, SuperMUC-NG only): https://doku.lrz.de/faq-jupyter-on-hpc-systems-10746056.html
- ssh - Secure Shell on LRZ HPC Systems (SuperMUC-NG, Linux Cluster only): https://doku.lrz.de/ssh-secure-shell-on-lrz-hpc-systems-10746160.html
- LRZ news, one year of BayernKI: https://www.lrz.de/en/news/detail/one-year-of-bayernki
- BayernKI Access: https://www.ki-in-bayern.de/access/
- BayernKI FAQs: https://www.ki-in-bayern.de/faqs/
- BayernKI registration page (only navigation text was readable): https://www.ki-in-bayern.de/de/registration-for-bayernki-access/
- BayernKI homepage at NHR@FAU: https://www.kib.cms.rrze.net/
- NHR@FAU BayernKI application: https://doc.nhr.fau.de/bayernki-application/

### 国内平台 / Platforms in China

全部在 2026-11-01 读取 / all read on 2026-11-01.

AutoDL
- 文档首页 / Docs home: https://www.autodl.com/docs/
- 开放端口 / Open ports: https://www.autodl.com/docs/port/
- SSH 隧道 / SSH tunnel: https://www.autodl.com/docs/ssh_proxy/
- 实例自定义服务补充协议 / Custom service supplementary agreement: https://www.autodl.com/docs/service_agreement/
- 实名认证服务协议 / Real-name service agreement: https://www.autodl.com/docs/real_name_cert/
- 充值与计费 / Billing: https://www.autodl.com/docs/price/
- GPU 选型 / GPU selection: https://www.autodl.com/docs/gpu/
- SSH: https://www.autodl.com/docs/ssh/
- JupyterLab: https://www.autodl.com/docs/jupyterlab/
- 暴露多个服务 / Exposing multiple services: https://www.autodl.com/docs/proxy_in_instance/
- AutoDL 服务协议 / Service agreement: https://www.autodl.com/docs/agreements/
- 维护与故障 / Maintenance: https://www.autodl.com/docs/maintenance/
- 快速开始 / Quick start: https://www.autodl.com/docs/quick_start/
- 省钱绝招 / Saving money: https://www.autodl.com/docs/save_money/
- (算力市场 https://www.autodl.com/market/list 和首页只返回了导航,没有价格 / the market page and home page returned navigation only, no prices)

恒源云 Gpushare
- 文档首页 / Docs home: https://gpushare.com/docs/
- 公网暴露服务 / Public exposure: https://gpushare.com/docs/best_practices/custom/
- 登录 Linux 实例 / Linux login: https://gpushare.com/docs/getting-started/login_instance/
- 服务协议 / Service agreement: https://gpushare.com/docs/product/agreement/
- 产品价格 / Pricing: https://gpushare.com/docs/product/price/
- 账户相关 FAQ / Account FAQ: https://gpushare.com/docs/faq/account/
- 实例相关 FAQ / Instance FAQ: https://gpushare.com/docs/faq/instance/
- JupyterLab: https://gpushare.com/docs/best_practices/jupyterlab/
- 如何选卡 / Choosing a card: https://gpushare.com/docs/getting-started/car/
- 快速开始 / Quick start: https://gpushare.com/docs/getting-started/quickstart/
- (官网首页 https://gpushare.com/ 只返回 "Loading..." / the home page returned only "Loading...")

OpenBayes
- 文档首页 / Docs home: https://openbayes.com/docs/
- 算力容器 / Gear: https://openbayes.com/docs/gear/
- 使用 SSH Tunnel 访问容器的服务 / SSH tunnel: https://openbayes.com/docs/gear/ssh-tunnel
- 自定义端口映射与服务暴露 / Port mapping: https://openbayes.com/docs/gear/expose-service
- 通过 SSH 连接 Jupyter 工作空间 / SSH to a Jupyter workspace: https://openbayes.com/docs/gear/ssh
- 算力容器的限额 / Gear limits: https://openbayes.com/docs/gear/limitation
- 常见问题 / FAQ: https://openbayes.com/docs/gear/faq
- 配额限制 / Limitations: https://openbayes.com/docs/limitations
- 资源计费方式 / Payment methods: https://openbayes.com/docs/payment-methods
- 定价 / Pricing: https://openbayes.com/pricing
- 服务条款 / Terms of service: https://openbayes.com/tos
- (同文页面 / an equivalent page on another site: https://hyper.ai/cn/docs/gear/ssh-tunnel)

趋动云 / VirtAI Cloud
- 首页 / Home: https://www.virtaicloud.com/
- (公告正文 / notice body, HTTP 403: https://platform.virtaicloud.com/gemini/v1/gemini_doc/%E6%9C%8D%E5%8A%A1%E8%B0%83%E6%95%B4%E5%85%AC%E5%91%8A.html)

阿里云 / Alibaba Cloud
- 创建和管理 DSW 实例 / Create and manage DSW instances: https://help.aliyun.com/zh/pai/create-and-manage-dsw-instances
- DSW 自定义服务公网访问 / Custom services access: https://help.aliyun.com/zh/pai/custom-services-access-configurations
- DSW 计费说明 / DSW billing: https://help.aliyun.com/zh/pai/product-overview/dsw-billing-description
- 访问 DSW 实例 / Access a DSW instance: https://help.aliyun.com/zh/pai/access-dsw-instance
- DSW 常见问题 / DSW FAQ: https://help.aliyun.com/zh/pai/faq-about-dsw
- DSW SSH 直连 / DSW SSH direct connection: https://help.aliyun.com/zh/pai/dsw-direct-connection
- ECS GPU 实例规格族 / ECS GPU instance families: https://help.aliyun.com/zh/ecs/user-guide/gpu-accelerated-compute-optimized-and-vgpu-accelerated-instance-families-1
- 购买内地 ECS 的实名登记 / Real-name registration for mainland ECS: https://help.aliyun.com/zh/user-center/real-name-registration-for-purchasing-an-ecs-instance-in-the-chinese-mainland
- 自定义购买 ECS / Create an instance with the wizard: https://help.aliyun.com/zh/ecs/user-guide/create-an-instance-by-using-the-wizard
- 安全组规则 / Security group rules: https://help.aliyun.com/zh/ecs/user-guide/security-group-rules
- 公网 IP / Public IP address: https://help.aliyun.com/zh/ecs/user-guide/public-ip-address
- 可购买地域 / Regions and zones: https://help.aliyun.com/zh/ecs/user-guide/regions-and-zones
- 实例上的网站无法访问 / Cannot access a website hosted on an instance: https://help.aliyun.com/en/ecs/support/what-do-i-do-if-i-cannot-access-a-website-hosted-on-an-instance
- 不同场景下 ICP 备案 FAQ / ICP filing FAQ by scenario: https://help.aliyun.com/zh/icp-filing/basic-icp-service/product-overview/faq-about-icp-filing-applications-in-different-scenarios
- 备案条件和流程 FAQ / Filing conditions FAQ: https://help.aliyun.com/zh/icp-filing/basic-icp-service/support/for-the-record-process-faq
- 备案前服务器及接入信息排查 / Server and access information check before filing: https://help.aliyun.com/zh/icp-filing/basic-icp-service/user-guide/icp-filing-server-access-information-check
- (价格页 https://www.aliyun.com/product/ecs/gpu 和 https://www.aliyun.com/price/product 一直重定向,没有读到价格 / these price pages kept redirecting, no prices read)

腾讯云 / Tencent Cloud
- 渲染型 GPU 实例 / Rendering GPU instances: https://cloud.tencent.com/document/product/560/19701
- GPU 计算型实例 / GPU compute instances: https://cloud.tencent.com/document/product/560/30130
- GPU 云服务器计费说明 / GPU CVM billing: https://cloud.tencent.com/document/product/560/8025
- 云服务器价格总览 / CVM price overview: https://cloud.tencent.com/document/product/213/2176
- 购买 Linux 实例 / Buy a Linux CVM: https://cloud.tencent.com/document/product/213/10517
- 配置安全组 / Configure security groups: https://cloud.tencent.com/document/product/213/15377
- ICP 备案是否需要备案 / Is ICP filing needed: https://cloud.tencent.com/document/product/243/19630
- HAI 文档首页 / HAI docs home: https://cloud.tencent.com/document/product/1721
- HAI 产品概述 / HAI overview: https://cloud.tencent.com/document/product/1721/101024
- HAI 产品对比 / HAI comparison: https://cloud.tencent.com/document/product/1721/101026
- HAI 计费概述 / HAI billing: https://cloud.tencent.com/document/product/1721/101029
- HAI 购买限制 / HAI purchase limits: https://cloud.tencent.com/document/product/1721/101030
- HAI 购买方式 / HAI purchase methods: https://cloud.tencent.com/document/product/1721/101031
- HAI 常见问题 / HAI FAQ: https://cloud.tencent.com/document/product/1721/101038
- HAI 默认端口说明 / HAI default ports: https://cloud.tencent.com/document/product/1721/102531
- HAI 产品页 / HAI product page: https://cloud.tencent.com/product/hai
- HAI 特惠页 / HAI promotion page: https://cloud.tencent.com/act/pro/hai
- GPU 云服务器价格页 / GPU CVM pricing page (no table): https://cloud.tencent.com/product/gpu/pricing

华为云 / Huawei Cloud
- 通过 SSH 工具远程使用 Notebook / Using Notebook over SSH: https://support.huaweicloud.com/devtool-modelarts/devtool-modelarts_0021.html
- 启动/停止/删除 Notebook / Start, stop, delete Notebook: https://support.huaweicloud.com/devtool-modelarts/devtool-modelarts_0006.html
- Notebook 使用说明 / Notebook usage notes: https://support.huaweicloud.com/devtool-modelarts/devtool-modelarts_0002.html
- 创建 Notebook(英文旧版页面,含限制) / Creating a Notebook (English old page, constraints): https://support.huaweicloud.com/intl/es-us/usermanual-standard-modelarts/devtool-modelarts_0004.html
- Notebook 快速入门(Gradio 示例) / Notebook quickstart (Gradio demo): https://support.huaweicloud.com/qs-modelarts/modelarts_06_0034.html
- VS Code 连接失败排查 / VS Code connection troubleshooting: https://support.huaweicloud.com/trouble-modelarts/modelarts_05_4190.html
- GPU 加速型实例规格 / GPU-accelerated ECS flavors: https://support.huaweicloud.com/productdesc-ecs/ecs_01_0045.html
- 使用 GPU 实例部署 Stable Diffusion WebUI / Deploy Stable Diffusion WebUI on a GPU ECS: https://support.huaweicloud.com/bestpractice-ecs/ecs_bp_6019.html
- GPU 加速云服务器产品页 / GPU product page: https://www.huaweicloud.com/product/gpu.html
- 什么情况下必须实名认证 / When real-name verification is required: https://support.huaweicloud.com/intl/zh-cn/account_faq/zh-cn_topic_0142752673.html
- 我需要在华为云备案吗 / Do I need to file with Huawei Cloud: https://support.huaweicloud.com/icp_faq/icp_05_0145.html
- (只在搜索摘要里看到、未抓取全文 / seen only in search snippets: https://support.huaweicloud.com/usermanual-account/account_auth_00001.html )

全部在 2026-11-01 读取。 / All read on 2026-11-01. 标 [摘要] 的只看到搜索结果摘要, 页面本身没能抓取; 标 [第三方] 的不是平台官方页面。 / Entries marked [snippet] were seen only as search-result snippets because the page itself could not be fetched; entries marked [third-party] are not official platform pages.

百度 AI Studio / Baidu AI Studio:
- 算力卡 (页面更新 2024-03-20): https://ai.baidu.com/ai-doc/AISTUDIO/nk39v9kec
- 项目服务部署 (页面更新 2025-07-01): https://ai.baidu.com/ai-doc/AISTUDIO/Blopive5g
- 项目概述 (页面更新 2026-05-11): https://ai.baidu.com/ai-doc/AISTUDIO/0k3e2tfzm
- 常见问题 (页面更新 2024-03-20, 部分内容较旧): https://ai.baidu.com/ai-doc/AISTUDIO/5k39vd65f
- 用户协议 (更新 2024-04-23): https://ai.baidu.com/ai-doc/AISTUDIO/3k39vrahw
- 权益说明 (2024-04-23): https://ai.baidu.com/ai-doc/AISTUDIO/1lu5r7wzw
- https://aistudio.baidu.com/ 与 https://aistudio.baidu.com/membership 对抓取返回 403, 未读到 / returned 403 to the fetch tool, not read

天翼云 / Ctyun:
- 价格总览-GPU云主机-计费说明 (页面更新 2026-10-15): https://www.ctyun.cn/document/10029787/10047957
- NVIDIA GPU云主机-产品规格: https://www.ctyun.cn/document/10029787/10348867
- 创建配备GPU驱动的GPU云主机(Linux): https://ctyun.cn/document/10029787/10195732
- 按量计费模式-弹性云主机 ECS: https://www.ctyun.cn/document/10026730/10030879
- 手动部署 Java Web (含 80/8080/443/8443 备案说明): https://www.ctyun.cn/document/10026730/10030802
- 中国电信天翼云用户协议 (版本 2025-06-20): https://www.ctyun.cn/portal/protocol/10144340
- 支持挂载主机规格族清单 (规格族名称对照): https://ctyun.cn/document/10027696/10965905
- GPU 云主机用户使用手册 PDF: https://www.ctyun.cn/s/q04sv38ZSzTBF4mEHo-3dVsyWITNHb2AHhoKmmcfMQvFLURsx3V4aZ93q1RNu3GGzQKhrSGX3-c0FHA9DL4VQp7DanvIK3hQ3rdQ6E4qRjkU3uvrfqsdTrAULqDomgmXXN5fs2iff4sVXYkXYMY65TneFc0tArQXgtL2oepVsdvXSyWgsmR3gX4LRc_PnYFqYePnNG7P3uQp1Q9slClhSQ (PDF 文本无法提取, 未用于结论 / PDF text could not be extracted, not used for any conclusion)

国家超算互联网 SCNet:
- 首页 / home page: https://www.scnet.cn
- Notebook 如何配置访问自定义服务: https://www.scnet.cn/help/docs/mainsite/ai/notebook/function-introduction/service-port/index.html
- AI 服务常见问题: https://www.scnet.cn/help/docs/mainsite/ai/faq/index.html
- SSH 登录: https://www.scnet.cn/help/docs/mainsite/ai/notebook/function-introduction/SSH/index.html
- AI 服务计费: https://www.scnet.cn/help/docs/mainsite/ai/bill/index.html
- 个人中心(实名认证): https://www.scnet.cn/help/docs/mainsite/console/personal/index.html
- 用户协议: https://www.scnet.cn/sso/registeragreement
- 快速开始 / Notebook 快速使用: https://www.scnet.cn/help/docs/mainsite/ai/quick-start/index.html , https://www.scnet.cn/help/docs/mainsite/ai/notebook/quick-use/
- 容器实例(旧版): https://www.scnet.cn/help/docs/mainsite/container-service/container-instance/
- 模型部署: https://www.scnet.cn/help/docs/mainsite/ai/model-deploy/index.html
- 快速体验活动: https://www.scnet.cn/help/docs/mainsite/activity/invite/quick-test/index.html
- 核心节点邀测计划: https://www.scnet.cn/ycjh/index.html
- HPC 常用技巧 / 命令行 FAQ / 连接超算集群: https://www.scnet.cn/help/docs/mainsite/hpc/cmd/skills/index.html , https://www.scnet.cn/help/docs/mainsite/hpc/cmd/faq/index.html , https://www.scnet.cn/help/docs/mainsite/hpc/cmd/connect-to-hpc/index.html
- 华中一区平台基础使用: https://www.scnet.cn/help/docs/mainsite/bw-core-node/platform-basic-usage/index.html

天河 / Tianhe:
- 长沙中心上机申请 (页面日期 2018-04-16): https://nscc.hnu.edu.cn/info/1080/1104.htm
- 天河二号简明使用手册 V1.4 (2016-03-24, 广州中心, [第三方] GitHub 托管): https://github.com/JiangLiNSCC/TH2-demos/blob/master/Manual.MD
- [摘要] 广州中心"我要上机": http://nscc-gz.cn/Service/Igotto.html (抓取时连接被拒绝 / connection refused)
- [摘要] 天津中心 天河 HPC 云: https://nscc-tj.cn/cjjs_zxpt_hpc (抓取失败 / fetch failed)

鹏城云脑与启智 / Peng Cheng Cloud Brain and OpenI:
- 鹏城云脑首页: https://cloudbrain.pcl.ac.cn/
- 鹏城实验室首页: https://www.pcl.ac.cn/
- 启智协议公告所在页 (用户指南 wiki): https://openi.pcl.ac.cn/OpenI/aiforge/wiki/user_guide
- [第三方] 启智社区教程仓库及 FAQ: https://openi.pcl.ac.cn/zeizei/OpenI_Learning , https://openi.pcl.ac.cn/zeizei/OpenI_Learning/src/branch/master/Tutorial/FAQ.md
- 启智帮助文档首页 (读取时为维护页, 未取得内容): https://openi.pcl.ac.cn/docs/index.html

通用 / Generic:
- Slurm salloc: https://slurm.schedmd.com/salloc.html
- Slurm srun: https://slurm.schedmd.com/srun.html
- Slurm pam_slurm_adopt: https://slurm.schedmd.com/pam_slurm_adopt.html
- OpenSSH ssh 手册 (-L, -J, -N): https://man.openbsd.org/ssh
- [第三方, 单站点示例] 交互式计算与登录节点规则: https://ccl.cse.nd.edu/blog/2026/interactive-computing/
- [第三方, 单站点示例] LRZ Jupyter on HPC FAQ: https://doku.lrz.de/faq-jupyter-on-hpc-systems-10746056.html
- MDN Secure Contexts: https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts
- MDN Mixed content: https://developer.mozilla.org/en-US/docs/Web/Security/Mixed_content
- W3C Mixed Content: https://w3c.github.io/webappsec-mixed-content/

<!-- bilingual-check: on -->

## 8. 未核实 / Not verified

以下是各部分调研时没有在官方页面上核实的事项,以及本文自己的未核实项。请在依赖这些信息之前,先在你自己的账号或平台页面上确认。

These are the points that could not be checked on an official page during the research, plus this document's own. Confirm them in your own account or on the platform pages before relying on them.

### 本文和面板 / This document and the panel

- 真实的 KataGo、真实的 GPU 上的整条流程没有运行过:流式输出、终止和切换网络只在模拟引擎上验证过。 / The whole flow on a real KataGo and a real GPU was not run: streaming, terminate and switching were only verified against the fake engine.
- `katago version` 的"Using ... backend"一行来自 KataGo 源码,没有实际运行;读不到时面板显示 `-`(桥报告 `unknown`)。 / The "Using ... backend" line of `katago version` comes from the KataGo source and was not run; when it cannot be read the panel shows `-` (the bridge reports `unknown`).
- 经过 SSH 转发、各平台的代理或端口映射的真实连接,以及 Windows 脚本 `start_bridge.ps1` 的完整运行,没有验证。 / Real connections through SSH forwards or the platforms' proxies and port mappings, and a full run of the Windows script `start_bridge.ps1`, were not verified.
- 双击打开的 `file://` 页面里面板和桥的配合只按代码和单元测试推断,没有在浏览器里实际打开过(浏览器窗格不能打开 file://)。 / The panel and the bridge with a double-clicked `file://` page were only reasoned from the code and unit tests; the browser pane cannot open file://.
- 网络文件的许可条款、Intel Mac 是否能用 Metal、较新 Chrome 的"本地网络访问"提示、Safari 对 `http://127.0.0.1` 的处理。 / The licence terms of network files, whether Metal works on Intel Macs, the "local network access" prompt of newer Chrome, how Safari treats `http://127.0.0.1`.

### 海外平台 A / Abroad A

1. RunPod: 价格表中社区云和安全云两列的对应关系在工具读取时不清楚;T4 和 A4000 不在 Pod 价格表里。 / RunPod: the mapping of the community and secure price columns was unclear in the tool's reading; T4 and A4000 are not in the Pod price table.
2. RunPod: 哪些云类型(Secure/Community)支持 TCP 端口暴露,文档没有明说。 / RunPod: which cloud types (Secure or Community) support TCP port exposure is not stated.
3. RunPod: 代理 URL 本身是否有访问控制没有说明(应当按公开地址对待,只靠 bridge token);`ssh -L` 在 RunPod 文档页里没有示例;没有找到单独的可接受使用政策,条款第 4 节(社区云主机)没有细读。 / RunPod: whether the proxy URL itself has access control is not stated (treat it as public and rely on the bridge token); no `ssh -L` example on the RunPod doc pages; no separate acceptable use policy was found, and Terms Section 4 (Community Cloud hosts) was not read in detail.
4. Vast.ai: 各 GPU 的当前价格(实时市场表无法读取)和最低充值额。 / Vast.ai: current per-GPU prices (the live market grid is not readable) and the minimum deposit.
5. Vast.ai: 服务条款只读到摘要,没有逐条读全文;条款没有说明主机能否访问用户数据。 / Vast.ai: only a summary of the Terms was read, not the full text; the Terms do not say whether hosts can access user data.
6. Vast.ai: Instance Portal 是否能用于任意自选镜像(搜索摘要说它随 Vast.ai 提供的 Docker 镜像出现,已读页面未明说);"Direct" SSH 只在开放端口的机器上可用,具体哪台机器要在选机时看。 / Vast.ai: whether the Instance Portal works with any image you choose (a search snippet says it comes with Vast.ai Docker images, the pages read do not say); "Direct" SSH needs a machine with open ports, which you only see when choosing a machine.
7. Lambda: 云条款第 2(c) 条引用的 Platform Guidelines 没有读到。 / Lambda: the Platform Guidelines referenced by Cloud Terms Section 2(c) were not read.
8. Lambda: 注册是否要求信用卡或预付、新账户的具体实例数量上限,已读页面没有写。 / Lambda: whether a card or prepayment is required at sign-up, and the exact instance limit for new accounts, are not stated on the pages read.
9. Paperspace: 可接受使用政策(AUP)没有读到,所以服务条款对对外提供服务的规定不明。 / Paperspace: the Acceptable Use Policy was not read, so what the terms say about offering a service is unknown.
10. Paperspace: Machines 的端口和防火墙规则、笔记本的端口暴露、SSH 命令格式和端口转发,已读文档均未涉及。 / Paperspace: Machines port and firewall rules, notebook port exposure, the SSH command format and port forwarding are not covered by the docs read.
11. Paperspace: 免费笔记本的会话时长限制只出现在 paperspace.com 价格页的摘要里(12 小时自动关机),该页文字与 DigitalOcean 文档不完全一致;新账户的 GPU 机器数量上限没有写。 / Paperspace: the free notebook session limit (12-hour auto-shutdown) appears only in a summary of the paperspace.com pricing page, whose text is not fully consistent with the DigitalOcean docs; the GPU machine limit for new accounts is not stated.
12. Modal: `@app.server()` 的 URL 格式文档未给出;`*.modal.run` 的格式只在 Web Function 页面里出现。 / Modal: the URL format for `@app.server()` is not given; the `*.modal.run` pattern appears only on the Web Function page.
13. Modal: 浏览器跨域(CORS)行为,包括 Proxy Token 请求头是否允许跨域、预检请求如何处理,文档没有写。 / Modal: browser cross-origin (CORS) behaviour, including whether Proxy Token headers are allowed cross-origin and how preflight requests are handled, is not documented.
14. Modal: 条款中"客户内部使用"对个人用户的含义,以及是否有另外的可接受使用政策页,没有进一步核实;Servers 的请求超时无法在 Modal 里设置,实际上限未写。 / Modal: what "customer internal use" means for an individual and whether a separate acceptable use page exists were not checked; Server request timeouts cannot be set in Modal and the effective limit is not stated.
15. Hugging Face Jobs: 单个 Job 的最长超时没有写(示例到 1 天);最低预付额没有写;补充条款(Supplemental Terms)和内容政策没有读到。 / Hugging Face Jobs: the maximum timeout of a single Job is not stated (examples go up to 1 day); the minimum prepaid amount is not stated; the Supplemental Terms and Content Policy were not read.
16. Hugging Face Jobs: Jobs 代理对浏览器跨域和预检请求的处理没有文档;私有暴露(要求 HF token)能否从浏览器使用未核实。 / Hugging Face Jobs: how the Jobs proxy treats browser cross-origin and preflight requests is not documented; whether private exposure (HF token required) is usable from a browser is not verified.
17. Lightning AI: 服务条款读取失败(多个地址 404),是否允许长期提供服务无法判断。 / Lightning AI: the Terms could not be read (several addresses returned 404), so whether long-lived serving is allowed cannot be judged.
18. 闪电 AI:文档没有给出 API builder 公网地址的格式、是否为 https、免费版是否包含,也没有 ports 插件说明和 SSH 端口转发示例;免费积分能否用于 GPU 的具体规则没有写;十分钟无活动就休眠,对需要常驻的桥有什么影响,要自己试。 / Lightning AI: the API builder public URL format, whether it is HTTPS, whether the free plan includes it, the ports plugin description and an SSH `-L` example are not given; the exact rules for spending free credits on a GPU are not stated; the effect of the 10-minute inactivity sleep on an always-on bridge must be tried yourself.

### 海外平台 B / Abroad B

1. Colab: 当前免费和付费可用的具体 GPU 型号与计算单元消耗速度(FAQ 只说型号会变) / the GPU models currently available and the compute unit burn rates (the FAQ only says models vary). 也没有核实付款方式要求 / payment requirements were not checked.
2. Colab: 我没有核实 Colab 的 `google.colab.output` 等把端口嵌入笔记本输出的功能;即使存在,它们也不是供外部网页调用的地址,且 FAQ 禁止与交互计算无关的网络服务 / I did not check Colab features that embed a port into notebook output; even if they exist they are not an address an outside web page can call, and the FAQ bans web services unrelated to interactive compute.
3. Kaggle: 账号要求(手机验证等)和 GPU/联网开关的前置条件未在所读页面核实 / account requirements (phone verification and so on) and prerequisites for the GPU and internet toggles were not verified on the pages read.
4. Kaggle: 条款没有逐字禁止 HTTP 服务;"仅批处理"是根据 AUP 与会话模型作出的判定,不是条款原文 / the terms do not literally ban HTTP services; "batch only" is my judgement from the AUP and the session model, not a quoted clause.
5. AWS: Session Manager 本身是否另收费、EBS 与流量费用,页面未读到 / whether Session Manager itself has a charge, and EBS and data transfer costs, were not read.
6. AWS: 新账号是否能顺利获批 G 实例配额、审批时长、是否需要信用卡或手机验证,所读页面没有写 / whether a new account gets G quota approved, how long it takes, and whether a card or phone check is needed are not stated on the pages read.
7. AWS: 两个页面对端口转发所需的 SSM Agent 最低版本写法不一致(2.3.672.0 与 3.0.222.0),请使用较新的 agent / two pages give different minimum SSM Agent versions for port forwarding (2.3.672.0 and 3.0.222.0); use a current agent.
8. 浏览器行为 / browser behavior: 公网 https 页面调用 `http://127.0.0.1` 或 `http://localhost` 时,浏览器(尤其是较新的本地网络访问权限提示或 Safari)的行为没有任何厂商文档可引,需在用户的浏览器里实测 / no vendor doc covers how browsers treat an https page calling `http://127.0.0.1` or `http://localhost` (newer local-network permission prompts, Safari), test in the user's own browser. 这条适用于 AWS、GCP、Azure 三条转发路线 / this applies to the AWS, GCP and Azure forwarding routes.
9. GCP: N1 虚拟机本身的价格(与 T4 挂接组合)未读;300 美元赠金升级后能否用于 GPU 未核实;各型号的默认 GPU 配额数值页面未列出;G2 在各区域的可用性未查 / the price of the N1 VM that goes with a T4 was not read; whether the 300 USD credit covers GPUs after upgrade is not verified; default GPU quota values are not listed on the page; G2 regional availability was not checked.
10. GCP: 价格表的区域我只读了 us-central1(Iowa);欧洲区域价格未读 / I only read us-central1 (Iowa) prices; European region prices were not read.
11. Azure: NCasT4_v3 的默认 vCPU 配额、各区域是否有 T4 规格库存、NV(A10)与 ND 系列规格都未核实 / the default NCasT4_v3 vCPU quota, regional T4 stock, and the NV (A10) and ND series were not verified.
12. Azure: 完整的可接受使用政策全文只读到摘要;`az network bastion tunnel` 是否能直接隧道到 8787 文档没有明确支持(文档说隧道用于 SSH 或 RDP),故只写了经 22 端口再 `ssh -L` / only a summary of the full acceptable use policy was read; Bastion tunnel support for 8787 is not documented (the docs say SSH or RDP), so only the route via port 22 plus `ssh -L` is given. Azure 学生类免费方案(不用信用卡)在免费账号页没有提到,未核实 / Azure student offers without a card are not mentioned on the free account page and were not verified.
13. LRZ: AI Systems 文档没有描述到计算节点的 SSH 或端口转发,计算节点是否允许从登录节点直接 SSH 未核实;网页门户的 Jupyter 会话是否支持 `jupyter-server-proxy` 的 `/proxy/8787/` 未核实 / the AI Systems docs do not describe SSH or port forwarding to compute nodes, whether compute nodes accept SSH from the login node is not verified, and whether a portal Jupyter session supports jupyter-server-proxy `/proxy/8787/` is not verified.
14. LRZ: 网页门户 https://login.ai.lrz.de 是否也要求设备在 MWN 内、是否需要双因素认证、学生是否可以个人申请(而不是通过项目 master user)、LRZ AI Systems 是否收费,都未在所读页面核实 / whether the web portal also needs the MWN, whether two-factor authentication applies, whether students may apply individually (rather than through a project master user), and whether LRZ AI Systems charges anything are not verified on the pages read.
15. LRZ: 使用政策只给出摘要内容;我没有读到 LRZ 使用规则(Benutzungsrichtlinien)全文,也没有读到 "98.x" 资格页(链接返回 404) / the usage policy page was read as a summary; the full LRZ usage regulations (Benutzungsrichtlinien) and the "98.x" eligibility pages (the links I tried returned 404) were not read. 出口管制的具体要求未核实 / the specific export control requirements are not verified.
16. 巴伐利亚 BayernKI:埃尔朗根大学一侧(NHR@FAU 的 Helma 和 Alex)的交互使用规则没有读;资源上限和授权时长没有读;慕尼黑工业大学是否在官方高校名单上(名单由常见问题页链接,调研时没有打开)、学生能否申请,都未核实 / the interactive-use rules at NHR@FAU (Helma, Alex) were not read; resource limits, grant duration, whether TUM is on the official list of universities (linked from the FAQ, not opened) and whether students may apply are not verified. BayernKI 注册页只读到导航文字,表单字段未核实 / only navigation text of the BayernKI registration page was readable, so its form fields are not verified.

### 中国平台 A / China A

1. AutoDL:GPU 小时单价(算力市场页读不到)。 / AutoDL: GPU hourly prices (the market page was not readable).
2. AutoDL:仅租 GPU 是否必须实名;开放端口页"企业认证"的规则是否仍然有效(页面无日期);是否有 T4 或 L4 一类的卡。 / AutoDL: whether renting a GPU alone needs real-name; whether the "enterprise certification" rule on the ports page is current (the page is undated); whether T4 or L4 class cards exist.
3. AutoDL:自定义服务选 TCP 或 HTTP 时地址的协议(示例只显示 https 加 8443)。 / AutoDL: the scheme of the custom-service address under TCP versus HTTP (the example shows only https and port 8443).
4. 恒源云:价格表的日期、单位(按小时为推断)和会员档;实时价格。 / Gpushare: the date, unit (hourly is inferred) and member tier of the price table; live prices.
5. 恒源云:是否需要实名;自定义服务的公网地址格式和协议;是否只能用 8080;SSH 是否允许端口转发。 / Gpushare: whether real-name is needed; the public address shape and scheme of the custom service; whether only 8080 works; whether SSH port forwarding is allowed.
6. OpenBayes:实名流程;除 RTX 5090 和 RTX PRO 6000 外是否还有别的 GPU;免费试用数额;服务条款对对外服务沉默,未见明文。 / OpenBayes: the real-name procedure; whether other GPUs exist beyond RTX 5090 and RTX PRO 6000; the free-trial amount; the terms are silent on serving.
7. 趋动云:停服公告正文和日期(403);GPU、价格、端口。 / 趋动云: the notice body and dates (403); GPUs, prices, ports.
8. 阿里云 DSW:GPU 单价、免费试用数额、NAT 网关和 EIP 单价;sshd 是否允许 TCP 转发。 / Alibaba Cloud DSW: GPU unit price, free-trial amount, NAT gateway and EIP prices; whether sshd allows TCP forwarding.
9. 阿里云 GPU ECS:官方 GPU 价格(价格页重定向)、各地域库存、GPU 配额;官方对"仅 IP、非 Web 端口"的备案说法;阿里云总服务条款未逐条读。 / Alibaba Cloud GPU ECS: official GPU prices (the price pages redirect), per-region stock, GPU quota; an official filing statement on "IP only, non-web port"; the general service terms were not read clause by clause.
10. 腾讯云 GPU CVM:官方价格;按量关机不收费的适用条件(在另一份 CVM 文档);地域库存;总服务条款未读。 / Tencent GPU CVM: official prices; conditions of shutdown-no-charge (in another CVM document); region stock; the general terms were not read.
11. 腾讯云备案:一份搜索摘要称腾讯文档对"仅 IP 访问"有另一种说法,但我抓取的 243/19630 页面没有这句话,两者没有对上。 / Tencent filing: a search summary suggested Tencent has a different statement on "IP-only access", but the page I fetched (243/19630) does not contain it; the two do not match.
12. 腾讯云 HAI:GPU 型号名;是否提供 root SSH 和自定义 TCP 端口("编辑端口规则"页未读);服务条款对自建长期服务的态度;体验券价格。 / Tencent HAI: GPU model names; whether root SSH and custom TCP ports exist (the "edit port rules" page was not read); the terms' stance on self-built long-lived services; voucher prices.
13. 华为云 ModelArts Notebook:GPU 型号和单价;`/proxy/<端口>/` 是否接受仅带桥接令牌的跨域请求(很可能要控制台登录,文档未写);SSH 页对端口转发沉默。 / Huawei ModelArts Notebook: GPU models and unit prices; whether `/proxy/<port>/` accepts cross-origin calls with only the bridge token (it likely needs the console login, not documented); the SSH page is silent on port forwarding.
14. 华为云 GPU ECS:价格、配额、库存、EIP 单价;备案 FAQ 针对"网站或 App",对自用 API 未说明;账号中心实名页只看到搜索摘要。 / Huawei GPU ECS: price, quota, stock, EIP price; the filing FAQ speaks about "websites or apps" and not a private API; the account real-name page was seen only as a search snippet.
15. 香港节点是否有合适的 GPU 库存(三家公有云的 FAQ 都说香港不要求 ICP 备案,但库存没查)。 / Whether Hong Kong nodes have a suitable GPU in stock (all three public-cloud FAQs say Hong Kong needs no ICP filing, but stock was not checked).
16. 浏览器行为:https 页面调用 `http://127.0.0.1` 是通用浏览器规则而非厂商文档;Safari 和新版 Chrome 的本地网络提示未核实。 / Browser behaviour: an https page calling `http://127.0.0.1` is a general browser rule and not vendor documentation; Safari and the newer Chrome local-network prompts were not verified.

### 中国平台 B / China B

1. 百度: 当前 A 币每小时单价(V100/A100)和项目服务部署的专机单价. / Baidu: current A-coin hourly prices (V100/A100) and the dedicated-machine rate for service deployment.
2. 百度: 服务部署的实际 URL 是否 https、Access Token 放在哪个请求头、是否与桥的 Authorization 令牌冲突、浏览器跨域预检是否放行(调用示例在文档图片里). / Baidu: whether the deployed service URL is https, which header carries the Access Token, whether it collides with the bridge's Authorization token, whether browser CORS preflight is allowed (the call examples are images on the doc page).
3. 百度: KataGo 二进制能否在 Codelab 或部署环境运行(无 apt-get,协议称仅支持飞桨),以及这算不算"平台不支持的项目或框架". / Baidu: whether a KataGo binary runs in Codelab or the deployment environment (no apt-get, the agreement says PaddlePaddle only) and whether that counts as an unsupported project or framework.
4. 百度: 免费算力卡能否合规地用于常驻服务(文档与协议均未直接回答); 实名/手机要求和非大陆用户能否注册. / Baidu: whether free compute cards may be used for a standing service (neither docs nor agreement answer it directly); real-name and phone requirements and whether non-mainland users can register.
5. 天翼云: 你的区域/资源池是否有 PI2、PI7 库存,按需与包月的可用性(不同页面说法不一,PDF 手册无法提取文本). / Ctyun: whether your region or resource pool has PI2 or PI7 in stock, and on-demand versus subscription availability (pages differ, the PDF manual's text could not be extracted).
6. 天翼云: 公共镜像的 CUDA 版本是否满足所用 KataGo 版本; G 系列 vGPU 能否跑 CUDA. / Ctyun: whether the public image's CUDA version fits your KataGo build; whether the G-series vGPU can run CUDA.
7. 天翼云: 弹性 IP 与带宽单价,关机后哪些项继续计费; 公网放行非标准端口 8787 是否会被视为未备案. / Ctyun: elastic IP and bandwidth prices, which items keep billing after shutdown; whether exposing non-standard port 8787 publicly counts as unfiled.
8. 天翼云: 没有大陆证件的用户能否实名注册、可用的付款方式; 从境外下载 KataGo 与权重的速度. / Ctyun: whether users without mainland documents can register with real-name verification, accepted payment methods; download speed for KataGo and weights from outside China.
9. SCNet: Notebook/容器实际可选的加速卡型号(文档只写"异构加速卡")、是否有 NVIDIA 卡、KataGo 在这些卡上的兼容性. / SCNet: which accelerator models Notebook or containers actually offer (docs only say "heterogeneous accelerator cards"), whether NVIDIA cards exist, KataGo compatibility with them.
10. SCNet: 自定义服务端口的公网 URL 格式、是否 https、是否有鉴权、可用端口范围. / SCNet: public URL format of the custom service port, whether https, authentication, allowed port range.
11. SCNet: Notebook SSH 是否允许 `ssh -L`(文档只写密码登录,没写转发); HPC 登录节点是否允许端口转发. / SCNet: whether Notebook SSH allows `ssh -L` (docs only describe password login, not forwarding); whether HPC login nodes allow port forwarding.
12. SCNet: 价目表(元/卡时); 免费活动(100 卡时)今天是否仍有效(抓到的邀测页写 2026-02-05 至 2026-04-30,搜索摘要另给出 2026-07 的日期,二者不一致). / SCNet: the price table (CNY per card-hour); whether the free 100 card-hour activity is still valid today (the fetched beta page says 2026-02-05 to 2026-04-30, a search snippet gives a July 2026 date, the two disagree).
13. SCNet: 没有大陆身份证的用户能否通过实名认证; 是否需要高校或单位身份(协议未写). / SCNet: whether users without a mainland ID card can pass real-name verification; whether a university or institution affiliation is needed (the agreement does not say).
14. 天河: 天津和广州中心官网本次无法抓取(连接被拒绝/中断),现行的账号申请、登录节点规则、GPU 配置、端口转发、计费均只来自旧页面或搜索摘要. / Tianhe: the Tianjin and Guangzhou center sites could not be fetched (connection refused or reset), so current account application, login-node rules, GPU configuration, port forwarding and billing come only from old pages or search snippets.
15. 天河: 个人(非单位)能否申请账号; 长沙页面日期为 2018-04-16,流程可能已变. / Tianhe: whether an individual (not an institution) can apply; the Changsha page is dated 2018-04-16 and the process may have changed.
16. 启智/鹏城云脑: 官方帮助文档首页读取时为维护页,GPU 型号、调试任务时长(摘要称 4 小时)、算力积分规则(每日上限 100 与 50 两种说法)、在线推理是否可用、是否能开放自定义端口均未核实. / OpenI and Cloud Brain: the official help index was a maintenance page when read, so GPU models, debug-task duration (a snippet says 4 hours), points rules (daily cap given as both 100 and 50), whether online inference is usable and whether a custom port can be opened are not verified.
17. 启智: 使用协议原文中"内网穿透工具"的具体范围; 实名或手机认证要求. / OpenI: the exact scope of "intranet-penetration tools" in the agreement text; real-name or phone verification requirements.
18. 鹏城云脑: 谁可以使用、资源申请的条件和流程(首页只有栏目名). / Peng Cheng Cloud Brain: who may use it and the conditions and process of the resource application (the landing page shows only the section name).
19. 通用: 各浏览器对"https 页面访问 http://127.0.0.1"的实际处理(例如 Safari)未逐一核实,MDN 与 W3C 页面只给出回环地址属于潜在可信来源. / Generic: how each browser actually treats an https page calling http://127.0.0.1 (for example Safari) was not checked one by one; the MDN and W3C pages only establish that loopback addresses are potentially trustworthy.
20. 通用: 具体集群是否启用 pam_slurm_adopt、是否禁止 TCP 转发(sshd 的 AllowTcpForwarding 设置),以及交互作业时限. / Generic: whether a given cluster uses pam_slurm_adopt or forbids TCP forwarding (sshd AllowTcpForwarding), and its interactive time limits.

