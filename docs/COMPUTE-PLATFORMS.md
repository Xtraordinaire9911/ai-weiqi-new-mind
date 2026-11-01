# Cloud and compute platforms (with notes on LRZ)

This extends `remote/README.md`, which is not in the repository yet (it lives in the local working directory). Sources were read on 2026-11-01. Prices and quotas should be checked on each provider's own page. Where something could not be checked it says "not verified". Every cost and run time below is an estimate, not a measurement. No account was created and KataGo was not run for this note.

## 0. Short answer

1. The whole job (about 29 groups) needs roughly 1 to 4 GPU hours by estimate. Free quotas cover it, and in the worst case it costs a few dollars, so an expensive platform is not worth the effort.
2. Suggested order: Kaggle first (free, and "Save & Run All" runs in the background), then Colab free (needs you present with the page open), then a paid fallback such as Hugging Face Jobs, RunPod, Vast.ai or Modal (about 1 to 5 dollars for the whole batch, estimated).
3. A failed LRZ application does not block anything. If LRZ is wanted, the fastest route is to be added by a project manager to an LRZ project that already has AI Systems enabled.
4. Run batch jobs only. Do not use Colab or Kaggle as a server: tunnels, open ports and keep-alive scripts break or dodge the terms.
5. What to find out before a run is listed in section 3. It is all non-sensitive facts you can see after logging in yourself. Never share passwords, tokens, phone numbers or payment details with anyone.

## 1. How big is the job (estimate)

The numbers come from `remote/README.md`: on the local machine (a 780M integrated GPU with OpenCL) one search of 220 visits takes about 11 seconds, a group takes 30 to 40 minutes and the whole set about 15 to 19 hours.

| Quantity | Working | Result (estimate) |
|---|---|---|
| Local throughput | 220 visits / 11 s | about 20 visits per second |
| Number of searches | 15 to 19 h x 3600 s / 11 s | about 4,900 to 6,200 (170 to 215 per group) |
| Total visits | searches x 220 | about 1.1 to 1.4 million |
| A T4 class GPU (the README guesses 5 to 15 times faster) | 15 to 19 h divided by 5 to 15 | about 1 to 4 h. Add time for downloading KataGo, installing libraries and retries, so plan for 2 to 6 h |
| A stronger GPU (L4, A10, 3090, 4090 and so on) | higher factor | about 0.5 to 2 h, but 220 visit searches cannot fill a big card, so a pricier GPU is not proportionally faster |

No public benchmark for this network (b11c768 transformer) on these GPUs was found. A community data point (an RTX 4070, a b18 class network, 10,000 visit tests) shows 750 to 1,600 visits per second depending on thread count ([lifein19x19 summary](https://www.lifein19x19.com/viewtopic.php?p=278149)). It only shows that a modern GPU is one to two orders of magnitude above 20 visits per second and cannot be applied directly.

To calibrate, run the "trial of 3 branch points" cell first, then finish one group and read `seconds` in the `meta.json` in the output folder. Multiply by 29. Keep `--visits 220 --forced 100` and do not change the network, otherwise old and new results are not comparable (`remote/README.md`).

## 2. Platforms at a glance

| Platform | GPU | Price or quota | Limits for batch work | Whole job (estimate) | Source |
|---|---|---|---|---|---|
| Kaggle Notebooks | T4 (some pages say 2x T4) or P100 | Free. Weekly GPU quota is about 30 hours according to most sources (your account page shows the real number, the official docs page shows none). One session lasts 9 or 12 hours, sources disagree | GPU and internet need phone verification (current rule not verified). "Save & Run All" runs in the background. An open source project reports tunnels were blocked | 0 dollars, uses about 1 to 4 h of quota | [Kaggle docs](https://www.kaggle.com/docs/notebooks), [third party roundup, 2026-09-21](https://gpuperhour.com/blog/free-cloud-gpus-and-credits) |
| Colab free | Usually a T4, not guaranteed | Free. Quota, idle timeout and maximum session (about 12 h) are not published | The FAQ forbids remote proxies, file hosting and web services, SSH or remote desktop on the free tier, "chess training", distributed computing workers and more, and a runtime can be stopped without warning | 0 dollars, you must stay present | [Colab FAQ](https://research.google.com/colaboratory/faq.html) |
| Colab pay as you go or Pro | T4, L4, A100 | About 9.99 dollars per 100 compute units. A T4 burns about 1.2 units per hour (third party measurement from 2026-03, not checked against Google's page) | Same as above. With a positive balance the SSH limits differ, but the "remote proxy or web service" ban stays | A T4 at about 0.12 dollars per hour, so about 0.1 to 0.5 dollars | [third party roundup](https://gpuperhour.com/blog/google-colab-alternatives) |
| Hugging Face Jobs | T4, L4, A10G, A100, L40S and more | Billed per second. t4-small 0.40 dollars per hour, t4-medium 0.60, l4x1 0.80, a10g-small 1.00. Needs a positive balance | The default timeout is 30 minutes, so always pass a timeout. Runs a Docker image and can mount Hub storage | about 0.5 to 4 dollars | [Jobs docs](https://huggingface.co/docs/huggingface_hub/guides/jobs) |
| RunPod | 3090, 4090, A40, L4, A100 and more | Billed per second. 3090: community cloud 0.22 dollars per hour, secure cloud 0.50. 4090: 0.34 and 0.89 (which column is which was inferred from the page structure) | You rent a whole machine, so no batch limits. The minimum top up is not stated on the page | about 0.2 to 2 dollars | [RunPod pricing](https://www.runpod.io/pricing) |
| Vast.ai | Many consumer and data centre cards | Marketplace prices, per second. Interruptible instances are advertised as 50 percent or more cheaper. A 4090 was about 0.40 dollars per hour in a third party snapshot from 2026-09-21 | Hosts belong to different providers, so keep sensitive data off them (this project only uploads board coordinates). Interruptible instances can be taken away, and the batch script resumes where it stopped | about 0.2 to 2 dollars | [Vast.ai pricing](https://vast.ai/pricing) |
| Modal | T4 0.59 dollars per hour, L4 0.80, A10 1.10, L40S 1.95, A100 2.10 to 2.50 (the page prices per second, the hourly figures are converted) | The Starter plan has 30 dollars of free credit per month and a GPU concurrency of 10. Researchers can apply for academic credits (a third party says up to 10,000 dollars, not verified) | Code first serverless platform that needs its Python SDK. Whether a card is required is not stated on the page | Inside the free credit (about 0.6 to 2.4 dollars) | [Modal pricing](https://modal.com/pricing) |
| Lightning AI | T4 0.55 dollars per hour, L4 0.79 (on demand) | The official page: up to 30 free credits (5 on sign up, 25 more after adding a card), roughly 80 GPU hours on interruptible machines, valid 12 months. A third party reports a price change on 2026-09-21 and that the rules keep moving | A free Studio has to be restarted every 4 hours and a phone number is asked for. The page says nothing about ports or servers (not verified) | Possibly 0 inside the credit, else about 1 to 2 dollars | [Lightning pricing](https://lightning.ai/pricing), [price change report (third party)](https://www.usagepricing.com/blueprint/activity/lightning-ai-2026-09-21-gpu-rate-card-reprice) |
| Paperspace (DigitalOcean) | Free Quadro M4000 (8 GB, a 2015 card) | A free tier is still listed, availability is doubtful | Free notebooks are public, so never put keys in them. A transformer network on an M4000 would be very slow | Not recommended | [DigitalOcean docs](https://docs.digitalocean.com/products/paperspace/pricing) |
| Hugging Face Spaces and ZeroGPU | ZeroGPU only supports Gradio. A T4 small costs 0.40 dollars per hour | Free accounts get about 5 minutes of ZeroGPU per day | Built for demos, not long jobs | Not suitable, use Jobs | [Spaces GPU docs](https://huggingface.co/docs/hub/spaces-gpus) |
| Amazon SageMaker Studio Lab | T4, 4 h per session and 4 h per 24 h | Free | Closed to new users (second hand) | Not available | [third party roundup](https://gpuperhour.com/blog/free-cloud-gpus-and-credits) |
| Google Cloud | | 300 dollars for 90 days for new accounts | Free trial accounts usually cannot use GPUs. After upgrading to a paid account a quota request is still needed, and community reports often mention a GPU quota of 0 or "not adjustable" | Not recommended, too much hassle | [community report](https://discuss.google.dev/t/300-free-trial-is-useless-without-gpu-quota-my-trial-period-is-wasting-away/290091) |
| AWS | | Since July 2025 a new account on the free plan gets up to 200 dollars for 6 months | The free plan restricts instance types and GPU instances are probably out (second hand, not verified) | Not recommended | [AWS announcement](https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/) |
| Azure for Students | | 100 dollars for 12 months, no credit card | The default quota of a student subscription is 3 vCPUs and no GPU VMs. A paid upgrade plus a quota request may get you one | Not recommended | [Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/2157302/clarification-on-gpu-access-after-upgrading-azure) |
| GitHub Student Developer Pack | | The page lists Azure 100 dollars (age 18 or older) and a Camber student plan with 5 GPU hours and 40 CPU hours per month. No DigitalOcean credit appeared on that page, check the live page | Student status has to be verified (how is not stated) | Cannot cover the whole job, a small extra | [Student Pack](https://education.github.com/pack) |
| LRZ AI Systems and BayernKI | V100 (16 GB), A100 (80 GB), H100 (94 GB) | The docs mention no charge | See section 5 | Under 1 h once a job gets a slot | [LRZ docs](https://doku.lrz.de/ai-systems-11484278.html) |
| Chinese platforms (ModelScope free GPU, Baidu AI Studio, Alibaba Tianchi) | Not verified | Not verified. A tutorial of unknown date mentions 36 free GPU hours after linking an Alibaba Cloud account | Usually a mainland phone number and real name verification, not verified | Not assessed | A lead only |

How to pick: Kaggle first. If it cannot be opened or the phone is not verified, use Colab. If neither gives a GPU or both keep dropping, spend about 5 dollars on Hugging Face Jobs or RunPod and finish in one go.

## 3. What to find out before a run

Principle: only facts you can see yourself after logging in. Do not pass on passwords, verification codes, tokens, API keys, phone numbers or card details. Blur emails and avatars in screenshots. Creating accounts, phone verification, payment and authorization are done by the account owner.

### 3.1 General

| Question | Why it matters |
|---|---|
| Can the current network open colab.research.google.com, kaggle.com and huggingface.co? | Decides which one to try first |
| Where was `kata1-tf3-b11c768-s12752M-d6531M.bin.gz` (262 MB) downloaded from? | Needed to confirm its license, see `docs/LICENSE-ADVICE.md` section 5 |
| How big is `n_json.zip` in MB? | Decides where to upload it |
| A budget limit (one number such as "5 dollars") and whether adding a payment method is acceptable | Decides whether the paid fallback is on the table |
| A short trial while present, or submit and walk away? | Decides between Colab and Kaggle |

### 3.2 Kaggle (first choice)

1. Sign in at kaggle.com with your own account.
2. Open the profile menu, then Settings, and find the phone verification entry. Note only "verified" or "not verified", never the number. Complete it yourself if needed.
3. Create a new notebook. In Session options check whether Accelerator offers a GPU (T4 or P100) and whether the Internet switch can be turned on.
4. In the notebook run these two lines and keep the output:
   ```
   !nvidia-smi
   !df -h /kaggle/working | tail -1
   ```
5. Find the GPU quota display (used and total hours, reset day) in the account settings or the session menu and note the numbers.
6. Create two private datasets, one with the weights file and one with `n_json.zip`, and note that they are uploaded and how big they are.

What these answers decide: which KataGo build to use (a T4 and a P100 differ in CUDA capability), the `--batch` and thread values, how many groups fit in one session, and whether several "Save & Run All" rounds are needed.

### 3.3 Colab

1. Open colab.research.google.com with your own Google account and upload `remote/katago_batch.ipynb`.
2. Runtime, Change runtime type, choose T4 GPU. If it cannot be chosen or it says no GPU is available or the usage limit was reached, note the message word for word.
3. In a new code cell run these and keep the output:
   ```
   !nvidia-smi
   !df -h /content | tail -1
   !free -h | head -2
   ```
4. To protect progress against disconnects with Drive: note the free space (bottom left of drive.google.com) and the folder name you will use, for example `MyDrive/josekiapp/`. The authorization dialog is yours to accept.
5. With Pro or pay as you go: note the compute unit balance.
6. While it runs keep the page open and stay nearby. After a disconnect reconnect and rerun all cells, finished groups are skipped.

### 3.4 Paid fallbacks

| Platform | What the account owner does | What to note down (non sensitive) |
|---|---|---|
| Hugging Face Jobs | Sign up, top up a small amount (for example 5 dollars) in Billing, log in with `hf auth login` on your own computer. Keep the token private | The balance and the flavor chosen (for example `t4-small`) |
| RunPod | Sign up and top up, start a Pod from a PyTorch or CUDA template, open the web terminal or SSH command | The GPU model and hourly price, and the `nvidia-smi` output |
| Vast.ai | The same, prefer data centre or well rated hosts | The same, plus on demand or interruptible |
| Modal | Sign up and log in from your own terminal through the browser | The remaining free credit and whether a card was needed |
| Lightning AI | Sign up and finish phone verification | The credit balance, whether a Studio can use a GPU and open a terminal |

### 3.5 GitHub Student Developer Pack (optional)

On education.github.com/pack note whether student verification went through, and copy the names and amounts of any cloud or GPU benefits shown.

### 3.6 LRZ (only if you apply)

Note whether you have an LRZ account, whether you were added to a project with AI Systems enabled (yes or no), the output of `sinfo` on the login node (partition names), the output of `nvidia-smi` on a compute node, and whether a compute node can reach the internet (does `curl -I https://github.com` work). Do not share SSH private keys, passwords or VPN credentials.

## 4. Terms and risks per platform

- Colab: see the FAQ. KataGo analysis is neither training nor a distributed worker, and running a batch in a notebook then downloading the result counts as interactive computing, but that is a reading of the FAQ and not a guarantee from Google. Do not open tunnels, use `colab_ssh`, keep-alive scripts or extra accounts to get around limits. When it says the usage limit has been reached, stop.
- Kaggle: the official docs pages are rendered by the browser and the text with quota and session length could not be read, so the numbers above come from third party roundups. Trust what your own account shows. No multiple accounts, no tunnels.
- Hugging Face Jobs: always set a timeout (the default 30 minutes stops the job). Write output to a mounted bucket or a Hub repo, because the container's files are gone afterwards. Library compatibility of KataGo inside the image has not been tested.
- RunPod and Vast.ai: stop and delete the instance when done, because disks keep billing. Never sign in to personal accounts or leave private keys on a rented machine.
- Everywhere: upload only board coordinates (`n.json`) and the weights. Do not upload videos or transcripts (copyright, see `docs/LICENSE-ADVICE.md`). Clear credentials and temporary files after downloading the results.
- Weights: the KataGo license for official networks is permissive, but networks from other contributors may have no clear terms ([network license](https://katagotraining.org/network_license/)). Confirm which kind your file is before putting it anywhere public. Private datasets and repos are not affected.

## 5. LRZ and BayernKI: when the application may not go through

### 5.1 Routes and eligibility (from the official docs)

- LRZ AI Systems needs a valid LRZ account that belongs to an LRZ project with AI Systems enabled. The page asks applicants to show a clear research focus. It does not mention students, and it is written for project leaders (PIs) and project managers (Master Users), with ordinary users joining through the Master User ([LRZ access page](https://doku.lrz.de/1-access-10746642.html)). `remote/README.md` already says that TUM and LMU student accounts by default cover mail and storage but not the high performance systems.
- Fastest route: ask your course, practical or thesis supervisor. Their project's Master User can add you to the group `<project id>-ai-c`. Or ask them to enable AI Systems for an existing project through the service desk form "AI Systems Project Activation/Update". Old projects with many members often do not qualify.
- A new project: the PI fills in the LRZ project application form, writes "AI Systems" in the remarks, and sends a follow-up request to enable AI access once the project exists.
- BayernKI: for researchers at state universities and universities of applied sciences in Bavaria, applied for through NHR@FAU, with LRZ or NHR@FAU as the preferred centre. One application per research group, and the PI and contact person have to log in to the NHR@FAU HPC portal first (taken from a search summary, because the application page itself returned 404 here, so the latest rules are not verified). Resources: about 120 H100 at LRZ and about 200 H100 at FAU according to the same source ([NHR@FAU BayernKI](https://hpc.fau.de/application-for-bayernki-access)).
- Review time: the LRZ page only says suitability is assessed from what you provide and gives no time. Projects expire after a year and have to be renewed.
- Network: logging in to `login.ai.lrz.de` works from inside the Munich Scientific Network (MWN) or through VPN. Membership of the `-ai-c` group includes VPN access.
- Status: AI Systems is in pilot operation, and the docs list a planned maintenance window from 2026-11-23 to 2026-11-25.

### 5.2 If it is refused or slow

1. Kaggle or Colab (free), or Hugging Face Jobs, RunPod, Vast.ai (a few dollars), see section 2.
2. Ask your chair or research group whether it has its own GPU server or cluster accounts (what TUM offers internally was not verified).
3. NHR@FAU Alex: search results suggest FAU members have their own Tier 3 route and that test projects are open or closed to university members depending on the source (not verified). You are not an FAU member, so look at the BayernKI and NHR rules.
4. A line for your supervisor: "I am running a small project that analyses Go joseki with KataGo, about 1 to 4 GPU hours of batch work on a single card. Could you add me to your LRZ project with AI Systems enabled? I will only use Slurm batch jobs and follow the usage rules."

### 5.3 When you do get an account

- Do not run computation on the login node. Use it to copy files, set up the environment and submit jobs, and run KataGo and transcription with `sbatch`, `srun` or `salloc` on compute nodes. This is the usual HPC rule. The LRZ usage policy page could not be read, so its exact wording is not verified, follow their "Usage Policies".
- Partitions and time: every partition except `lrz-cpu` needs `--gres=gpu:1`. The default time is 1 hour and the maximum is 2 days (`--time=2-00:00:00`). The default partition is `lrz-v100x2` (2 x V100 16 GB). A100 and H100 partition names carry the memory and GPU count, for example `lrz-hgx-h100-94x4`. Partitions starting with `MCML` are for partners only and those with `test` are internal. Names may change, so trust `sinfo` on the login node ([LRZ resources page](https://doku.lrz.de/1-general-description-and-resources-10746641.html), [compute page summary](https://doku.lrz.de/2-compute-10746641.html)).
- This job needs one card. Ask for one GPU and a short time (try `--time=00:20:00` first). It queues much faster and is more polite. The 29 groups can be split into a `--array` of small jobs, and `analyze_remote.py` resumes, skipping groups that are already done.
- Containers: Enroot with pyxis (`srun --container-image=...`), images can be imported from NGC. KataGo needs matching CUDA and cuDNN (transformer networks need cuDNN 9.8 or newer, see the troubleshooting in `remote/README.md`). Never put credentials into an image or job script.
- Internet from compute nodes was not found in the docs (not verified). Plan for no internet: download KataGo and the weights on the login node first and let the job read local files only. `slurm_analyze.sbatch` is written like this, but it has not been tested on the real system.
- Data policy: shared storage (DSS) is tight, so keep only what you need and delete the rest. Do not put copyrighted material there. Videos and transcripts stay on your machine and only `n.json` (board coordinates) and the weights go up. Describe the purpose honestly as a small research or course project on Go joseki analysis.
- Credentials: log in with an SSH key and keep the private key out of the repo, cloud drives and chats. Do not share the account. Keep tokens in environment variables or a password manager.
- Quota and queue: use fair amounts. Do not fill the queue with one huge array. If a job fails, read the log before resubmitting and never resubmit the same failing job in a loop.
- Compliance: follow the LRZ terms and the export control declaration that `remote/README.md` mentions. Projects expire after a year. Student accounts can lapse when your status changes, so copy results out in time.
- Acknowledgement: BayernKI and LRZ resources usually ask for a credit in results. The wording is not verified, check the welcome mail.

## 6. A minimal plan

1. Settle the answers in sections 3.1 and 3.2 (or 3.3).
2. Run the trial cell of `remote/katago_batch.ipynb` on Kaggle or Colab and note the speed.
3. Decide from the speed: run everything at once, run in a few rounds, or use a paid fallback.
4. Download `g_*.a2.json` to the local machine, follow the existing steps (`regen.py`, then `tools/build.ps1`), and commit on a `data/<batch>` branch as described in `docs/WORKFLOW.md`.

## Not verified

- Kaggle's current weekly quota, the session length (9 or 12 hours) and the current phone verification rules for GPU and internet.
- Colab pay as you go GPU unit rates (only third party measurements).
- The latest Lightning AI free credit rules.
- Live Vast.ai prices. The secure and community columns in the RunPod price table are inferred.
- Whether Modal requires a payment method, and the academic credit amount.
- AWS free plan limits on GPU instances (second hand).
- LRZ: internet from compute nodes, the usage policy text, review time. BayernKI's latest application details. Other GPU resources inside TUM.
- Free quotas and real name rules of Chinese platforms.
- All speeds and costs: they are extrapolated from the local numbers in `remote/README.md`, and no cloud GPU was measured.

## Sources (visited 2026-11-01)

- Colab FAQ: https://research.google.com/colaboratory/faq.html. Third party price roundup: https://gpuperhour.com/blog/google-colab-alternatives
- Kaggle: https://www.kaggle.com/docs/notebooks (rendered in the browser, the body text could not be read). Third party roundup: https://gpuperhour.com/blog/free-cloud-gpus-and-credits
- Hugging Face Jobs: https://huggingface.co/docs/huggingface_hub/guides/jobs. Spaces GPUs: https://huggingface.co/docs/hub/spaces-gpus
- RunPod: https://www.runpod.io/pricing. Vast.ai: https://vast.ai/pricing. Modal: https://modal.com/pricing. Lightning AI: https://lightning.ai/pricing
- Paperspace: https://docs.digitalocean.com/products/paperspace/pricing
- Google Cloud free trial and GPU quota (community report): https://discuss.google.dev/t/300-free-trial-is-useless-without-gpu-quota-my-trial-period-is-wasting-away/290091. AWS free plan: https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/. Azure student GPU quota: https://learn.microsoft.com/en-us/answers/questions/2157302/clarification-on-gpu-access-after-upgrading-azure
- GitHub Student Developer Pack: https://education.github.com/pack. Eligibility: https://docs.github.com/en/education/about-github-education/github-education-for-students/about-github-education-for-students
- LRZ AI Systems: https://doku.lrz.de/ai-systems-11484278.html, access https://doku.lrz.de/1-access-10746642.html, resources and partitions https://doku.lrz.de/1-general-description-and-resources-10746641.html, compute https://doku.lrz.de/2-compute-10746641.html
- BayernKI and NHR@FAU: https://hpc.fau.de/application-for-bayernki-access and https://doc.nhr.fau.de/bayernki-application/
- KataGo network license: https://katagotraining.org/network_license/. The KataGo release notes (transformer, CUDA) are in the source list of `remote/README.md`
- Community speed data point (old, different network): https://www.lifein19x19.com/viewtopic.php?p=278149
