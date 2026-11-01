# Cloud and compute platforms (with notes on LRZ) / 云与算力平台(含 LRZ 说明)

This extends `remote/README.md`, which is not in the repository yet (it lives in the local working directory). Sources were read on 2026-11-01. Prices and quotas should be checked on each provider's own page. Where something could not be checked it says "not verified". Every cost and run time below is an estimate, not a measurement. No account was created and KataGo was not run for this note.

本文是对 `remote/README.md` 的补充(那份文件还不在仓库里,目前只在本地工作目录中)。资料读取于 2026-11-01。价格和配额请以各平台自己的页面为准;查不到的地方写作"未核实"。下面所有的费用和耗时都是估计,不是实测。写这份说明时没有注册任何账号,也没有运行过 KataGo。

## 0. Short answer / 简短结论

1. The whole job (about 29 groups) needs roughly 1 to 4 GPU hours by estimate. Free quotas cover it, and in the worst case it costs a few dollars, so an expensive platform is not worth the effort.

   整个任务(约 29 个分组)按估计大约需要 1 到 4 个 GPU 小时。免费配额就够用,最坏情况也只花几美元,没必要折腾贵的平台。

2. Suggested order: Kaggle first (free, and "Save & Run All" runs in the background), then Colab free (needs you present with the page open), then a paid fallback such as Hugging Face Jobs, RunPod, Vast.ai or Modal (about 1 to 5 dollars for the whole batch, estimated).

   建议的顺序:先用 Kaggle(免费,"Save & Run All" 可以在后台跑),再用 Colab 免费版(需要你在场、页面保持打开),最后才是付费兜底,比如 Hugging Face Jobs、RunPod、Vast.ai 或 Modal(整批大约 1 到 5 美元,估计值)。

3. A failed LRZ application does not block anything. If LRZ is wanted, the fastest route is to be added by a project manager to an LRZ project that already has AI Systems enabled.

   LRZ 申请不下来也不影响进度。如果想用 LRZ,最快的办法是请已启用 AI Systems 的 LRZ 项目的管理员把你加进去。

4. Run batch jobs only. Do not use Colab or Kaggle as a server: tunnels, open ports and keep-alive scripts break or dodge the terms.

   只跑批处理任务。不要把 Colab 或 Kaggle 当服务器用:隧道、对外开端口、保活脚本都会违反或规避平台条款。

5. What to find out before a run is listed in section 3. It is all non-sensitive facts you can see after logging in yourself. Never share passwords, tokens, phone numbers or payment details with anyone.

   运行之前要确认哪些信息,列在第 3 节。全是你自己登录后能看到的非敏感信息。密码、令牌、手机号和付款信息,任何情况下都不要告诉别人。

## 1. How big is the job (estimate) / 任务规模(估计)

The numbers come from `remote/README.md`: on the local machine (a 780M integrated GPU with OpenCL) one search of 220 visits takes about 11 seconds, a group takes 30 to 40 minutes and the whole set about 15 to 19 hours.

数据来自 `remote/README.md`:在本机(780M 核显,走 OpenCL)上,一次 220 visits 的搜索大约要 11 秒,一个分组要 30 到 40 分钟,全部做完大约 15 到 19 小时。

| Quantity / 量 | Working / 推算 | Result (estimate) / 结果(估计) |
|---|---|---|
| Local throughput / 本机吞吐 | 220 visits / 11 s | about 20 visits per second / 约 20 visits/秒 |
| Number of searches / 搜索次数 | 15 to 19 h x 3600 s / 11 s | about 4,900 to 6,200 (170 to 215 per group) / 约 4,900 到 6,200 次(每组 170 到 215 次) |
| Total visits / 总 visits | searches x 220 / 搜索次数乘以 220 | about 1.1 to 1.4 million / 约 110 万到 140 万 |
| A T4 class GPU (the README guesses 5 to 15 times faster) / T4 级别的 GPU(README 估计快 5 到 15 倍) | 15 to 19 h divided by 5 to 15 / 15 到 19 小时除以 5 到 15 | about 1 to 4 h. Add time for downloading KataGo, installing libraries and retries, so plan for 2 to 6 h / 约 1 到 4 小时。再加上下载 KataGo、装库和重试的时间,按 2 到 6 小时预留 |
| A stronger GPU (L4, A10, 3090, 4090 and so on) / 更强的 GPU(L4、A10、3090、4090 等) | higher factor / 倍数更高 | about 0.5 to 2 h, but 220 visit searches cannot fill a big card, so a pricier GPU is not proportionally faster / 约 0.5 到 2 小时,但 220 visits 的小搜索喂不满大卡,所以更贵的 GPU 并不会按比例更快 |

No public benchmark for this network (b11c768 transformer) on these GPUs was found. A community data point (an RTX 4070, a b18 class network, 10,000 visit tests) shows 750 to 1,600 visits per second depending on thread count ([lifein19x19 summary](https://www.lifein19x19.com/viewtopic.php?p=278149)). It only shows that a modern GPU is one to two orders of magnitude above 20 visits per second and cannot be applied directly.

没有找到这个网络(b11c768 Transformer)在这些 GPU 上的公开基准。社区里有一个数据点(RTX 4070、b18 级别网络、1 万 visits 测试),随线程数不同是 750 到 1,600 visits/秒([lifein19x19 摘要](https://www.lifein19x19.com/viewtopic.php?p=278149))。它只能说明现代 GPU 比 20 visits/秒快一到两个数量级,不能直接照搬。

To calibrate, run the "trial of 3 branch points" cell first, then finish one group and read `seconds` in the `meta.json` in the output folder. Multiply by 29. Keep `--visits 220 --forced 100` and do not change the network, otherwise old and new results are not comparable (`remote/README.md`).

校准的办法:先跑"试跑 3 个分叉点"那个单元,再完整跑完一个分组,读输出目录里 `meta.json` 的 `seconds`,乘以 29。保持 `--visits 220 --forced 100`,不要换网络,否则新旧结果没法比较(见 `remote/README.md`)。

## 2. Platforms at a glance / 平台一览

| Platform / 平台 | GPU | Price or quota / 价格或配额 | Limits for batch work / 对批处理的限制 | Whole job (estimate) / 整批预计(估计) | Source / 来源 |
|---|---|---|---|---|---|
| Kaggle Notebooks | T4 (some pages say 2x T4) or P100 / T4(有的页面写 2 块 T4)或 P100 | Free. Weekly GPU quota is about 30 hours according to most sources (your account page shows the real number, the official docs page shows none). One session lasts 9 or 12 hours, sources disagree / 免费。多数来源说每周 GPU 配额约 30 小时(以你账号页面显示的为准,官方文档页没写数字)。单次会话 9 或 12 小时,来源不一致 | GPU and internet need phone verification (current rule not verified). "Save & Run All" runs in the background. An open source project reports tunnels were blocked / GPU 和联网需要手机验证(现行规则未核实)。"Save & Run All" 可以在后台跑。有开源项目报告隧道被封 | 0 dollars, uses about 1 to 4 h of quota / 0 美元,占用约 1 到 4 小时配额 | [Kaggle docs](https://www.kaggle.com/docs/notebooks), [third party roundup, 2026-09-21 / 第三方汇总](https://gpuperhour.com/blog/free-cloud-gpus-and-credits) |
| Colab free / Colab 免费版 | Usually a T4, not guaranteed / 通常是 T4,不保证 | Free. Quota, idle timeout and maximum session (about 12 h) are not published / 免费。配额、空闲超时和最长会话(约 12 小时)都不公布 | The FAQ forbids remote proxies, file hosting and web services, SSH or remote desktop on the free tier, "chess training", distributed computing workers and more, and a runtime can be stopped without warning / FAQ 禁止远程代理、文件托管和 Web 服务、免费版上的 SSH 或远程桌面、"chess training"、分布式计算 worker 等,运行时可能被无预警终止 | 0 dollars, you must stay present / 0 美元,但要人在场 | [Colab FAQ](https://research.google.com/colaboratory/faq.html) |
| Colab pay as you go or Pro / Colab 按量或 Pro | T4, L4, A100 | About 9.99 dollars per 100 compute units. A T4 burns about 1.2 units per hour (third party measurement from 2026-03, not checked against Google's page) / 约 9.99 美元 100 个计算单元。T4 每小时约消耗 1.2 个单元(2026-03 的第三方测量,没有对照过 Google 的页面) | Same as above. With a positive balance the SSH limits differ, but the "remote proxy or web service" ban stays / 同上。余额为正时 SSH 的限制不同,但"远程代理或 Web 服务"的禁令仍然有效 | A T4 at about 0.12 dollars per hour, so about 0.1 to 0.5 dollars / T4 约 0.12 美元/小时,整批约 0.1 到 0.5 美元 | [third party roundup / 第三方汇总](https://gpuperhour.com/blog/google-colab-alternatives) |
| Hugging Face Jobs | T4, L4, A10G, A100, L40S and more / 以及更多 | Billed per second. t4-small 0.40 dollars per hour, t4-medium 0.60, l4x1 0.80, a10g-small 1.00. Needs a positive balance / 按秒计费。t4-small 0.40 美元/小时,t4-medium 0.60,l4x1 0.80,a10g-small 1.00。账户余额必须为正 | The default timeout is 30 minutes, so always pass a timeout. Runs a Docker image and can mount Hub storage / 默认超时 30 分钟,所以一定要显式设置超时。运行 Docker 镜像,可以挂载 Hub 存储 | about 0.5 to 4 dollars / 约 0.5 到 4 美元 | [Jobs docs](https://huggingface.co/docs/huggingface_hub/guides/jobs) |
| RunPod | 3090, 4090, A40, L4, A100 and more / 以及更多 | Billed per second. 3090: community cloud 0.22 dollars per hour, secure cloud 0.50. 4090: 0.34 and 0.89 (which column is which was inferred from the page structure) / 按秒计费。3090:社区云 0.22 美元/小时,安全云 0.50。4090:0.34 和 0.89(哪一列对应哪种云是根据页面结构推断的) | You rent a whole machine, so no batch limits. The minimum top up is not stated on the page / 租的是整台机器,批处理没有限制。页面没写最低充值金额 | about 0.2 to 2 dollars / 约 0.2 到 2 美元 | [RunPod pricing](https://www.runpod.io/pricing) |
| Vast.ai | Many consumer and data centre cards / 各种消费级和数据中心显卡 | Marketplace prices, per second. Interruptible instances are advertised as 50 percent or more cheaper. A 4090 was about 0.40 dollars per hour in a third party snapshot from 2026-09-21 / 市场定价,按秒计费。可中断实例宣称便宜 50% 以上。第三方 2026-09-21 的快照里 4090 约 0.40 美元/小时 | Hosts belong to different providers, so keep sensitive data off them (this project only uploads board coordinates). Interruptible instances can be taken away, and the batch script resumes where it stopped / 主机来自不同的提供方,敏感数据不要放上去(本项目只上传棋盘坐标)。可中断实例可能被收回,批处理脚本支持断点续传 | about 0.2 to 2 dollars / 约 0.2 到 2 美元 | [Vast.ai pricing](https://vast.ai/pricing) |
| Modal | T4 0.59 dollars per hour, L4 0.80, A10 1.10, L40S 1.95, A100 2.10 to 2.50 (the page prices per second, the hourly figures are converted) / T4 0.59 美元/小时,L4 0.80,A10 1.10,L40S 1.95,A100 2.10 到 2.50(页面按秒标价,小时价是换算的) | The Starter plan has 30 dollars of free credit per month and a GPU concurrency of 10. Researchers can apply for academic credits (a third party says up to 10,000 dollars, not verified) / Starter 计划每月有 30 美元免费额度,GPU 并发上限 10。研究人员可以申请学术额度(第三方称最高 1 万美元,未核实) | Code first serverless platform that needs its Python SDK. Whether a card is required is not stated on the page / 以代码为先的无服务器平台,要用它的 Python SDK。页面没写是否必须绑卡 | Inside the free credit (about 0.6 to 2.4 dollars) / 在免费额度之内(约 0.6 到 2.4 美元) | [Modal pricing](https://modal.com/pricing) |
| Lightning AI | T4 0.55 dollars per hour, L4 0.79 (on demand) / T4 0.55 美元/小时,L4 0.79(按需) | The official page: up to 30 free credits (5 on sign up, 25 more after adding a card), roughly 80 GPU hours on interruptible machines, valid 12 months. A third party reports a price change on 2026-09-21 and that the rules keep moving / 官方页面:最多 30 个免费额度(注册送 5 个,绑卡后再送 25 个),在可中断机器上约 80 个 GPU 小时,12 个月有效。第三方报道 2026-09-21 调过价,而且规则一直在变 | A free Studio has to be restarted every 4 hours and a phone number is asked for. The page says nothing about ports or servers (not verified) / 免费 Studio 每 4 小时要重启一次,并且会要求手机号。页面没提端口或服务器的限制(未核实) | Possibly 0 inside the credit, else about 1 to 2 dollars / 在额度内可能是 0,否则约 1 到 2 美元 | [Lightning pricing](https://lightning.ai/pricing), [price change report (third party) / 调价报道(第三方)](https://www.usagepricing.com/blueprint/activity/lightning-ai-2026-09-21-gpu-rate-card-reprice) |
| Paperspace (DigitalOcean) | Free Quadro M4000 (8 GB, a 2015 card) / 免费的 Quadro M4000(8 GB,2015 年的显卡) | A free tier is still listed, availability is doubtful / 页面仍列出免费档,但是否有货存疑 | Free notebooks are public, so never put keys in them. A transformer network on an M4000 would be very slow / 免费笔记本是公开的,绝不能放密钥。Transformer 网络放在 M4000 上会非常慢 | Not recommended / 不推荐 | [DigitalOcean docs](https://docs.digitalocean.com/products/paperspace/pricing) |
| Hugging Face Spaces and ZeroGPU / Hugging Face Spaces 与 ZeroGPU | ZeroGPU only supports Gradio. A T4 small costs 0.40 dollars per hour / ZeroGPU 只支持 Gradio。T4 small 0.40 美元/小时 | Free accounts get about 5 minutes of ZeroGPU per day / 免费账号每天约有 5 分钟 ZeroGPU | Built for demos, not long jobs / 为演示设计,不适合长任务 | Not suitable, use Jobs / 不合适,改用 Jobs | [Spaces GPU docs](https://huggingface.co/docs/hub/spaces-gpus) |
| Amazon SageMaker Studio Lab | T4, 4 h per session and 4 h per 24 h / T4,每次 4 小时,每 24 小时最多 4 小时 | Free / 免费 | Closed to new users (second hand) / 对新用户关闭(二手信息) | Not available / 不可用 | [third party roundup / 第三方汇总](https://gpuperhour.com/blog/free-cloud-gpus-and-credits) |
| Google Cloud | | 300 dollars for 90 days for new accounts / 新账号 90 天内 300 美元 | Free trial accounts usually cannot use GPUs. After upgrading to a paid account a quota request is still needed, and community reports often mention a GPU quota of 0 or "not adjustable" / 免费试用账号通常不能用 GPU。升级成付费账号后还要申请配额,社区里常见"GPU 配额为 0"或"不可调整"的反馈 | Not recommended, too much hassle / 不推荐,太麻烦 | [community report / 社区反馈](https://discuss.google.dev/t/300-free-trial-is-useless-without-gpu-quota-my-trial-period-is-wasting-away/290091) |
| AWS | | Since July 2025 a new account on the free plan gets up to 200 dollars for 6 months / 2025 年 7 月起,新账号的免费计划最多 200 美元,6 个月 | The free plan restricts instance types and GPU instances are probably out (second hand, not verified) / 免费计划限制实例类型,GPU 实例大概率用不了(二手信息,未核实) | Not recommended / 不推荐 | [AWS announcement / AWS 公告](https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/) |
| Azure for Students | | 100 dollars for 12 months, no credit card / 100 美元,12 个月,不需要信用卡 | The default quota of a student subscription is 3 vCPUs and no GPU VMs. A paid upgrade plus a quota request may get you one / 学生订阅默认配额是 3 个 vCPU,没有 GPU 虚拟机。升级成付费并申请配额后才可能有 | Not recommended / 不推荐 | [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/2157302/clarification-on-gpu-access-after-upgrading-azure) |
| GitHub Student Developer Pack | | The page lists Azure 100 dollars (age 18 or older) and a Camber student plan with 5 GPU hours and 40 CPU hours per month. No DigitalOcean credit appeared on that page, check the live page / 页面列出了 Azure 100 美元(18 岁及以上)和 Camber 学生计划(每月 5 个 GPU 小时、40 个 CPU 小时)。那个页面上没有出现 DigitalOcean 的额度,请看实时页面 | Student status has to be verified (how is not stated) / 需要验证学生身份(怎么验证没写) | Cannot cover the whole job, a small extra / 覆盖不了整个任务,只是个小补充 | [Student Pack](https://education.github.com/pack) |
| LRZ AI Systems and BayernKI / LRZ AI Systems 与 BayernKI | V100 (16 GB), A100 (80 GB), H100 (94 GB) | The docs mention no charge / 文档里没提收费 | See section 5 / 见第 5 节 | Under 1 h once a job gets a slot / 作业排上队之后不到 1 小时 | [LRZ docs](https://doku.lrz.de/ai-systems-11484278.html) |
| Chinese platforms (ModelScope free GPU, Baidu AI Studio, Alibaba Tianchi) / 国内平台(魔搭 ModelScope 免费 GPU、百度 AI Studio、阿里天池) | Not verified / 未核实 | Not verified. A tutorial of unknown date mentions 36 free GPU hours after linking an Alibaba Cloud account / 未核实。有一篇日期不详的教程提到绑定阿里云账号后有 36 小时免费 GPU | Usually a mainland phone number and real name verification, not verified / 通常需要大陆手机号和实名认证,未核实 | Not assessed / 未评估 | A lead only / 仅作线索 |

How to pick: Kaggle first. If it cannot be opened or the phone is not verified, use Colab. If neither gives a GPU or both keep dropping, spend about 5 dollars on Hugging Face Jobs or RunPod and finish in one go.

怎么选:先用 Kaggle。打不开或者手机没验证,就用 Colab。如果两个都拿不到 GPU,或者老是掉线,就花 5 美元左右在 Hugging Face Jobs 或 RunPod 上一次跑完。

## 3. What to find out before a run / 运行之前要确认的信息

Principle: only facts you can see yourself after logging in. Do not pass on passwords, verification codes, tokens, API keys, phone numbers or card details. Blur emails and avatars in screenshots. Creating accounts, phone verification, payment and authorization are done by the account owner.

原则:只提供你自己登录后看得到的事实。不要转交密码、验证码、令牌、API Key、手机号或银行卡信息。截图里的邮箱和头像要打码。注册账号、手机验证、付款和授权,都由账号的主人自己完成。

### 3.1 General / 通用

| Question / 问题 | Why it matters / 为什么重要 |
|---|---|
| Can the current network open colab.research.google.com, kaggle.com and huggingface.co? / 当前网络能不能打开 colab.research.google.com、kaggle.com 和 huggingface.co? | Decides which one to try first / 决定先试哪一个 |
| Where was `kata1-tf3-b11c768-s12752M-d6531M.bin.gz` (262 MB) downloaded from? / `kata1-tf3-b11c768-s12752M-d6531M.bin.gz`(262 MB)是从哪里下载的? | Needed to confirm its license, see `docs/LICENSE-ADVICE.md` section 5 / 要据此确认它的许可证,见 `docs/LICENSE-ADVICE.md` 第 5 节 |
| How big is `n_json.zip` in MB? / `n_json.zip` 有多少 MB? | Decides where to upload it / 决定传到哪里 |
| A budget limit (one number such as "5 dollars") and whether adding a payment method is acceptable / 预算上限(一个数字,比如"5 美元"),以及能不能接受绑定付款方式 | Decides whether the paid fallback is on the table / 决定能不能用付费兜底 |
| A short trial while present, or submit and walk away? / 是人在场短时间试跑,还是提交后走开? | Decides between Colab and Kaggle / 决定选 Colab 还是 Kaggle |

### 3.2 Kaggle (first choice) / Kaggle(首选)

1. Sign in at kaggle.com with your own account.

   用你自己的账号登录 kaggle.com。

2. Open the profile menu, then Settings, and find the phone verification entry. Note only "verified" or "not verified", never the number. Complete it yourself if needed.

   打开个人菜单,进入 Settings,找到手机验证一项。只记录"已验证"或"未验证",不要记号码。需要的话自己完成验证。

3. Create a new notebook. In Session options check whether Accelerator offers a GPU (T4 or P100) and whether the Internet switch can be turned on.

   新建一个 notebook。在 Session options 里看 Accelerator 能不能选 GPU(T4 或 P100),Internet 开关能不能打开。

4. In the notebook run these two lines and keep the output:

   在 notebook 里运行下面两行,并保留输出:

   ```
   !nvidia-smi
   !df -h /kaggle/working | tail -1
   ```

5. Find the GPU quota display (used and total hours, reset day) in the account settings or the session menu and note the numbers.

   在账号设置或会话菜单里找到 GPU 配额的显示(已用和总共的小时数、重置日期),记下数字。

6. Create two private datasets, one with the weights file and one with `n_json.zip`, and note that they are uploaded and how big they are.

   建两个私有的 Dataset,一个放权重文件,一个放 `n_json.zip`,记下已经上传以及各自的大小。

What these answers decide: which KataGo build to use (a T4 and a P100 differ in CUDA capability), the `--batch` and thread values, how many groups fit in one session, and whether several "Save & Run All" rounds are needed.

这些答案决定的事情:用哪个 KataGo 构建(T4 和 P100 的 CUDA 能力不同)、`--batch` 和线程数怎么设、一次会话能跑几个分组,以及要不要分几轮 "Save & Run All"。

### 3.3 Colab

1. Open colab.research.google.com with your own Google account and upload `remote/katago_batch.ipynb`.

   用你自己的 Google 账号打开 colab.research.google.com,上传 `remote/katago_batch.ipynb`。

2. Runtime, Change runtime type, choose T4 GPU. If it cannot be chosen or it says no GPU is available or the usage limit was reached, note the message word for word.

   依次选 Runtime、Change runtime type,选 T4 GPU。如果选不了,或者提示没有可用的 GPU、已达使用上限,把提示原文记下来。

3. In a new code cell run these and keep the output:

   在新的代码单元里运行下面这些,并保留输出:

   ```
   !nvidia-smi
   !df -h /content | tail -1
   !free -h | head -2
   ```

4. To protect progress against disconnects with Drive: note the free space (bottom left of drive.google.com) and the folder name you will use, for example `MyDrive/josekiapp/`. The authorization dialog is yours to accept.

   想用 Drive 防止断线丢进度:记下剩余空间(drive.google.com 左下角)和你打算用的文件夹名,例如 `MyDrive/josekiapp/`。授权对话框由你自己点同意。

5. With Pro or pay as you go: note the compute unit balance.

   如果订阅了 Pro 或按量付费:记下计算单元的余额。

6. While it runs keep the page open and stay nearby. After a disconnect reconnect and rerun all cells, finished groups are skipped.

   运行期间保持页面打开,人别走远。断线之后重新连接并重跑所有单元,已完成的分组会被跳过。

### 3.4 Paid fallbacks / 付费兜底

| Platform / 平台 | What the account owner does / 账号主人要做的 | What to note down (non sensitive) / 要记下的(非敏感信息) |
|---|---|---|
| Hugging Face Jobs | Sign up, top up a small amount (for example 5 dollars) in Billing, log in with `hf auth login` on your own computer. Keep the token private / 注册,在 Billing 里小额充值(比如 5 美元),在自己的电脑上用 `hf auth login` 登录。令牌要保密 | The balance and the flavor chosen (for example `t4-small`) / 余额和所选的 flavor(比如 `t4-small`) |
| RunPod | Sign up and top up, start a Pod from a PyTorch or CUDA template, open the web terminal or SSH command / 注册并充值,用 PyTorch 或 CUDA 模板启动一个 Pod,打开网页终端或 SSH 命令 | The GPU model and hourly price, and the `nvidia-smi` output / GPU 型号和每小时价格,以及 `nvidia-smi` 的输出 |
| Vast.ai | The same, prefer data centre or well rated hosts / 同上,优先选数据中心或评分高的主机 | The same, plus on demand or interruptible / 同上,另外记下是按需还是可中断实例 |
| Modal | Sign up and log in from your own terminal through the browser / 注册,在自己的终端里通过浏览器完成登录 | The remaining free credit and whether a card was needed / 剩余的免费额度,以及是否需要绑卡 |
| Lightning AI | Sign up and finish phone verification / 注册并完成手机验证 | The credit balance, whether a Studio can use a GPU and open a terminal / 额度余额,以及 Studio 能不能用 GPU、能不能打开终端 |

### 3.5 GitHub Student Developer Pack (optional) / GitHub 学生开发者包(可选)

On education.github.com/pack note whether student verification went through, and copy the names and amounts of any cloud or GPU benefits shown.

在 education.github.com/pack 上记下学生身份验证是否通过,并抄下页面上云或 GPU 相关福利的名称和额度。

### 3.6 LRZ (only if you apply) / LRZ(只在你确实去申请时)

Note whether you have an LRZ account, whether you were added to a project with AI Systems enabled (yes or no), the output of `sinfo` on the login node (partition names), the output of `nvidia-smi` on a compute node, and whether a compute node can reach the internet (does `curl -I https://github.com` work). Do not share SSH private keys, passwords or VPN credentials.

记下:你有没有 LRZ 账号,有没有被加入启用了 AI Systems 的项目(是或否),登录节点上 `sinfo` 的输出(分区名),计算节点上 `nvidia-smi` 的输出,以及计算节点能不能访问互联网(`curl -I https://github.com` 通不通)。SSH 私钥、密码和 VPN 凭据不要告诉任何人。

## 4. Terms and risks per platform / 各平台的条款与风险

- Colab: see the FAQ. KataGo analysis is neither training nor a distributed worker, and running a batch in a notebook then downloading the result counts as interactive computing, but that is a reading of the FAQ and not a guarantee from Google. Do not open tunnels, use `colab_ssh`, keep-alive scripts or extra accounts to get around limits. When it says the usage limit has been reached, stop.

  Colab:见 FAQ。KataGo 分析既不是训练,也不是分布式 worker;在 notebook 里跑批处理再下载结果,算交互式计算,但这只是我对 FAQ 的理解,不是 Google 的保证。不要为了绕过限制去开隧道、用 `colab_ssh`、跑保活脚本或者多开账号。提示已达使用上限就停。

- Kaggle: the official docs pages are rendered by the browser and the text with quota and session length could not be read, so the numbers above come from third party roundups. Trust what your own account shows. No multiple accounts, no tunnels.

  Kaggle:官方文档页面由浏览器渲染,配额和会话时长的文字没能读到,所以上面的数字来自第三方汇总,请以你自己账号里显示的为准。不要多开账号,不要用隧道。

- Hugging Face Jobs: always set a timeout (the default 30 minutes stops the job). Write output to a mounted bucket or a Hub repo, because the container's files are gone afterwards. Library compatibility of KataGo inside the image has not been tested.

  Hugging Face Jobs:一定要设置超时(默认 30 分钟就会把作业停掉)。输出要写到挂载的存储桶或 Hub 仓库,因为容器里的文件之后就没了。KataGo 在镜像里的库兼容性没有测试过。

- RunPod and Vast.ai: stop and delete the instance when done, because disks keep billing. Never sign in to personal accounts or leave private keys on a rented machine.

  RunPod 和 Vast.ai:用完要停止并删除实例,因为磁盘会继续计费。不要在租来的机器上登录个人账号,也不要留下私钥。

- Everywhere: upload only board coordinates (`n.json`) and the weights. Do not upload videos or transcripts (copyright, see `docs/LICENSE-ADVICE.md`). Clear credentials and temporary files after downloading the results.

  所有平台通用:只上传棋盘坐标(`n.json`)和权重,不要上传视频或转写文字(版权问题,见 `docs/LICENSE-ADVICE.md`)。下载完结果后,清掉凭据和临时文件。

- Weights: the KataGo license for official networks is permissive, but networks from other contributors may have no clear terms ([network license](https://katagotraining.org/network_license/)). Confirm which kind your file is before putting it anywhere public. Private datasets and repos are not affected.

  权重:KataGo 官方网络的许可证很宽松,但其他贡献者的网络可能没有明确条款([网络许可证](https://katagotraining.org/network_license/))。放到任何公开的地方之前,先确认你的文件属于哪一类。私有的 Dataset 和仓库不受影响。

## 5. LRZ and BayernKI: when the application may not go through / LRZ 与 BayernKI:申请可能不通过时

### 5.1 Routes and eligibility (from the official docs) / 渠道与资格(来自官方文档)

- LRZ AI Systems needs a valid LRZ account that belongs to an LRZ project with AI Systems enabled. The page asks applicants to show a clear research focus. It does not mention students, and it is written for project leaders (PIs) and project managers (Master Users), with ordinary users joining through the Master User ([LRZ access page](https://doku.lrz.de/1-access-10746642.html)). `remote/README.md` already says that TUM and LMU student accounts by default cover mail and storage but not the high performance systems.

  LRZ AI Systems 需要一个有效的 LRZ 账号,并且账号属于启用了 AI Systems 的 LRZ 项目。页面要求申请者说明工作有明确的科研方向。页面没有提学生,它是写给项目负责人(PI)和项目管理员(Master User)的,普通用户通过 Master User 加入([LRZ 申请页](https://doku.lrz.de/1-access-10746642.html))。`remote/README.md` 里已经写了:TUM 和 LMU 的学生账号默认只能用邮件和存储这类服务,不能用高性能系统。

- Fastest route: ask your course, practical or thesis supervisor. Their project's Master User can add you to the group `<project id>-ai-c`. Or ask them to enable AI Systems for an existing project through the service desk form "AI Systems Project Activation/Update". Old projects with many members often do not qualify.

  最快的路:去问你的课程、实践课或论文导师。他们项目的 Master User 可以把你加进 `<project id>-ai-c` 这个组;或者请他们通过服务台的表单 "AI Systems Project Activation/Update" 给已有项目启用 AI Systems。成员很多的老项目往往不符合条件。

- A new project: the PI fills in the LRZ project application form, writes "AI Systems" in the remarks, and sends a follow-up request to enable AI access once the project exists.

  新项目:由 PI 填写 LRZ 项目申请表,在备注里写 "AI Systems",项目建好之后再发一个后续请求来启用 AI 访问。

- BayernKI: for researchers at state universities and universities of applied sciences in Bavaria, applied for through NHR@FAU, with LRZ or NHR@FAU as the preferred centre. One application per research group, and the PI and contact person have to log in to the NHR@FAU HPC portal first (taken from a search summary, because the application page itself returned 404 here, so the latest rules are not verified). Resources: about 120 H100 at LRZ and about 200 H100 at FAU according to the same source ([NHR@FAU BayernKI](https://hpc.fau.de/application-for-bayernki-access)).

  BayernKI:面向巴伐利亚州立大学和应用科学大学的研究人员,通过 NHR@FAU 申请,可以选 LRZ 或 NHR@FAU 作为首选中心。每个研究组只提交一份申请,PI 和联系人要先登录 NHR@FAU 的 HPC 门户(这些内容来自搜索摘要,因为申请页本身在这里返回 404,所以最新规则未核实)。资源:同一来源称 LRZ 约有 120 块 H100,FAU 约有 200 块 H100([NHR@FAU BayernKI](https://hpc.fau.de/application-for-bayernki-access))。

- Review time: the LRZ page only says suitability is assessed from what you provide and gives no time. Projects expire after a year and have to be renewed.

  审批时间:LRZ 页面只说会根据你提供的信息评估是否合适,没有给出时间。项目一年后到期,需要续期。

- Network: logging in to `login.ai.lrz.de` works from inside the Munich Scientific Network (MWN) or through VPN. Membership of the `-ai-c` group includes VPN access.

  网络:登录 `login.ai.lrz.de` 要在慕尼黑科学网(MWN)内部,或者走 VPN。属于 `-ai-c` 组就包含 VPN 访问权限。

- Status: AI Systems is in pilot operation, and the docs list a planned maintenance window from 2026-11-23 to 2026-11-25.

  状态:AI Systems 目前处于试点运行,文档里列出了 2026-11-23 到 2026-11-25 的计划维护窗口。

### 5.2 If it is refused or slow / 被拒或迟迟没有回音时

1. Kaggle or Colab (free), or Hugging Face Jobs, RunPod, Vast.ai (a few dollars), see section 2.

   用 Kaggle 或 Colab(免费),或者 Hugging Face Jobs、RunPod、Vast.ai(几美元),见第 2 节。

2. Ask your chair or research group whether it has its own GPU server or cluster accounts (what TUM offers internally was not verified).

   问问你所在的教席或研究组有没有自己的 GPU 服务器或集群账号(TUM 内部提供什么,未核实)。

3. NHR@FAU Alex: search results suggest FAU members have their own Tier 3 route and that test projects are open or closed to university members depending on the source (not verified). You are not an FAU member, so look at the BayernKI and NHR rules.

   NHR@FAU 的 Alex 集群:搜索结果显示 FAU 成员有单独的 Tier 3 申请通道,测试项目对高校成员是否开放则因来源而异(未核实)。你不是 FAU 成员,所以要看 BayernKI 和 NHR 的规则。

4. A line for your supervisor: "I am running a small project that analyses Go joseki with KataGo, about 1 to 4 GPU hours of batch work on a single card. Could you add me to your LRZ project with AI Systems enabled? I will only use Slurm batch jobs and follow the usage rules."

   给导师的一句话:"我在做一个用 KataGo 分析围棋定式的小项目,只是单卡上大约 1 到 4 个 GPU 小时的批处理。能不能把我加进您那个启用了 AI Systems 的 LRZ 项目?我只会用 Slurm 批处理作业,并遵守使用规定。"

### 5.3 When you do get an account / 真拿到账号之后

- Do not run computation on the login node. Use it to copy files, set up the environment and submit jobs, and run KataGo and transcription with `sbatch`, `srun` or `salloc` on compute nodes. This is the usual HPC rule. The LRZ usage policy page could not be read, so its exact wording is not verified, follow their "Usage Policies".

  不要在登录节点上跑计算。登录节点只用来拷文件、搭环境和提交作业;KataGo 和转写都要用 `sbatch`、`srun` 或 `salloc` 放到计算节点上跑。这是 HPC 的通用规矩。LRZ 的使用政策页面没能读到,具体措辞未核实,请以他们的 "Usage Policies" 为准。

- Partitions and time: every partition except `lrz-cpu` needs `--gres=gpu:1`. The default time is 1 hour and the maximum is 2 days (`--time=2-00:00:00`). The default partition is `lrz-v100x2` (2 x V100 16 GB). A100 and H100 partition names carry the memory and GPU count, for example `lrz-hgx-h100-94x4`. Partitions starting with `MCML` are for partners only and those with `test` are internal. Names may change, so trust `sinfo` on the login node ([LRZ resources page](https://doku.lrz.de/1-general-description-and-resources-10746641.html), [compute page summary](https://doku.lrz.de/2-compute-10746641.html)).

  分区和时间:除 `lrz-cpu` 之外,所有分区都要写 `--gres=gpu:1`。默认时长 1 小时,最长 2 天(`--time=2-00:00:00`)。默认分区是 `lrz-v100x2`(2 块 V100 16 GB)。A100 和 H100 的分区名里带显存和卡数,例如 `lrz-hgx-h100-94x4`。以 `MCML` 开头的分区只对合作方开放,带 `test` 的是内部分区。分区名可能会变,以登录节点上的 `sinfo` 为准([LRZ 资源页](https://doku.lrz.de/1-general-description-and-resources-10746641.html)、[Compute 页摘要](https://doku.lrz.de/2-compute-10746641.html))。

- This job needs one card. Ask for one GPU and a short time (try `--time=00:20:00` first). It queues much faster and is more polite. The 29 groups can be split into a `--array` of small jobs, and `analyze_remote.py` resumes, skipping groups that are already done.

  这个任务只要一块卡。申请一块 GPU 和较短的时间(先试 `--time=00:20:00`),排队快得多,也更礼貌。29 个分组可以拆成 `--array` 的一组小作业,`analyze_remote.py` 支持续跑,会跳过已经完成的分组。

- Containers: Enroot with pyxis (`srun --container-image=...`), images can be imported from NGC. KataGo needs matching CUDA and cuDNN (transformer networks need cuDNN 9.8 or newer, see the troubleshooting in `remote/README.md`). Never put credentials into an image or job script.

  容器:用 Enroot 加 pyxis(`srun --container-image=...`),镜像可以从 NGC 导入。KataGo 需要匹配的 CUDA 和 cuDNN(Transformer 网络需要 cuDNN 9.8 或更新,见 `remote/README.md` 的排障部分)。凭据绝不能写进镜像或作业脚本。

- Internet from compute nodes was not found in the docs (not verified). Plan for no internet: download KataGo and the weights on the login node first and let the job read local files only. `slurm_analyze.sbatch` is written like this, but it has not been tested on the real system.

  计算节点能否联网,文档里没有找到(未核实)。按"不能联网"来规划:先在登录节点下载好 KataGo 和权重,作业只读本地文件。`slurm_analyze.sbatch` 就是这样写的,但还没有在真实系统上测试过。

- Data policy: shared storage (DSS) is tight, so keep only what you need and delete the rest. Do not put copyrighted material there. Videos and transcripts stay on your machine and only `n.json` (board coordinates) and the weights go up. Describe the purpose honestly as a small research or course project on Go joseki analysis.

  数据政策:共享存储(DSS)很紧张,只留需要的,其余及时删掉。不要把有版权的材料放上去。视频和转写文字留在你自己的机器上,只上传 `n.json`(棋盘坐标)和权重。用途要如实写成一个围棋定式分析的小型科研或课程项目。

- Credentials: log in with an SSH key and keep the private key out of the repo, cloud drives and chats. Do not share the account. Keep tokens in environment variables or a password manager.

  凭据:用 SSH 密钥登录,私钥不要放进仓库、云盘或聊天记录。不要共用账号。令牌放在环境变量或密码管理器里。

- Quota and queue: use fair amounts. Do not fill the queue with one huge array. If a job fails, read the log before resubmitting and never resubmit the same failing job in a loop.

  配额和排队:用量要合理,不要用一个巨大的 array 把队列塞满。作业失败了,先看日志再重新提交,不要对同一个必然失败的作业循环重提。

- Compliance: follow the LRZ terms and the export control declaration that `remote/README.md` mentions. Projects expire after a year. Student accounts can lapse when your status changes, so copy results out in time.

  合规:遵守 LRZ 的条款以及 `remote/README.md` 提到的出口管制声明。项目一年后到期。学生账号可能随身份变化而失效,所以要及时把结果拷出来。

- Acknowledgement: BayernKI and LRZ resources usually ask for a credit in results. The wording is not verified, check the welcome mail.

  致谢:使用 BayernKI 和 LRZ 的资源,通常要求在成果里致谢。具体措辞未核实,请看欢迎邮件。

## 6. A minimal plan / 最小行动方案

1. Settle the answers in sections 3.1 and 3.2 (or 3.3).

   把 3.1 和 3.2(或 3.3)里的问题都弄清楚。

2. Run the trial cell of `remote/katago_batch.ipynb` on Kaggle or Colab and note the speed.

   在 Kaggle 或 Colab 上运行 `remote/katago_batch.ipynb` 的试跑单元,记下速度。

3. Decide from the speed: run everything at once, run in a few rounds, or use a paid fallback.

   根据速度决定:一次跑完,分几轮跑,还是改用付费兜底。

4. Download `g_*.a2.json` to the local machine, follow the existing steps (`regen.py`, then `tools/build.ps1`), and commit on a `data/<batch>` branch as described in `docs/WORKFLOW.md`.

   把 `g_*.a2.json` 下载到本机,按现有步骤处理(先 `regen.py`,再 `tools/build.ps1`),然后按 `docs/WORKFLOW.md` 的说明,在 `data/<batch>` 分支上提交。

## Not verified / 未核实项

- Kaggle's current weekly quota, the session length (9 or 12 hours) and the current phone verification rules for GPU and internet.

  Kaggle 当前的每周配额、会话时长(9 还是 12 小时),以及 GPU 和联网现行的手机验证规则。

- Colab pay as you go GPU unit rates (only third party measurements).

  Colab 按量付费的 GPU 单元消耗率(只有第三方测量)。

- The latest Lightning AI free credit rules.

  Lightning AI 最新的免费额度规则。

- Live Vast.ai prices. The secure and community columns in the RunPod price table are inferred.

  Vast.ai 的实时价格。RunPod 价格表里"安全云"和"社区云"两列的对应关系是推断出来的。

- Whether Modal requires a payment method, and the academic credit amount.

  Modal 是否必须绑定付款方式,以及学术额度的金额。

- AWS free plan limits on GPU instances (second hand).

  AWS 免费计划对 GPU 实例的限制(二手信息)。

- LRZ: internet from compute nodes, the usage policy text, review time. BayernKI's latest application details. Other GPU resources inside TUM.

  LRZ:计算节点能否联网、使用政策原文、审批时间;BayernKI 最新的申请细则;TUM 内部其他的 GPU 资源。

- Free quotas and real name rules of Chinese platforms.

  国内平台的免费额度和实名规则。

- All speeds and costs: they are extrapolated from the local numbers in `remote/README.md`, and no cloud GPU was measured.

  所有速度和费用:都是从 `remote/README.md` 里的本机数字外推出来的,没有实测任何云 GPU。

## Sources (visited 2026-11-01) / 来源(2026-11-01 访问)

- Colab FAQ: https://research.google.com/colaboratory/faq.html. Third party price roundup / 第三方价格汇总: https://gpuperhour.com/blog/google-colab-alternatives
- Kaggle: https://www.kaggle.com/docs/notebooks (rendered in the browser, the body text could not be read / 由浏览器渲染,没能读到正文). Third party roundup / 第三方汇总: https://gpuperhour.com/blog/free-cloud-gpus-and-credits
- Hugging Face Jobs: https://huggingface.co/docs/huggingface_hub/guides/jobs. Spaces GPUs: https://huggingface.co/docs/hub/spaces-gpus
- RunPod: https://www.runpod.io/pricing. Vast.ai: https://vast.ai/pricing. Modal: https://modal.com/pricing. Lightning AI: https://lightning.ai/pricing
- Paperspace: https://docs.digitalocean.com/products/paperspace/pricing
- Google Cloud free trial and GPU quota (community report) / Google Cloud 免费试用与 GPU 配额(社区反馈): https://discuss.google.dev/t/300-free-trial-is-useless-without-gpu-quota-my-trial-period-is-wasting-away/290091. AWS free plan / AWS 免费计划: https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/. Azure student GPU quota / Azure 学生 GPU 配额: https://learn.microsoft.com/en-us/answers/questions/2157302/clarification-on-gpu-access-after-upgrading-azure
- GitHub Student Developer Pack: https://education.github.com/pack. Eligibility / 资格: https://docs.github.com/en/education/about-github-education/github-education-for-students/about-github-education-for-students
- LRZ AI Systems: https://doku.lrz.de/ai-systems-11484278.html, access / 申请 https://doku.lrz.de/1-access-10746642.html, resources and partitions / 资源与分区 https://doku.lrz.de/1-general-description-and-resources-10746641.html, compute https://doku.lrz.de/2-compute-10746641.html
- BayernKI and NHR@FAU: https://hpc.fau.de/application-for-bayernki-access and https://doc.nhr.fau.de/bayernki-application/
- KataGo network license / KataGo 网络许可证: https://katagotraining.org/network_license/. The KataGo release notes (transformer, CUDA) are in the source list of `remote/README.md` / KataGo 的发布说明(Transformer、CUDA)见 `remote/README.md` 的来源列表
- Community speed data point (old, different network) / 社区速度数据点(较旧,网络不同): https://www.lifein19x19.com/viewtopic.php?p=278149
