"""Shared helpers for the pipeline scripts: atomic file writes, tolerant json reading, utf-8 and logging.

Why this exists: the pipeline gets killed and restarted a lot, and other tools
(build.ps1, the viewer, a second regen run) read its output while it is being
written. A half written json or sgf must never be visible, so every output goes
through atomic_write_*. Reads go through read_json, which copes with a BOM and
gives an error message that names the file. setup_stdio/utf8_env/Log keep every
log line and child process on utf-8 (Windows consoles default to cp936).
"""
import glob
import json
import os
import random
import shutil
import sys
import threading
import time

_MISSING = object()


def atomic_write_bytes(path, data, tries=8):
    """Write data so readers see either the old file or the new one, never a partial file.

    The data goes to a temp file next to the target, is fsynced, and is then moved
    over the target with os.replace (atomic on the same volume). On Windows
    os.replace can raise PermissionError while another process has the target open
    (build.ps1, a virus scanner, a file server), so it is retried a few times.
    """
    path = os.fspath(path)
    tmp = '%s.tmp.%d.%d' % (path, os.getpid(), threading.get_ident())
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        for k in range(tries):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if k == tries - 1:
                    raise
                time.sleep(0.25 * (k + 1))
    finally:
        # Only still there when the write or the replace failed: do not leave junk behind.
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def atomic_write_text(path, text, encoding='utf-8'):
    """Atomic text write. Always utf-8 and no newline translation (LF stays LF on Windows)."""
    atomic_write_bytes(path, text.encode(encoding))


def atomic_write_json(path, obj, ensure_ascii=True, **kw):
    """Atomic json write. The object is serialised first, so a TypeError cannot touch the old file."""
    atomic_write_text(path, json.dumps(obj, ensure_ascii=ensure_ascii, **kw))


def read_json(path, default=_MISSING, quarantine=False):
    """Read a json file as utf-8 (a BOM is fine: PowerShell's Set-Content writes one).

    A missing file or a file that does not parse returns `default` when one is given,
    otherwise raises with the path in the message. With quarantine=True an unparsable
    file is renamed to <path>.corrupt so the stage that produces it runs again instead
    of failing on the same broken file forever (typical after a kill during a write).
    """
    try:
        with open(path, encoding='utf-8-sig') as f:
            return json.load(f)
    except FileNotFoundError:
        if default is not _MISSING:
            return default
        raise
    except (ValueError, UnicodeDecodeError) as e:
        if quarantine:
            try:
                os.replace(path, os.fspath(path) + '.corrupt')
            except OSError:
                pass
        if default is not _MISSING:
            return default
        raise ValueError('%s is not valid json: %s' % (path, e)) from e


def find_ffmpeg():
    """Return the ffmpeg path: env FFMPEG, the WinGet install this pipeline was built on, or PATH.

    Returns None when nothing is found; callers must turn that into a clear error
    (the old code did glob(...)[0] at import time and died with an IndexError).
    """
    p = os.environ.get('FFMPEG')
    if p and os.path.exists(p):
        return p
    la = os.environ.get('LOCALAPPDATA')
    if la:
        pat = os.path.join(la, 'Microsoft', 'WinGet', 'Packages', 'Gyan.FFmpeg*', '**', 'ffmpeg.exe')
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    return shutil.which('ffmpeg')


def setup_stdio():
    """Force utf-8 on stdout/stderr.

    A cp936 (GBK) Windows console either garbles Chinese log lines or raises
    UnicodeEncodeError on characters it cannot show. errors='replace' keeps the
    process alive in every case. Child processes get the same via utf8_env().
    """
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError, OSError):
            pass  # not a real text stream (pytest capture, pythonw): nothing to fix


def utf8_env(extra=None):
    """Environment for child processes: utf-8 text mode and unbuffered output (so logs show progress live)."""
    env = dict(os.environ)
    env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    if extra:
        env.update(extra)
    return env


class Log:
    """print() plus an append-only utf-8 log file. Never raises: a broken console must not kill a worker thread."""

    def __init__(self, path_fn):
        self.path_fn = path_fn  # a function, so the log dir can still change after import (tests)
        self.lock = threading.Lock()

    def __call__(self, *a):
        line = time.strftime('%H:%M:%S ') + ' '.join(str(x) for x in a)
        try:
            print(line, flush=True)
        except (UnicodeError, OSError):
            try:
                print(line.encode('ascii', 'replace').decode('ascii'), flush=True)
            except Exception:
                pass
        try:
            p = self.path_fn()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with self.lock, open(p, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except OSError:
            pass


def retry_with_backoff(attempt, tries=4, base=60.0, factor=3.0, cap=900.0, jitter=0.2, sleep=time.sleep, log=lambda *a: None):
    """Call attempt() -> (ok, info) until it succeeds or `tries` are used up. Returns (ok, info of the last try).

    The wait grows base, base*factor, ... up to `cap`, plus some jitter. HTTP 567/412 throttling needs minutes
    to clear, so hammering every 45 s (the old loop) only extends it. The caller must not hold any shared
    lock while this sleeps: the sleep happens here, outside attempt().
    """
    info = ''
    for k in range(tries):
        ok, info = attempt()
        if ok:
            return True, info
        if k < tries - 1:
            wait = min(cap, base * factor ** k) * (1 + random.uniform(0, jitter))
            log('try %d/%d failed (%s), waiting %ds' % (k + 1, tries, info, wait))
            sleep(wait)
    return False, info


class Manifest:
    """Small json file {key: record} for things that failed (videos). Thread safe, atomic, utf-8."""

    def __init__(self, path_fn):
        self.path_fn = path_fn
        self.lock = threading.Lock()

    def _load(self):
        d = read_json(self.path_fn(), default={}, quarantine=True)
        return d if isinstance(d, dict) else {}

    def record(self, key, **fields):
        with self.lock:
            d = self._load()
            old = d.get(str(key), {})
            fields['attempts'] = old.get('attempts', 0) + 1
            fields['time'] = time.strftime('%Y-%m-%d %H:%M:%S')
            d[str(key)] = fields
            os.makedirs(os.path.dirname(self.path_fn()), exist_ok=True)
            atomic_write_json(self.path_fn(), d, ensure_ascii=False, indent=1)

    def clear(self, key):
        with self.lock:
            d = self._load()
            if str(key) in d:
                del d[str(key)]
                atomic_write_json(self.path_fn(), d, ensure_ascii=False, indent=1)

    def all(self):
        with self.lock:
            return self._load()


def single_instance(path):
    """Take an exclusive lock on `path` for the life of the process. Returns the open file (keep it referenced) or None if
    another process already holds it. The OS drops the lock when the process dies, so a crash never leaves a stale lock
    behind. Two pipelines at once would fight over downloads, the GPU and the same output files."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    f = open(path, 'a+b')
    try:
        f.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f
