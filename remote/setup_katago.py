#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download and check the Linux GPU build of KataGo (works on Colab / Kaggle / Slurm nodes). No root needed, no system libraries are touched.

What it does:
  1) Downloads katago-<ver>-<build>-linux-x64.zip from the GitHub release and unpacks it (default v1.18.2 + cuda12.1-cudnn9.8.0:
     it is built against the lowest CUDA version, so it is the most forward-compatible with the newer CUDA 12.x runtimes in
     cloud images; since v1.18.x, Transformer networks need cuDNN >= 9.8);
  2) uses ldd to find missing shared libraries; if cuDNN/cuBLAS/cudart/nvrtc are missing, installs them with pip into a
     separate directory (--target, system Python packages are untouched) and builds the matching LD_LIBRARY_PATH;
  3) locates the weights file (given with --model, or searched for in the usual places; otherwise --weights-url is required);
  4) writes <dir>/env.sh and <dir>/env.json, and finally prints KATAGO_BIN / KATAGO_MODEL / LD_LIBRARY_PATH.

References (checked 2026-11): KataGo v1.18.2 release page https://github.com/lightvector/KataGo/releases/tag/v1.18.2
  - "Use CUDNN >= 9.8.0. The CUDNN 8.9.7 builds will be a LOT slower when running transformers"
  - "TensorRT versions older than 10 are not supported."
  - v1.18.2 adds tensor-core attention for Turing (RTX 20xx / Tesla T4, sm_75), speeding up Transformer networks by more than 50%.
  5) checks the downloaded zip against the sha256 published on the release page (table KNOWN_SHA256 below).
Note: this has not been run on real hardware (the environment it was written in had no GPU); the version combination was picked
from the official release notes. The asset names and checksums were read from the release data on 2026-11-08; nothing was downloaded. If something fails, see the "Troubleshooting" section of README.md.
"""
import argparse, glob, hashlib, json, os, shutil, subprocess, sys, urllib.request, zipfile

# sha256 of the official Linux release zips of KataGo v1.18.2, copied from the GitHub release data on 2026-11-08.
# A download that does not match is deleted and the run stops: a broken or swapped binary must not be executed.
# Other versions or builds are not in this table and are only reported as "not verified".
KNOWN_SHA256 = {
    'katago-v1.18.2-cuda12.1-cudnn9.8.0-linux-x64.zip': '3e30b486b7bc38287eeead350aa832ff8ca50d1f0c0a83b5409cabf8a3bc9c5d',
    'katago-v1.18.2-cuda12.5-cudnn9.8.0-linux-x64.zip': '8c39d9ac1053f0e0eff0b0d376fcc2b7503e8caf44020710dda758de53a802f8',
    'katago-v1.18.2-cuda12.8-cudnn9.8.0-linux-x64.zip': '2cb197fc9bc2050f29112abb5b83cdbad63936cb4605d6e199772aedc9806c02',
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_zip(path, name, enforce=True):
    """True when the zip matches the published checksum or none is known; on a mismatch the file is removed and False returned."""
    want = KNOWN_SHA256.get(name)
    if not want:
        print('No published checksum known for %s: not verified.' % name)
        return True
    got = sha256_file(path)
    if got == want:
        print('Checksum of %s matches the release (sha256 %s...)' % (name, got[:16]))
        return True
    print('!! Checksum mismatch for %s' % name)
    print('   expected %s' % want)
    print('   got      %s' % got)
    if enforce:
        os.remove(path)
        print('   The file was deleted. Try again; if it keeps failing, use another --build or pass --no-verify only if you know why.')
        return False
    return True


def sh(cmd, env=None):
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def download(url, dst):
    print('Downloading', url, flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'josekiapp-remote/1'})
    with urllib.request.urlopen(req) as r, open(dst + '.part', 'wb') as f:
        total = int(r.headers.get('Content-Length', '0') or 0)
        got = 0
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            got += len(b)
            if total:
                print('\r  %d / %d MB' % (got >> 20, total >> 20), end='', flush=True)
    print()
    os.replace(dst + '.part', dst)


def missing_libs(binary, env):
    r = sh(['ldd', binary], env)
    return sorted({ln.split('=>')[0].strip() for ln in r.stdout.splitlines() if 'not found' in ln}), r.stdout


def find_model(explicit):
    if explicit:
        return explicit if os.path.exists(explicit) else ''
    pats = ['./kata1-tf3-b11c768*.bin.gz', './*.bin.gz', '/content/*.bin.gz', '/content/drive/MyDrive/josekiapp/*.bin.gz',
            '/content/drive/MyDrive/*.bin.gz', '/kaggle/input/*/*.bin.gz', '/kaggle/input/*/*/*.bin.gz', os.path.expanduser('~/*.bin.gz')]
    for p in pats:
        hit = sorted(glob.glob(p))
        if hit:
            return hit[0]
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='katago_env')
    ap.add_argument('--ver', default=os.environ.get('KATAGO_VER', 'v1.18.2'))
    ap.add_argument('--build', default=os.environ.get('KATAGO_BUILD', 'cuda12.1-cudnn9.8.0'),
                    help='e.g. cuda12.1-cudnn9.8.0 / cuda12.5-cudnn9.8.0 / cuda12.8-cudnn9.8.0 / cuda13.2-cudnn9.24.0')
    ap.add_argument('--model', default=os.environ.get('KATAGO_MODEL', ''))
    ap.add_argument('--weights-url', default=os.environ.get('WEIGHTS_URL', ''))
    ap.add_argument('--no-verify', action='store_true', help='do not stop on a checksum mismatch of the KataGo zip (it is still reported)')
    ap.add_argument('--no-pip-libs', action='store_true', help='do not try to pip-install the NVIDIA runtime libraries when libraries are missing')
    a = ap.parse_args()

    d = os.path.abspath(a.dir)
    os.makedirs(d, exist_ok=True)
    nv = sh(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'])
    print('GPU:', nv.stdout.strip() or '(nvidia-smi unavailable -- no GPU runtime? Colab: Runtime > Change runtime type > GPU)')

    binary = os.path.join(d, 'katago')
    if not os.path.exists(binary):
        name = 'katago-%s-%s-linux-x64.zip' % (a.ver, a.build)
        z = os.path.join(d, name)
        download('https://github.com/lightvector/KataGo/releases/download/%s/%s' % (a.ver, name), z)
        if not verify_zip(z, name, enforce=not a.no_verify):
            sys.exit(1)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(d)
        os.chmod(binary, 0o755)
    print('KataGo:', binary)

    env = dict(os.environ)
    miss, out = missing_libs(binary, env)
    libpaths = []
    if miss and not a.no_pip_libs:
        print('Missing shared libraries:', miss)
        nvdir = os.path.join(d, 'nvlibs')
        pk = ['nvidia-cudnn-cu12', 'nvidia-cublas-cu12', 'nvidia-cuda-runtime-cu12', 'nvidia-cuda-nvrtc-cu12']
        print('Installing with pip into a separate directory %s (system packages are not affected): %s' % (nvdir, ' '.join(pk)), flush=True)
        r = sh([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--target', nvdir] + pk)
        if r.returncode:
            print(r.stderr[-800:])
        libpaths = sorted(glob.glob(os.path.join(nvdir, 'nvidia', '*', 'lib')))
        env['LD_LIBRARY_PATH'] = ':'.join(libpaths + [env.get('LD_LIBRARY_PATH', '')]).strip(':')
        miss, out = missing_libs(binary, env)
    if miss:
        # system libraries such as libzip: try apt when running as root (works on Colab, not on clusters)
        if hasattr(os, 'geteuid') and os.geteuid() == 0 and any('zip' in m for m in miss) and shutil.which('apt-get'):
            for pkg in ('libzip4', 'libzip4t64', 'libzip5'):
                if sh(['apt-get', 'install', '-y', '-qq', pkg]).returncode == 0:
                    break
            miss, out = missing_libs(binary, env)
    if miss:
        print('Still missing:', miss, '\n--- ldd ---\n' + out)
        print('=> See "Troubleshooting" in README.md: try another --build (cuda12.5/12.8), use the OpenCL/Eigen build, or ask the cluster admin to load the cuda/cudnn modules.')
    else:
        print('ldd check passed (no missing shared libraries)')

    model = find_model(a.model)
    if not model and a.weights_url:
        model = os.path.join(d, os.path.basename(a.weights_url.split('?')[0]))
        if not os.path.exists(model):
            download(a.weights_url, model)
    if not model:
        print('!! No weights file (*.bin.gz) found. Upload the same kata1-tf3-b11c768-s12752M-d6531M.bin.gz as on the local machine (about 262MB), or set WEIGHTS_URL / --weights-url.')
    else:
        print('Weights:', model, '(%d MB)' % (os.path.getsize(model) >> 20))

    ld = env.get('LD_LIBRARY_PATH', '')
    info = {'katago': binary, 'model': model, 'ld_library_path': ld, 'missing_libs': miss, 'ver': a.ver, 'build': a.build}
    json.dump(info, open(os.path.join(d, 'env.json'), 'w'), indent=1)
    open(os.path.join(d, 'env.sh'), 'w').write('export LD_LIBRARY_PATH="%s"\nexport KATAGO_BIN="%s"\nexport KATAGO_MODEL="%s"\n' % (ld, binary, model))
    print('Wrote %s/env.sh (bash: source it)' % d)
    print(json.dumps(info, ensure_ascii=False))


if __name__ == '__main__':
    main()
