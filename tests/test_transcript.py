"""Transcript sanity check: an empty or damaged transcript must not be saved as 'done'."""
import tr


def seg(s, e, t):
    return {"s": s, "e": e, "t": t}


def test_normal_transcript_passes():
    out = [seg(0, 5, "先看黑棋" * 20), seg(5, 10, "白棋压" * 20)]
    assert tr.check_transcript(out, 600) == []


def test_no_audio_and_no_speech_are_rejected():
    assert "no audio" in tr.check_transcript([], 0.2, "Invalid data found")[0]
    assert "Invalid data found" in tr.check_transcript([], 0, "Invalid data found")[0]
    assert "no speech recognised" in tr.check_transcript([], 300)[0]
    assert tr.check_transcript([], 30) == [], "a very short clip may really be silent"


def test_far_too_little_text_is_rejected():
    assert "only 3 characters" in tr.check_transcript([seg(0, 1, "abc")], 1200)[0]


def test_replacement_characters_are_tolerated_in_small_numbers_only():
    text = "脱�" + "白棋压" * 100                      # whisper does this now and then (0.3% in real data)
    assert tr.check_transcript([seg(0, 5, text)], 600) == []
    damaged = "�" * 30 + "白" * 100
    assert "replacement characters" in tr.check_transcript([seg(0, 5, damaged)], 600)[0]


def test_segment_times_must_fit_the_audio():
    out = [seg(0, 5, "白棋" * 100), seg(9000, 9005, "x" * 10)]
    assert any("segment times" in r for r in tr.check_transcript(out, 600))
    assert any("segment times" in r for r in tr.check_transcript([seg(5, 4, "白棋" * 100)], 600))
