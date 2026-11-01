# Remote GPU / compute switch (UI v4)

> Researched on 2026-11-01. Numbers follow the source pages (sources at the end); "unverified" means it has not been run on real hardware. The viewer UI itself is in Chinese; UI labels are given here in English translation.

## 1. Conclusions

- **The bottleneck really is the graphics card, and it is the slowest possible combination**: the local machine uses the OpenCL backend with a Transformer network (b11c768). The KataGo v1.18.0 release notes state that OpenCL is "much slower, particularly for transformer models", while the NVIDIA CUDA build is 1.2~2x faster on Transformers, and v1.18.2 adds tensor-core attention for T4 / RTX 20 series (Turing). Any NVIDIA discrete GPU will make a clear difference.
- **Recommended: offline batch, not "web page talking to the cloud in real time".** What you need is to "generate AI data once for ~29 groups", not low-latency play. A batch job needs one machine for a few hours and produces `g_<name>.a2.json`; the web page does not need the network at all. This is also the most compliant option (see section 5), because the free platforms specifically forbid "using Colab/Kaggle as a server".
- Real-time analysis is built into the page as an **option** (off by default): it only connects to a KataGo that you control (this machine, or LRZ / a machine you rent). If the connection fails, it falls back to the cached AI data automatically.

| Option | Speed (estimate, not measured) | Cost | Main risks | Compliant? |
|---|---|---|---|---|
| Status quo: local 780M integrated GPU, OpenCL | Baseline: 220 visits ≈ 11 s, 30~40 min per group, about 15~19 hours in total | 0 | Ties up the local machine and slows other work | Yes |
| **Colab free tier, batch** (`katago_batch.ipynb`) | T4 + CUDA: I estimate 5~15x, 2~4 hours in total | 0 | No GPU guaranteed; sessions last at most 12 hours; the page must stay open; quota is not published | **Yes** (batch jobs inside the notebook only, no tunnels) |
| **Kaggle Notebooks, batch** | T4/P100 (official docs: about 30 GPU hours per week); can run in the background with "Save & Run All" | 0 | Phone verification needed; Internet must be on; speed on P100 (no tensor cores) unknown | Yes (batch); tunnel-style use has been reported to get banned |
| **LRZ AI Systems + Slurm, batch** | V100/A100/H100: estimate 10~50x | Docs do not mention fees | Needs an LRZ project account (a student account is not enough); compute nodes often have no internet | Yes (intended use) |
| Lightning AI free Studio | Depends on the GPU; one Studio, restart every 4 hours | Free credits (amounts differ between sources; prices were apparently changed in 2026-09) | The credit rules keep changing; not verified whether ports can be exposed | Not verified |
| Hugging Face Spaces | T4 small is officially 0.40 USD/hour; ZeroGPU supports Gradio only, 5 free minutes per day | Paid | Not suited to long KataGo jobs | Yes (paid) |
| Browser WebGPU KataGo (web-katrain / Kaya) | May use the integrated GPU (via D3D12); speed not measured | 0 | Uploaded models are limited to 128MB and our weights are 262MB; a different network => results not comparable with the existing data | Yes |
| **Colab/Kaggle + ngrok/cloudflared tunnel for real-time web page use** | - | - | Account ban / runtime termination | **Violates the terms; not provided in this directory** |

The speed column is my estimate from "20 visits/s locally" and community data (one old post gives about 390 network evaluations per second on a T4, but that was a small network and an old version). **After the first group finishes, calibrate with the `seconds` field in `meta.json`.**

## 2. Why it is designed this way

1. **Batch first**: one run produces a whole group's `a2.json`, in the same format as the existing pipeline, auditable and re-runnable (finished groups are skipped automatically).
2. **Port the logic, do not rewrite it**: `analyze_remote.py` is a line-by-line port of `analyze2.py` (region, branch points, forced evaluation of the teacher's moves, `reportAnalysisWinratesAs=BLACK` → side-to-move perspective). `selftest.py --ref analyze2.py` runs both on the same fake engine and the outputs are **byte-for-byte identical**.
3. **The perspective error must not happen again**: the bridge forces `reportAnalysisWinratesAs=BLACK` and declares `bridge.winratesAs` in every response; the page converts to the side-to-move perspective only when it sees BLACK, and refuses to use the response otherwise. The page still only shows "how many points worse than the local best", never the whole-board winrate.
4. **No change to existing behaviour by default**: the compute control defaults to "cache" and sends no network request at all; connections are made only after switching to local/remote; on failure / disconnect / perspective mismatch the page keeps showing the cached data.
5. **Keep the bridge small**: it only forwards analysis queries with allowlisted fields, has a token, a CORS allowlist, and limits on visits / number of moves / concurrency, and listens on 127.0.0.1 only by default.

## 3. Usage A: offline batch (recommended)

**Preparation (local machine, read-only)**: pack the `g_*.n.json` files to analyze (the originals are not modified; you can also pack the finished ones while the pipeline is still running):

```powershell
Compress-Archive -Path D:\tmp\work\g_*.n.json -DestinationPath $env:USERPROFILE\Desktop\n_json.zip
```

The weights `kata1-tf3-b11c768-s12752M-d6531M.bin.gz` (262MB) are the same file the local machine uses; upload it once to Google Drive / a Kaggle Dataset. **Do not switch networks**, otherwise old and new results are not comparable.

**Colab free tier**
1. Open [colab.research.google.com](https://colab.research.google.com) and upload `remote/katago_batch.ipynb`; *Runtime → Change runtime type → T4 GPU*.
2. To avoid losing progress on a disconnect: in the 4th code cell set `USE_DRIVE = True` and authorize Drive (you approve it yourself).
3. Run from top to bottom; upload the input zip and the weights when prompted (or put them in `MyDrive/josekiapp/`). First run the "trial run on 3 branch points" to check the speed.
4. **Keep the page open and stay nearby.** After a disconnect, reconnect and re-run all cells; finished groups are skipped automatically.
5. The last cell downloads `a2_results.zip`. Unpack it, put the `g_*.a2.json` files back into `D:\tmp\work`, and continue with the usual flow (`regen.py` → `tools\build.ps1`). I did not read `orch2.py`, so please check against your existing flow whether its checkpoint logic picks the files up directly.

**Kaggle**: create a new Notebook, choose a GPU as Accelerator in the right-hand panel, and turn Internet on (phone verification required); make the n.json files and the weights into Datasets and add them; import the same `.ipynb`; *Save & Run All* runs unattended in the background and the results can be downloaded from Output.

**Slurm (LRZ etc.)**: see the comment at the top of `slurm_analyze.sbatch`. In short: download everything on the login node with `setup_katago.py` first, and let the job read local files only; replace the partition name / container image with your cluster's. **A template, not verified on real hardware.**

**How to get LRZ access** (official docs): you need an LRZ account **and** membership in a project with AI Systems enabled; TUM/LMU student accounts by default only get services such as mail and cloud storage, not the high-performance systems. Ways in: ask your course / Praktikum / thesis supervisor, whose LRZ project administrator (Master User) can add you; or apply through BayernKI. Submit a service request "AI topics → LRZ AI Systems - Request for Access" and state the purpose. Logging in to `login.ai.lrz.de` requires being inside the Munich Scientific Network or using the VPN.

**Parameters**: `--visits 220 --forced 100` match the local baseline; on a strong GPU you can add `--threads 3` for more speed, but do not change visits (otherwise results are not comparable with the old data). GPU/FP16 numbers are not bit-identical to the integrated GPU's; that is normal fluctuation.

## 4. Usage B: the "compute" switch in the page (optional, real-time analysis)

A small line at the bottom of the left sidebar, "● Compute · Cache". Click it to expand:

| Item | Description |
|---|---|
| Cache (default) | No network; uses the already-generated AI data as before |
| Local engine | Connects to `katago_bridge.py` on your own computer (default `http://127.0.0.1:8787`) |
| Remote GPU | Connects to another machine you control (enter its address) |
| token | Printed when the bridge starts (or set it yourself). Stored only in this browser's localStorage (in plain text, readable by scripts of the same origin; do not store it on a shared computer) |
| Test connection | Shows latency, KataGo version and model name; simulated data is clearly labeled |
| Analyze current position | Runs a 220-visit search at the current node and a forced 100-visit evaluation of each of the teacher's moves (same as the offline flow) |
| Click an empty point on the board | Tries that move (color = side to move) and analyzes the opponent's replies in the new position; the left/right keys step back |
| Auto-analyze when uncached | Automatically analyzes a node that has no cached AI data when you reach it (off by default) |

Live results are presented the same way as cached ones: translucent stone color = side to move, ring color/number = how many points worse than the local best, blue dashed ring = the teacher's move, hover to see the variation; the caption bar says "live analysis (local/remote) · visits · seconds". Only the "teaching region" is searched (computed from the game record with the same percentile rule as `analyze2.region`).

**Starting the bridge (local machine, Windows example)**: do not start the real engine while the pipeline `orch2.py` is using the GPU.

```powershell
$env:KATAGO_BRIDGE_TOKEN = "make up a random string of 20+ characters"   # if unset, one is generated and printed once
python remote\katago_bridge.py --katago D:\workspace\fun\Weiqi\Weiqi_AI\engine\katago-v1.18.0-opencl-windows-x64\katago.exe `
       --model D:\workspace\fun\Weiqi\Weiqi_AI\weights\network_file\kata1-tf3-b11c768-s12752M-d6531M.bin.gz
# To try the UI without touching the GPU:  python remote\katago_bridge.py --fake      (returns fake data labeled as simulated)
```

A page opened from `http://localhost:8765` is allowed by default; a `file://` page opened by double-clicking needs `--allow-file-origin`; other origins need `--allow-origin`.

**Compliant ways to use a remote GPU**: (1) start the bridge on an LRZ / university / self-rented VM and forward the port to your machine with `ssh -L 8787:127.0.0.1:8787 <machine>`, so the page still uses `http://127.0.0.1:8787`; (2) or put a reverse proxy with TLS in front, or give the bridge `--cert/--key`. **Do not** listen on `0.0.0.0` without TLS (the token would be sent in clear text; the bridge warns about it). I have not verified LRZ's port-forwarding procedure; read the LRZ Jupyter/tunnel FAQ first and check the policy.

## 5. Terms-of-service risks (read this honestly)

Sources are listed at the end; the current wording of the official pages is what counts.

- **Colab free tier**: the FAQ lists "connecting to remote proxies" and "file hosting / media serving / other web services unrelated to interactive computing" as prohibited on all hosted runtimes, and "remote control such as SSH, remote desktop" as prohibited on free (or zero-compute-unit) runtimes; offending runtimes may be terminated without warning. It also lists "chess training" and "distributed computing workers". Therefore:
  - Running KataGo batch analysis directly in the notebook and downloading the results is interactive computing and **allowed**, but you must be present with the page open. KataGo analysis is neither training nor a distributed worker, but that is my reading, not a guarantee from Google.
  - Opening an ngrok/cloudflared tunnel, `colab_ssh`, letting the web page connect from outside to a bridge inside Colab in real time, or using keep-alive scripts: these **violate** the terms or circumvent the limits. **Do not do it; this directory does not provide it.** SSH restrictions differ for paid users with positive compute units, but the "remote proxy / web service" rule still applies to every hosted runtime, so exposing the bridge is not recommended even with Pro.
  - The quota is not published and a GPU is not guaranteed; when it says the usage limit has been reached, stop. Do not switch accounts or work around it.
- **Kaggle**: the official docs give a weekly GPU quota (about 30 hours, "or sometimes higher") and a 60-minute idle timeout; GPU and Internet need phone verification. An open-source project reports that Kaggle blocked SSH tunnels into running kernels and warned that this may violate the terms. I found no text in Kaggle's terms that explicitly allows "serving to the outside", so only batch mode is used.
- **LRZ**: accounts are tied to projects, the purpose must be stated, and the export-control statement must be observed; student accounts need a project. The compliant use is batch jobs.
- **Lightning AI**: the free-credit rules have changed recently (see the sources); its Studios support SSH, but I did not verify the port-exposure terms, so it is neither recommended nor given a script for now.
- **Data**: the only thing uploaded to the cloud is the Go positions set up in the videos (coordinates); no account or personal information.

## 6. Files

| File | Purpose |
|---|---|
| `analyze_remote.py` | Port of `analyze2.py` + resume + loop over several groups; outputs `g_<name>.a2.json` + `.a2.meta.json` |
| `setup_katago.py` | Downloads the Linux GPU build of KataGo (default v1.18.2 + cuda12.1-cudnn9.8.0), checks with `ldd`, and pip-installs missing CUDA libraries into a separate directory |
| `katago_batch.ipynb` / `make_notebook.py` | Notebook for both Colab and Kaggle (embeds the two scripts above); after changing a script, regenerate with `python make_notebook.py` |
| `slurm_analyze.sbatch` | Slurm batch template (not verified on real hardware) |
| `katago_bridge.py` | Optional: KataGo analysis → HTTP (token + CORS + validation); `--fake` lets you try the UI without a GPU |
| `selftest.py` | GPU-free self-test (fake engine): perspective conversion, region, forced evaluation, resume, comparison with `analyze2.py`, bridge validation/auth/CORS |

## 7. Troubleshooting

- **`nvidia-smi` prints nothing**: the GPU runtime is not selected (Colab: Runtime → Change runtime type; Kaggle: Accelerator).
- **Colab says it cannot connect to a GPU / the usage limit has been reached**: the free quota is used up; wait a while and retry, or switch to Kaggle / LRZ.
- **`setup_katago.py` reports missing `libcudnn.so.9` / `libcublas.so.12` etc.**: the script pip-installs them into `katago_env/nvlibs` and sets `LD_LIBRARY_PATH`; if it still fails, change `KATAGO_BUILD` to `cuda12.5-cudnn9.8.0` or `cuda12.8-cudnn9.8.0` and retry; failing that, use the OpenCL Linux build of v1.18.1 (slow, but the most universal). Transformer networks need cuDNN >= 9.8; the 8.9.7 builds are "a LOT slower".
- **Missing `libzip.so.x`**: with root, `apt-get install libzip4` (on Ubuntu 24.04 it is `libzip4t64`); on a cluster, ask the admin to load the module.
- **KataGo exits right after starting**: look at `katago_stderr.log` in the output directory; the usual causes are insufficient GPU memory (change `--batch 64` to `32`) or a wrong model path.
- **`ModuleNotFoundError` / n.json not found**: input files must be named `g_*.n.json`.
- **The page says it cannot connect**: the bridge is not running / wrong address or port / the page origin is not in the allowlist (`--allow-origin`, `--allow-file-origin`) / an `https` page connecting to an `http` address (the browser blocks it). The page falls back to the cached data automatically.
- **The page says winratesAs=BLACK was not declared**: you connected to something that is not this directory's bridge, or the versions do not match; the page refuses to use it to avoid perspective errors.
- **Scores look systematically positive/negative**: first look at "color = side to move" in the caption bar; both offline and live data use the side-to-move perspective, not Black's.

## 8. What was verified / what was not

Verified: `selftest.py` passes completely (fake engine; byte-for-byte identical with `analyze2.py`; the bridge's validation / auth / CORS / HTTP handling runs correctly on in-memory streams); the page's default behaviour is unchanged with no console errors; the page's connection test, analysis, trial moves, failure fallback, and perspective-declaration check run correctly against an **in-page fetch stub (a simulated bridge)**, with candidate-point colors / signs / forced evaluations as expected; an unreachable real address → a message and fallback to the cache after about 3 seconds.

**Not verified**: a real KataGo, a real GPU, actual runs on Colab/Kaggle/LRZ (no accounts, and as requested KataGo was not run); library compatibility of `setup_katago.py` on the cloud images; the speed-up factors (all estimates); the bridge's real sockets and SSH port forwarding; the Slurm template; the browser WebGPU option was not tried.

## Sources (accessed 2026-11-01)

- Colab FAQ (prohibited uses, 12 hours, GPU models may change): <https://research.google.com/colaboratory/faq.html>
- KataGo v1.18.2 / v1.18.0 / v1.17.0 release notes: <https://github.com/lightvector/KataGo/releases/tag/v1.18.2> · <https://github.com/lightvector/KataGo/releases/tag/v1.18.0> · <https://github.com/lightvector/KataGo/releases/tag/v1.17.0>
- Free GPU roundup (third party, 2026-09-21): <https://gpuperhour.com/blog/free-cloud-gpus-and-credits>
- Kaggle docs: <https://www.kaggle.com/docs/efficient-gpu-usage> · <https://www.kaggle.com/docs/notebooks> · phone verification discussion <https://www.kaggle.com/product-feedback/255038> · report of blocked tunnels (community) <https://github.com/lamhoangtung/remokaggle>
- Lightning AI: <https://lightning.ai/pricing> · price-change report (third party) <https://www.usagepricing.com/blueprint/activity/lightning-ai-2026-09-21-gpu-rate-card-reprice>
- Hugging Face Spaces GPU: <https://huggingface.co/docs/hub/main/spaces-gpus>
- LRZ AI Systems: <https://doku.lrz.de/ai-systems-11484278.html> · access request <https://doku.lrz.de/1-access-10746642.html> · login <https://doku.lrz.de/1-1-ai-systems-login-2498299908.html> · Jupyter/tunnel FAQ <https://doku.lrz.de/faq-jupyter-on-hpc-systems-10746056.html>
- NHR@FAU / BayernKI: <https://hpc.fau.de/application-for-bayernki-access-at-nhrfau>
- In-browser KataGo: web-katrain <https://github.com/Sir-Teo/web-katrain> (TF.js WebGPU, MIT, upload limit 128MB) · Kaya <https://github.com/kaya-go/kaya> (ONNX)
- Community data for KataGo on a T4 (old): <https://lifein19x19.com/viewtopic.php?p=263794>
