"""Shared helpers for the pipeline scripts: atomic file writes and tolerant json reading.

Why this exists: the pipeline gets killed and restarted a lot, and other tools
(build.ps1, the viewer, a second regen run) read its output while it is being
written. A half written json or sgf must never be visible, so every output goes
through atomic_write_*. Reads go through read_json, which copes with a BOM and
gives an error message that names the file.
"""
import json
import os
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
