#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generates katago_batch.ipynb (for both Colab and Kaggle). The notebook embeds the current contents of analyze_remote.py and setup_katago.py,
so you only need to upload this one .ipynb plus the n.json zip. After changing either script, re-run this file:   python make_notebook.py
"""
import json, os

H = os.path.dirname(os.path.abspath(__file__))
rd = lambda n: open(os.path.join(H, n), encoding='utf-8').read()


def md(s):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': s.strip('\n').splitlines(True)}


def code(s):
    return {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': s.strip('\n').splitlines(True)}


cells = [
    md("""
# Joseki library · remote-GPU batch AI local evaluation (KataGo)

Moves the slowest step of the local pipeline (`analyze2.py`, 30~40 minutes per group on the integrated GPU) onto a machine with a discrete GPU and runs it as a batch. The output is `g_<name>.a2.json` in **exactly the same format** as `analyze2.py`.

**How to use (Colab free tier / Kaggle)**
1. Select a GPU runtime (Colab: *Runtime → Change runtime type → T4 GPU*; Kaggle: *Settings → Accelerator → GPU*, and turn Internet on).
2. On the local machine, zip the `g_*.n.json` files you want analyzed (see README.md) and upload the zip in the 4th code cell (or put it on Google Drive / a Kaggle Dataset).
3. The weights `kata1-tf3-b11c768-s12752M-d6531M.bin.gz` (about 262MB) are the same file the local machine uses; the easiest way is to upload them once to Drive / a Kaggle Dataset.
4. Run the cells from top to bottom. If the connection drops, reconnect and **re-run all cells**; finished groups are skipped automatically (progress survives only if the output is on Drive or in `/kaggle/working`).
5. The last cell zips the results. After downloading, put them back into `D:\\tmp\\work` (replacing/adding `g_<name>.a2.json`), then continue with the usual `regen.py` + `tools\\build.ps1`.

**Terms of use (must read)**: the Colab free tier may **only be used as an interactive notebook**. This notebook only runs a batch job inside the notebook process; it opens no ports and uses no SSH, tunnels or remote desktop.
**Do not** add a keep-alive script, an ngrok/cloudflared tunnel, or use Colab as a server for the web page to connect to in real time -- the Colab free-tier FAQ explicitly prohibits these, and you may be throttled or banned.
Keep the browser tab open and stay nearby; if it says the usage limit has been reached, stop and come back another day or switch platform instead of working around it.
"""),
    code("""
import os, subprocess, sys, glob, json, time
ON_KAGGLE = os.path.exists('/kaggle/working')
ON_COLAB = 'google.colab' in sys.modules
WORK = '/kaggle/working' if ON_KAGGLE else ('/content' if ON_COLAB else os.getcwd())
print('Platform:', 'Kaggle' if ON_KAGGLE else 'Colab' if ON_COLAB else 'other', 'working directory:', WORK)
print(subprocess.run(['nvidia-smi'], capture_output=True, text=True).stdout or '!! No GPU detected: switch to a GPU runtime first')
"""),
    md("The next two cells write the scripts into the working directory (same content as the files of the same name in the `remote/` directory)."),
    code("%%writefile analyze_remote.py\n" + rd('analyze_remote.py')),
    code("%%writefile setup_katago.py\n" + rd('setup_katago.py')),
    md("""
## Input and output locations
- **Input**: looks for `g_*.n.json` in `IN_DIR`; if there are none, Kaggle searches `/kaggle/input/*/` automatically and Colab shows an upload box (choose a zip or several json files).
- **Output**: written to `WORK/out` by default; on Colab, set `USE_DRIVE=True` to keep progress across disconnects (a Google Drive authorization prompt appears; you approve it yourself).
"""),
    code("""
import zipfile, shutil
USE_DRIVE = False            # Colab: True => put input and output under MyDrive/josekiapp/, so a disconnect does not lose them
IN_DIR = os.path.join(WORK, 'in')
OUT_DIR = os.path.join(WORK, 'out')
if ON_COLAB and USE_DRIVE:
    from google.colab import drive
    drive.mount('/content/drive')
    base = '/content/drive/MyDrive/josekiapp'
    IN_DIR, OUT_DIR = base + '/in', base + '/out'
os.makedirs(IN_DIR, exist_ok=True); os.makedirs(OUT_DIR, exist_ok=True)

def have_inputs():
    return sorted(glob.glob(IN_DIR + '/g_*.n.json'))

if not have_inputs():
    for d in glob.glob('/kaggle/input/*') + glob.glob('/kaggle/input/*/*'):
        for f in glob.glob(d + '/g_*.n.json'):
            shutil.copy(f, IN_DIR)
if not have_inputs() and ON_COLAB:
    from google.colab import files
    print('Select a zip containing g_*.n.json, or multi-select the json files to upload:')
    for name, data in files.upload().items():
        p = os.path.join(IN_DIR, name)
        open(p, 'wb').write(data)
        if name.endswith('.zip'):
            with zipfile.ZipFile(p) as z:
                for m in z.namelist():
                    if m.endswith('.n.json'):
                        open(os.path.join(IN_DIR, os.path.basename(m)), 'wb').write(z.read(m))
inp = have_inputs()
print('%d input groups:' % len(inp)); [print('  ', os.path.basename(f)) for f in inp]
assert inp, 'No g_*.n.json found -- see the instructions above'
"""),
    md("""
## Install KataGo (GPU build) and locate the weights
The weights are found automatically if they are in one of these places: the working directory, `/content/*.bin.gz`, `MyDrive/josekiapp/*.bin.gz`, `/kaggle/input/*/`.
You can also set `WEIGHTS_PATH` (a local path) or `WEIGHTS_URL` (a download URL). **Use the same weights as the local machine**, otherwise old and new analyses are not comparable.
"""),
    code("""
WEIGHTS_PATH = ''   # e.g. '/content/drive/MyDrive/josekiapp/kata1-tf3-b11c768-s12752M-d6531M.bin.gz'
WEIGHTS_URL = ''    # e.g. a direct download link to that weights file (leave empty if unsure and upload it instead)
KATAGO_BUILD = 'cuda12.1-cudnn9.8.0'   # if libraries are missing, try cuda12.5-cudnn9.8.0 / cuda12.8-cudnn9.8.0 in turn
cmd = [sys.executable, '-u', 'setup_katago.py', '--dir', WORK + '/katago_env', '--build', KATAGO_BUILD]
if WEIGHTS_PATH: cmd += ['--model', WEIGHTS_PATH]
if WEIGHTS_URL: cmd += ['--weights-url', WEIGHTS_URL]
subprocess.run(cmd, check=True)
ENV = json.load(open(WORK + '/katago_env/env.json'))
if not ENV['model'] and ON_COLAB:
    from google.colab import files
    print('Upload the weights file kata1-tf3-b11c768-s12752M-d6531M.bin.gz (about 262MB, the upload is slow):')
    for name, data in files.upload().items():
        open(WORK + '/' + name, 'wb').write(data)
    subprocess.run(cmd, check=True)
    ENV = json.load(open(WORK + '/katago_env/env.json'))
assert ENV['model'], 'no weights file'
assert not ENV['missing_libs'], 'missing shared libraries: %s (see Troubleshooting in the README)' % ENV['missing_libs']
os.environ['LD_LIBRARY_PATH'] = ENV['ld_library_path']
print('Ready:', ENV['katago'], ENV['model'])
"""),
    md("""
## (Optional) Trial run on 3 branch points to check the speed
The local integrated GPU takes about 11 seconds per query (220 visits). The time of each query is printed here, so you can estimate how long the whole batch will take.
"""),
    code("""
t0 = time.time()
subprocess.run([sys.executable, '-u', 'analyze_remote.py', '--in', inp[0], '--out', WORK + '/trial', '--katago', ENV['katago'],
                '--model', ENV['model'], '--limit', '3', '--force'], check=True)
print('Trial run took %.0f seconds (including model loading and first-time compilation, so the first run is slower)' % (time.time() - t0))
"""),
    md("## Full batch run (can be interrupted at any time; re-running resumes automatically)"),
    code("""
r = subprocess.run([sys.executable, '-u', 'analyze_remote.py', '--in', IN_DIR, '--out', OUT_DIR, '--katago', ENV['katago'],
                    '--model', ENV['model'], '--visits', '220', '--forced', '100'])
print('exit code', r.returncode)
"""),
    md("## Package the results"),
    code("""
res = sorted(glob.glob(OUT_DIR + '/g_*.a2.json')) + sorted(glob.glob(OUT_DIR + '/g_*.a2.meta.json'))
zp = WORK + '/a2_results.zip'
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in res: z.write(f, os.path.basename(f))
print('%d files -> %s' % (len(res), zp))
if ON_COLAB:
    from google.colab import files
    files.download(zp)
"""),
]

nb = {'cells': cells, 'metadata': {'accelerator': 'GPU', 'colab': {'name': 'katago_batch.ipynb', 'provenance': []},
                                   'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
                                   'language_info': {'name': 'python'}}, 'nbformat': 4, 'nbformat_minor': 5}
for i, c in enumerate(cells):
    c['id'] = 'c%02d' % i
out = os.path.join(H, 'katago_batch.ipynb')
json.dump(nb, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('generated', out, '(%d cells)' % len(cells))
