"""Transcribe the audio of a video with faster-whisper: t.json = [{"s": start, "e": end, "t": text}, ...]

Usage: tr.py video.mp4 out.json

Before this wrote anything the result was never looked at: a failed audio extraction gave an empty transcript that was
saved as "done" for ever. Now an implausible transcript is rejected (no t.json, a t.rej.json with the reasons, exit code 3).
"""
import os
import subprocess
import sys

import numpy as np

from wqutil import atomic_write_json, find_ffmpeg, setup_stdio

PROMPT = "先手 后手 二间高夹 小目 小飞挂 飞压 冲断 白棋 黑棋 定式 AI 胜率 征子 一路 二路 三路"   # nudges whisper towards go vocabulary


def extract_audio(ff, path):
    """16 kHz mono float32 samples, plus ffmpeg's stderr."""
    r = subprocess.run([ff, '-v', 'error', '-i', path, '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True)
    raw = r.stdout[:len(r.stdout) // 4 * 4]
    return np.frombuffer(raw, np.float32), r.stderr.decode('utf-8', 'replace')


def check_transcript(out, seconds, audio_err=''):
    """Reasons to reject a transcript of `seconds` of audio (empty list = fine)."""
    if seconds < 1:
        return ['no audio could be decoded (%s)' % (audio_err.strip()[-150:] or 'file unreadable or without an audio track')]
    why = []
    text = ''.join(x['t'] for x in out)
    if not out and seconds > 60:
        why.append('no speech recognised in %d s of audio' % seconds)
    elif seconds > 120 and len(text) < seconds / 60 * 10:
        why.append('only %d characters of text in %d minutes of audio' % (len(text), seconds / 60))
    # whisper itself emits an odd U+FFFD now and then (0.3% at most in the 29 real transcripts, fix() strips them); a lot of them means damaged text
    if text.count('\ufffd') > 0.02 * max(1, len(text)):
        why.append('%d of %d characters are replacement characters (text encoding was damaged)' % (text.count('\ufffd'), len(text)))
    if any(x['e'] < x['s'] or x['s'] > seconds * 1.05 + 5 for x in out):
        why.append('segment times do not fit the audio length (%d s)' % seconds)
    return why


def main(argv=None):
    setup_stdio()
    a = argv if argv is not None else sys.argv
    if len(a) < 3:
        print(__doc__, file=sys.stderr)
        return 1
    ff = find_ffmpeg()
    if not ff:
        print('ffmpeg not found (set FFMPEG=path)', file=sys.stderr)
        return 1
    audio, err = extract_audio(ff, a[1])
    out = []
    if len(audio) / 16000 >= 1:
        from faster_whisper import WhisperModel   # heavy import, only when there is something to transcribe
        m = WhisperModel("small", device="cpu", compute_type="int8")
        seg, _ = m.transcribe(audio, language="zh", initial_prompt=PROMPT, vad_filter=True)
        out = [{"s": round(x.start, 1), "e": round(x.end, 1), "t": x.text} for x in seg]
    why = check_transcript(out, len(audio) / 16000, err)
    if why:
        atomic_write_json(os.path.splitext(a[2])[0] + '.rej.json', {'reasons': why}, ensure_ascii=False, indent=1)
        print('REJECTED %s: %s' % (a[1], '; '.join(why)), file=sys.stderr)
        return 3
    atomic_write_json(a[2], out, ensure_ascii=False)
    print(len(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
