#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generates katago_batch.ipynb (for both Colab and Kaggle).

The notebook embeds the current text of the scripts it runs, so the one .ipynb plus the n.json zip and the weights is all
that has to be uploaded:
    pipeline/treesync.py, pipeline/wqutil.py, pipeline/analyze2.py   the analysis itself, the same files the local pipeline uses
    remote/analyze_remote.py, remote/setup_katago.py                 batch loop and KataGo installer
After changing any of them, run   python make_notebook.py   again (tests/test_remote_batch.py fails when the notebook is out of date).
Usage: python make_notebook.py [output.ipynb]
"""
import json
import os
import sys

H = os.path.dirname(os.path.abspath(__file__))
PIPELINE = os.path.join(os.path.dirname(H), 'pipeline')

# The weights file the local pipeline uses (size and sha256 measured on the local copy, 2026-11-08).
WEIGHTS_NAME = 'kata1-tf3-b11c768-s12752M-d6531M.bin.gz'
WEIGHTS_BYTES = 262040299
WEIGHTS_SHA256 = 'c470f51078d31051961dfc372aaa3948a3eec0b93ed52075d16f55a2e17b8cec'

# (folder, file) of every script that is written into the notebook's working directory; the order matters only for reading
EMBEDDED = [(PIPELINE, 'treesync.py'), (PIPELINE, 'wqutil.py'), (PIPELINE, 'analyze2.py'), (H, 'analyze_remote.py'), (H, 'setup_katago.py')]


def rd(folder, name):
    with open(os.path.join(folder, name), encoding='utf-8') as f:   # text mode: CRLF checkouts and LF checkouts give the same text
        return f.read()


def md(s):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': s.strip('\n').splitlines(True)}


def code(s):
    return {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': s.strip('\n').splitlines(True)}


INTRO = r"""
# 定式库 · 云端 GPU 批量 AI 局部评估（KataGo） / Joseki library · cloud GPU batch AI local evaluation (KataGo)

这个笔记本把流水线里最慢的一步（`analyze2.py`，核显上每组约 15 到 30 分钟）搬到带独立显卡的机器上批量运行。分析代码就是本机流水线用的 `pipeline/analyze2.py` 本身（连同 `treesync.py`、`wqutil.py` 一起写进下面的单元格），所以输出的 `g_<名称>.a2.json` 与本机生成的是同一种文件：行棋方视角、带树指纹的 `_meta`、可以断点续跑，`wq.py check` 直接通过，不需要 `wq.py stamp`。

This notebook moves the slowest step of the local pipeline (`analyze2.py`, about 15 to 30 minutes per group on the integrated GPU) onto a machine with a discrete GPU and runs it as a batch. The analysis code is the local pipeline's own `pipeline/analyze2.py` (written into the cells below together with `treesync.py` and `wqutil.py`), so the `g_<name>.a2.json` files are the same kind of file the local run writes: side-to-move perspective, a `_meta` block with the tree fingerprint, resumable, accepted by `wq.py check` as they are, no `wq.py stamp` needed.

**使用步骤 / Steps**

1. 选 GPU 运行时（Colab：*运行时 → 更改运行时类型 → T4 GPU*；Kaggle：右侧 *Session options → Accelerator → GPU*，并把 *Internet* 打开）。
   Select a GPU runtime (Colab: *Runtime → Change runtime type → T4 GPU*; Kaggle: right panel *Session options → Accelerator → GPU*, and switch *Internet* on).
2. 先把两样东西放好：`n_json_<日期>.zip`（变化树）和权重文件 `kata1-tf3-b11c768-s12752M-d6531M.bin.gz`（约 262 MB）。Colab 推荐放进 Google Drive 的 `MyDrive/josekiapp/`；Kaggle 做成私有 Dataset 并添加到笔记本。
   Put two things in place first: `n_json_<date>.zip` (the variation trees) and the weights file `kata1-tf3-b11c768-s12752M-d6531M.bin.gz` (about 262 MB). On Colab put them in `MyDrive/josekiapp/` on Google Drive; on Kaggle make them a private Dataset and add it to the notebook.
3. 从上到下依次运行各单元格。断线后重新连接并重新运行全部单元格：已经完成的分组会被跳过，没完成的分组从检查点继续（前提是输出放在 Drive 或 `/kaggle/working`）。
   Run the cells from top to bottom. After a disconnect reconnect and run all cells again: finished groups are skipped and an unfinished group continues from its checkpoint (as long as the output is on Drive or in `/kaggle/working`).
4. 最后一个单元格生成 `a2_results.zip`。下载后按 README_cloud.md 把里面的 `g_*.a2.json` 放进 `D:\tmp\work`，再运行 `wq.py check`。
   The last cell builds `a2_results.zip`. After downloading, put the `g_*.a2.json` files into `D:\tmp\work` as README_cloud.md describes and run `wq.py check`.

**使用条款（必读） / Terms of use (must read)**

Colab 免费版只能当作交互式笔记本使用。这个笔记本只在笔记本进程内部跑批处理：不开端口，不用 SSH、隧道或远程桌面，不提供对外服务。**不要**加保活脚本、ngrok 或 cloudflared 隧道，也不要把 Colab 当作网页实时连接的服务器；Colab 免费版 FAQ 明确禁止这些做法，账号可能被限流或封禁。请保持浏览器页面打开、人在附近；如果提示已达到使用上限，就停下来，改天再来或换平台，不要想办法绕过。

The Colab free tier may only be used as an interactive notebook. This notebook only runs a batch job inside the notebook process: it opens no ports and uses no SSH, tunnels or remote desktop, and serves nothing. **Do not** add a keep-alive script, an ngrok or cloudflared tunnel, and do not use Colab as a server that a web page connects to in real time; the Colab free-tier FAQ prohibits these and the account may be throttled or banned. Keep the browser tab open and stay nearby; if it says the usage limit has been reached, stop and come back another day or switch platform instead of working around it.
"""

SETTINGS_MD = r"""
## 1. 环境与设置 / Environment and settings

第一个单元格打印 GPU、磁盘和网络情况。向助手求助时请把这一段输出原样贴回去（里面没有账号或密码）。

The first cell prints the GPU, disk and network. When you ask for help, paste this output back as it is (it holds no account data or passwords).
"""

ENV_CODE = r"""
import glob, hashlib, json, os, re, shutil, subprocess, sys, time, urllib.request, zipfile

# ---- settings (the defaults are the ones the README describes)
USE_DRIVE = True          # Colab: keep input, progress and results in MyDrive/josekiapp, so a disconnect loses nothing. False: upload by hand (lost on disconnect).
DRIVE_DIR = 'josekiapp'   # folder in My Drive that holds the weights, the n_json zip and (later) the results
WEIGHTS_PATH = ''         # only when the weights are somewhere unusual: the full path of the .bin.gz
KATAGO_BUILD = 'cuda12.1-cudnn9.8.0'   # if libraries are missing try cuda12.5-cudnn9.8.0, then cuda12.8-cudnn9.8.0
WEIGHTS_NAME = '@@WEIGHTS_NAME@@'
EXPECTED_SHA256 = '@@WEIGHTS_SHA256@@'   # the weights the local pipeline uses; '' skips the check, but then old and new analysis are not comparable
EXPECTED_BYTES = @@WEIGHTS_BYTES@@
VISITS, FORCED = 220, 100  # the local baseline: do not change, or old and new results are no longer comparable

ON_KAGGLE = os.path.exists('/kaggle/working')
ON_COLAB = (not ON_KAGGLE) and ('google.colab' in sys.modules or os.path.exists('/content'))
WORK = '/kaggle/working' if ON_KAGGLE else ('/content' if ON_COLAB else os.getcwd())
os.chdir(WORK)   # the scripts of the next cells are written here and run from here
if WORK not in sys.path:
    sys.path.insert(0, WORK)


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


def run_stream(cmd, env=None, every=30):
    '''Run a command and show its output as it comes (same on Colab and Kaggle). Progress lines are thinned out to one per `every` seconds.'''
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', env=env, bufsize=1)
    last = 0.0
    for line in p.stdout:
        if re.match(r'\d\d:\d\d:\d\d phase ', line) and time.time() - last < every and 'queries' in line and not re.search(r'(\d+)/\1 queries', line):
            continue
        if re.match(r'\d\d:\d\d:\d\d phase ', line):
            last = time.time()
        print(line, end='', flush=True)
    return p.wait()


try:
    urllib.request.urlopen('https://github.com', timeout=10)
    INTERNET = 'yes'
except Exception as e:
    INTERNET = 'NO (%s)' % e
GPU = sh('nvidia-smi')
print('=== paste this block back when you ask for help ===')
print('platform :', 'Kaggle' if ON_KAGGLE else 'Colab' if ON_COLAB else 'other', '| python', sys.version.split()[0], '| work dir', WORK)
print('internet to github.com:', INTERNET)
print(GPU or '!! nvidia-smi printed nothing: no GPU runtime')
print(sh('df -h ' + WORK))
print(sh('free -h | head -2'))
print('cpu cores:', os.cpu_count())
print('=== end of block ===')
assert GPU, 'No GPU: select a GPU runtime first (Colab: Runtime > Change runtime type > T4 GPU; Kaggle: Session options > Accelerator).'
if ON_KAGGLE:
    assert INTERNET == 'yes', 'Internet is off: switch it on in the right panel (Session options > Internet). KataGo is downloaded from GitHub.'
"""

SCRIPTS_MD = r"""
下面五个单元格把脚本写进工作目录，内容与仓库里的同名文件一致（由 `remote/make_notebook.py` 生成，不要手工改）。

The next five cells write the scripts into the working directory. Their text is identical to the files of the same name in the repository (generated by `remote/make_notebook.py`, do not edit by hand).
"""

INPUT_MD = r"""
## 2. 输入：变化树和权重 / Input: the trees and the weights

笔记本会在这些位置找 `n_json_*.zip`（或散放的 `g_*.n.json`）和权重文件：工作目录、Colab 的 `MyDrive/josekiapp/`、Kaggle 的 `/kaggle/input/*/`。找不到时，Colab 会弹出上传框。权重文件会用 sha256 核对，必须与本机用的是同一个文件。

The notebook looks for `n_json_*.zip` (or loose `g_*.n.json` files) and the weights in these places: the working directory, `MyDrive/josekiapp/` on Colab, and `/kaggle/input/*/` on Kaggle. If it finds nothing, Colab shows an upload box. The weights are checked by sha256 and must be the very file the local machine uses.
"""

INPUT_CODE = r"""
DRIVE_BASE = ''
if ON_COLAB and USE_DRIVE:
    from google.colab import drive   # a Google sign-in and permission prompt appears; you approve it yourself
    drive.mount('/content/drive')
    DRIVE_BASE = '/content/drive/MyDrive/' + DRIVE_DIR
    os.makedirs(DRIVE_BASE, exist_ok=True)
IN_DIR = os.path.join(WORK, 'in')
OUT_DIR = os.path.join(DRIVE_BASE, 'out') if DRIVE_BASE else os.path.join(WORK, 'out')
for d in (IN_DIR, OUT_DIR, WORK + '/uploads', WORK + '/weights'):
    os.makedirs(d, exist_ok=True)


def search_roots():
    '''(folder, recursive) pairs. /content itself is not searched recursively: Drive is mounted below it.'''
    r = [(WORK, False), (WORK + '/uploads', False)]
    if DRIVE_BASE:
        r.append((DRIVE_BASE, True))
    r += [(d, True) for d in sorted(glob.glob('/kaggle/input/*'))]
    return r


def find_files(pattern):
    hits = []
    for root, rec in search_roots():
        hits += glob.glob(os.path.join(root, '**', pattern) if rec else os.path.join(root, pattern), recursive=rec)
    return sorted(set(hits))


def unpack_zips():
    '''Take the trees and manifest.json out of every zip that has them (several packages are merged, in zip name order), and a
    weights file out of a zip that has one. Basename only: no path tricks.'''
    man, found = {'order': [], 'groups': {}}, 0
    for zp in find_files('*.zip'):
        try:
            z = zipfile.ZipFile(zp)
        except zipfile.BadZipFile:
            continue
        with z:
            for member in z.namelist():
                base = os.path.basename(member)
                if base.endswith('.n.json') and base.startswith('g_'):
                    open(os.path.join(IN_DIR, base), 'wb').write(z.read(member))
                elif base == 'manifest.json' and 'n_json' in os.path.basename(zp):
                    part = json.loads(z.read(member).decode('utf-8-sig'))
                    found += 1
                    man['order'] += [n for n in part.get('order', []) if n not in man['order']]
                    man['groups'].update(part.get('groups', {}))
                elif base.endswith('.bin.gz') and not glob.glob(WORK + '/weights/*.bin.gz'):
                    print('extracting the weights from', zp)
                    with z.open(member) as src, open(os.path.join(WORK, 'weights', base), 'wb') as dst:
                        shutil.copyfileobj(src, dst)
    if found:
        open(os.path.join(IN_DIR, 'manifest.json'), 'w', encoding='utf-8').write(json.dumps(man, ensure_ascii=False))
    if found > 1:
        print('%d packages with a manifest.json were merged (the groups of the first package come first)' % found)


def collect_inputs():
    for f in find_files('g_*.n.json'):
        if os.path.dirname(f) != IN_DIR:
            shutil.copy(f, IN_DIR)
    unpack_zips()
    return sorted(glob.glob(IN_DIR + '/g_*.n.json'))


inp = collect_inputs()
if not inp and ON_COLAB:
    from google.colab import files
    print('Nothing found. Select n_json_<date>.zip (or the g_*.n.json files) to upload:')
    for name, data in files.upload().items():
        open(os.path.join(WORK, 'uploads', name), 'wb').write(data)
    inp = collect_inputs()
man = {}
if os.path.exists(IN_DIR + '/manifest.json'):
    man = json.load(open(IN_DIR + '/manifest.json', encoding='utf-8-sig'))
print('%d input groups (the order in which they will be analysed):' % len(inp))
for n in man.get('order') or [os.path.basename(f)[2:-7] for f in inp]:
    g = (man.get('groups') or {}).get(n, {})
    print('  %-40s nodes %s, branch points %s, main queries %s' % (n, g.get('nodes', '?'), g.get('branch_nodes', '?'), g.get('queries_main', '?')))
assert inp, 'No g_*.n.json found. Put n_json_<date>.zip into MyDrive/%s (Colab) or add it as a Kaggle Dataset, then run this cell again.' % DRIVE_DIR


def sha256_of(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def find_weights():
    cands = [WEIGHTS_PATH] if WEIGHTS_PATH else []
    cands += find_files('*.bin.gz')
    return [c for c in dict.fromkeys(cands) if os.path.isfile(c)]


unpack_zips()
cands = find_weights()
if not cands and ON_COLAB:
    from google.colab import files
    print('Weights not found. Select %s (about 262 MB, the upload is slow):' % WEIGHTS_NAME)
    for name, data in files.upload().items():
        open(os.path.join(WORK, 'uploads', name), 'wb').write(data)
    cands = find_weights()
assert cands, 'No weights file (*.bin.gz) found. Put %s into MyDrive/%s (Colab) or add it as a Kaggle Dataset.' % (WEIGHTS_NAME, DRIVE_DIR)
MODEL = ''
for c in cands:
    got = sha256_of(c)
    ok = (not EXPECTED_SHA256) or got == EXPECTED_SHA256
    print('weights candidate: %s  %d bytes  sha256 %s  %s' % (c, os.path.getsize(c), got, 'MATCHES the local file' if ok else 'is NOT the local file'))
    if ok and not MODEL:
        MODEL = c
assert MODEL, 'None of the weight files has sha256 %s. Upload exactly the file the local pipeline uses (%s, %d bytes).' % (EXPECTED_SHA256, WEIGHTS_NAME, EXPECTED_BYTES)
if MODEL.startswith('/content/drive'):   # read it from local disk: faster and does not depend on the Drive connection
    local = os.path.join(WORK, 'weights', os.path.basename(MODEL))
    if not os.path.exists(local) or os.path.getsize(local) != os.path.getsize(MODEL):
        shutil.copy(MODEL, local)
    MODEL = local
print('using the weights', MODEL)
"""

KATAGO_MD = r"""
## 3. 安装 KataGo（GPU 版） / Install KataGo (GPU build)

脚本会从 GitHub 官方发布页下载 KataGo v1.18.2 的 Linux CUDA 版，并用发布页公布的 sha256 校验；缺少的 CUDA 库用 pip 装到单独的目录（不动系统自带的包）。

The script downloads the official Linux CUDA build of KataGo v1.18.2 from the GitHub release page and checks it against the sha256 published there; missing CUDA libraries are pip-installed into a separate directory (the system packages are not touched).
"""

KATAGO_CODE = r"""
cmd = [sys.executable, '-u', 'setup_katago.py', '--dir', WORK + '/katago_env', '--build', KATAGO_BUILD, '--model', MODEL]
assert run_stream(cmd) == 0, 'setup_katago.py failed: see the messages above (README_cloud.md, troubleshooting)'
ENV = json.load(open(WORK + '/katago_env/env.json'))
assert not ENV['missing_libs'], 'missing shared libraries: %s (try another KATAGO_BUILD in the settings cell)' % ENV['missing_libs']
os.environ['LD_LIBRARY_PATH'] = ENV['ld_library_path']
print('Ready:', ENV['katago'])
print(sh('%s version' % ENV['katago']))
"""

TRIAL_MD = r"""
## 4. （可选，建议）试跑 3 个分叉点，看速度 / (Optional, recommended) Trial run on 3 branch points to see the speed

本机核显每个主搜索（220 visits）约 14 秒，老师着法的强制评估（100 visits）约 4.5 秒（来自本机的进度日志）。试跑同时检查整条链路：KataGo 能启动、视角自检结果是 `BLACK (selftest)`、输出文件通过 `treesync.check_analysis`。第一次会慢一些，因为要加载网络并编译 CUDA 内核。

Locally one main search (220 visits) takes about 14 seconds and a forced evaluation of a teacher move (100 visits) about 4.5 seconds (from the local progress logs). The trial also checks the whole chain: KataGo starts, the perspective self test says `BLACK (selftest)`, and the output passes `treesync.check_analysis`. The first run is slower because the network is loaded and CUDA kernels are compiled.
"""

TRIAL_CODE = r"""
t0 = time.time()
rc = run_stream([sys.executable, '-u', 'analyze_remote.py', '--in', min(inp, key=os.path.getsize), '--out', WORK + '/trial', '--katago', ENV['katago'], '--model', MODEL,
                 '--expect-sha256', EXPECTED_SHA256, '--limit', '3', '--force'])
print('trial exit code %d, %.0f seconds (the first run includes loading the network and compiling kernels)' % (rc, time.time() - t0))
"""

RUN_MD = r"""
## 5. 完整批量运行（可随时中断，重新运行会续跑） / Full batch run (can be interrupted at any time, re-running resumes)

按 zip 里 manifest 给出的顺序逐组分析（从本机最后才会处理的分组开始）。每组结束后打印用时和每个查询的秒数；也可以随时打开输出目录里的 `g_<名称>.a2.meta.json` 看真实速度。

The groups are analysed in the order of the manifest in the zip (starting with the groups the local run reaches last). After each group the time and the seconds per query are printed; you can also open `g_<name>.a2.meta.json` in the output folder at any time to read the real speed.
"""

RUN_CODE = r"""
rc = run_stream([sys.executable, '-u', 'analyze_remote.py', '--in', IN_DIR, '--out', OUT_DIR, '--katago', ENV['katago'], '--model', MODEL,
                 '--expect-sha256', EXPECTED_SHA256, '--visits', str(VISITS), '--forced', str(FORCED)])
print('exit code', rc, '(0 = every group fine; 4 = the engine stopped, run this cell again to continue)')
"""

PACK_MD = r"""
## 6. 打包结果 / Package the results

只有通过 `treesync.check_analysis`（树指纹、行棋方视角、完整标记）的 `a2.json` 才会被打进 `a2_results.zip`。Colab 会自动下载；Kaggle 在右侧 *Output* 里下载；使用 Drive 时 zip 也会复制到 `MyDrive/josekiapp/`。

Only `a2.json` files that pass `treesync.check_analysis` (tree fingerprint, side-to-move perspective, complete flag) go into `a2_results.zip`. Colab downloads it automatically; on Kaggle download it from the *Output* panel on the right; with Drive the zip is also copied to `MyDrive/josekiapp/`.
"""

PACK_CODE = r"""
import treesync as ts
rows, good = [], []
for f in sorted(glob.glob(IN_DIR + '/g_*.n.json')):
    name = os.path.basename(f)[:-len('.n.json')]
    a2 = os.path.join(OUT_DIR, name + '.a2.json')
    if not os.path.exists(a2):
        rows.append((name, 'NOT DONE', '', ''))
        continue
    N = json.load(open(f, encoding='utf-8-sig'))
    A = json.load(open(a2, encoding='utf-8-sig'))
    st, msg = ts.check_analysis(N, A)
    meta = {}
    if os.path.exists(a2[:-5] + '.meta.json'):
        meta = json.load(open(a2[:-5] + '.meta.json', encoding='utf-8'))
    rows.append((name, st, meta.get('seconds', ''), meta.get('sec_per_query', '')))
    if st == 'ok':
        good.append(a2)
        if os.path.exists(a2[:-5] + '.meta.json'):
            good.append(a2[:-5] + '.meta.json')
print('%-44s %-12s %8s %12s' % ('group', 'status', 'seconds', 's/query'))
for r in rows:
    print('%-44s %-12s %8s %12s' % r)
info = ['packaged %s' % time.strftime('%Y-%m-%d %H:%M:%S'), 'weights sha256 %s' % sha256_of(MODEL), 'katago ' + sh('%s version | head -3' % ENV['katago']).replace('\n', ' | '), GPU]
open(WORK + '/run_info.txt', 'w', encoding='utf-8').write('\n'.join(info) + '\n')
zp = os.path.join(WORK, 'a2_results.zip')
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in good:
        z.write(f, os.path.basename(f))
    for extra in (OUT_DIR + '/run_summary.json', WORK + '/run_info.txt'):
        if os.path.exists(extra):
            z.write(extra, os.path.basename(extra))
print('%d analysis files -> %s (%d bytes)' % (sum(1 for g in good if g.endswith('.a2.json')), zp, os.path.getsize(zp)))
if DRIVE_BASE:
    shutil.copy(zp, os.path.join(DRIVE_BASE, 'a2_results.zip'))
    print('copy on Drive:', os.path.join(DRIVE_BASE, 'a2_results.zip'))
if ON_COLAB:
    from google.colab import files
    files.download(zp)
elif ON_KAGGLE:
    print('Kaggle: download a2_results.zip from the Output panel on the right (or from the saved version after Save & Run All).')
"""

DONE_MD = r"""
## 7. 之后 / Afterwards

下载 `a2_results.zip`，按 README_cloud.md 里的命令把 `g_*.a2.json` 放进 `D:\tmp\work`（已有的 `a2.json` 不要覆盖），然后对每个分组运行 `wq.py check <分组名>`，状态必须是 `analysis: ok`。没有完成的分组留给本机继续，或者重新运行第 5 步单元格。

Download `a2_results.zip`, put the `g_*.a2.json` files into `D:\tmp\work` with the commands in README_cloud.md (never overwrite an existing `a2.json`), then run `wq.py check <group name>` for each group; the status must be `analysis: ok`. Groups that are not done are left to the local run, or run the cell of step 5 again.
"""


def fill(s):
    return s.replace('@@WEIGHTS_NAME@@', WEIGHTS_NAME).replace('@@WEIGHTS_SHA256@@', WEIGHTS_SHA256).replace('@@WEIGHTS_BYTES@@', str(WEIGHTS_BYTES))


def build():
    cells = [md(INTRO), md(SETTINGS_MD), code(fill(ENV_CODE)), md(SCRIPTS_MD)]
    for folder, name in EMBEDDED:
        cells.append(code('%%writefile ' + name + '\n' + rd(folder, name)))
    cells += [md(INPUT_MD), code(fill(INPUT_CODE)), md(KATAGO_MD), code(KATAGO_CODE), md(TRIAL_MD), code(TRIAL_CODE),
              md(RUN_MD), code(RUN_CODE), md(PACK_MD), code(PACK_CODE), md(DONE_MD)]
    for i, c in enumerate(cells):
        c['id'] = 'c%02d' % i
    return {'cells': cells, 'metadata': {'accelerator': 'GPU', 'colab': {'name': 'katago_batch.ipynb', 'provenance': []},
                                         'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                                         'language_info': {'name': 'python'}}, 'nbformat': 4, 'nbformat_minor': 5}


def main(argv=None):
    argv = sys.argv if argv is None else argv
    out = argv[1] if len(argv) > 1 else os.path.join(H, 'katago_batch.ipynb')
    nb = build()
    with open(out, 'w', encoding='utf-8', newline='\n') as f:   # LF on every platform, so the file does not change with the checkout
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('generated', out, '(%d cells)' % len(nb['cells']))


if __name__ == '__main__':
    main()
