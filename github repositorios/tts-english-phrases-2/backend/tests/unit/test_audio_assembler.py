"""
Unit tests for services/audio_assembler.py
Patches AudioSegment.from_mp3 (requires ffmpeg) and AudioSegment.export
so the tests run without ffmpeg installed.
"""
import io
import pytest
from unittest.mock import patch, MagicMock
from pydub import AudioSegment

from services.audio_assembler import build_phrase_block, assemble_session


def _silent(ms: int = 2000) -> AudioSegment:
    """Convenience: AudioSegment.silent works without ffmpeg."""
    return AudioSegment.silent(duration=ms)


# ── build_phrase_block ────────────────────────────────────────────────────────

def test_build_phrase_block_returns_audio_segment():
    with patch("services.audio_assembler.AudioSegment.from_mp3", return_value=_silent(2000)):
        block = build_phrase_block(b"fake_normal", b"fake_slow")
    assert isinstance(block, AudioSegment)


def test_build_phrase_block_is_longer_than_input():
    """Block must be longer than the input phrase (adds pauses + slow version)."""
    input_ms = 2000
    with patch("services.audio_assembler.AudioSegment.from_mp3", return_value=_silent(input_ms)):
        block = build_phrase_block(b"fake_normal", b"fake_slow")
    # Minimum: normal(2000) + 1s + slow(2000) + 1s + normal(2000) + 1.5s = 9500ms
    assert len(block) > input_ms


def test_build_phrase_block_structure_timing():
    """Block length should be roughly 9.5s for a 2s input phrase."""
    with patch("services.audio_assembler.AudioSegment.from_mp3", return_value=_silent(2000)):
        block = build_phrase_block(b"fake_normal", b"fake_slow")
    # normal(2000) + 1000 + slow(2000) + 1000 + normal(2000) + 1500 = 9500ms, allow ±500ms
    assert 9000 < len(block) < 11000


def test_build_phrase_block_accepts_any_bytes():
    """Should not inspect the bytes content — leaves that to pydub."""
    for fake in [b"", b"\x00\x01\x02", b"ID3" + b"\x00" * 100]:
        with patch("services.audio_assembler.AudioSegment.from_mp3", return_value=_silent(1000)):
            block = build_phrase_block(fake, fake)
        assert isinstance(block, AudioSegment)


# ── assemble_session ──────────────────────────────────────────────────────────

def test_assemble_session_returns_bytes():
    pairs = [(b"n1", b"s1"), (b"n2", b"s2"), (b"n3", b"s3")]
    with patch("services.audio_assembler.AudioSegment.from_mp3", return_value=_silent(500)):
        with patch("services.audio_assembler.AudioSegment.export") as mock_export:
            result = assemble_session(pairs)
    assert isinstance(result, bytes)
    mock_export.assert_called_once()


def test_assemble_session_export_called_with_mp3():
    with patch("services.audio_assembler.AudioSegment.from_mp3", return_value=_silent(500)):
        with patch("services.audio_assembler.AudioSegment.export") as mock_export:
            assemble_session([(b"chunk", b"slow")])
    _, kwargs = mock_export.call_args
    assert kwargs.get("format") == "mp3"
    assert kwargs.get("bitrate") == "128k"


def test_assemble_session_single_chunk():
    with patch("services.audio_assembler.AudioSegment.from_mp3", return_value=_silent(500)):
        with patch("services.audio_assembler.AudioSegment.export"):
            result = assemble_session([(b"only_one", b"only_one_slow")])
    assert isinstance(result, bytes)


def test_assemble_session_empty_raises():
    with pytest.raises(ValueError, match="No audio chunks"):
        assemble_session([])


def test_assemble_session_combined_longer_than_single_block():
    """Session with 3 pairs should produce a longer combined segment than 1 block."""
    with patch("services.audio_assembler.AudioSegment.from_mp3", return_value=_silent(1000)):
        captured = {}

        def fake_export(self, out, **kwargs):
            captured["len"] = len(self)

        with patch.object(AudioSegment, "export", fake_export):
            assemble_session([(b"a", b"as"), (b"b", b"bs"), (b"c", b"cs")])

        single_block_len = len(build_phrase_block(b"single", b"single_slow"))

    assert captured["len"] > single_block_len


# ── assemble_session with target_ms ───────────────────────────────────────────

def test_assemble_session_without_target_ms_includes_all_blocks():
    """Without target_ms, all pairs are assembled."""
    pairs = [(b"a", b"as"), (b"b", b"bs"), (b"c", b"cs")]
    with patch("services.audio_assembler.AudioSegment.from_mp3", return_value=_silent(1000)):
        captured = {}

        def fake_export(self, out, **kwargs):
            captured["len"] = len(self)

        with patch.object(AudioSegment, "export", fake_export):
            assemble_session(pairs)

    # 3 blocks of ~7500ms each → total ~22500ms
    single_block_len = 1000 + 1000 + 1000 + 1000 + 1000 + 1500  # 6500ms
    assert captured["len"] >= single_block_len * 3


def test_assemble_session_target_ms_stops_early():
    """With a very small target_ms, only the first block is included."""
    pairs = [(b"a", b"as"), (b"b", b"bs"), (b"c", b"cs")]
    # Each block with 1000ms audio = 1000+1000+1000+1000+1000+1500 = 6500ms
    # Setting target_ms=1 means after the first block (6500ms >= 1ms), stop.
    with patch("services.audio_assembler.AudioSegment.from_mp3", return_value=_silent(1000)):
        captured = {}

        def fake_export(self, out, **kwargs):
            captured["len"] = len(self)

        with patch.object(AudioSegment, "export", fake_export):
            assemble_session(pairs, target_ms=1)

    single_block_len = 1000 + 1000 + 1000 + 1000 + 1000 + 1500  # 6500ms
    assert captured["len"] == single_block_len


def test_assemble_session_large_target_ms_includes_all_blocks():
    """With a very large target_ms, all blocks are still included."""
    pairs = [(b"a", b"as"), (b"b", b"bs"), (b"c", b"cs")]
    with patch("services.audio_assembler.AudioSegment.from_mp3", return_value=_silent(1000)):
        captured = {}

        def fake_export(self, out, **kwargs):
            captured["len"] = len(self)

        with patch.object(AudioSegment, "export", fake_export):
            assemble_session(pairs, target_ms=10_000_000)

    single_block_len = 1000 + 1000 + 1000 + 1000 + 1000 + 1500  # 6500ms
    assert captured["len"] == single_block_len * 3
