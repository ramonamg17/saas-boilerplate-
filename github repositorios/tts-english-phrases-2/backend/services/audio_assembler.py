import io
from pydub import AudioSegment


def build_phrase_block(normal_bytes: bytes, slow_bytes: bytes) -> AudioSegment:
    """
    Structure: normal → 1s pause → slow(0.7x) → 1s pause → normal → 1.5s pause
    Both normal and slow are rendered by the TTS service at the correct speed.
    """
    normal = AudioSegment.from_mp3(io.BytesIO(normal_bytes))
    slow = AudioSegment.from_mp3(io.BytesIO(slow_bytes))

    pause_1s = AudioSegment.silent(duration=1000)
    pause_1_5s = AudioSegment.silent(duration=1500)

    return normal + pause_1s + slow + pause_1s + normal + pause_1_5s


def assemble_session(audio_pairs: list[tuple[bytes, bytes]], target_ms: int | None = None) -> bytes:
    """Build phrase blocks from (normal, slow) pairs and concatenate into a single MP3.

    If target_ms is given, stops adding blocks once the combined length reaches the target
    (the block that causes it to meet/exceed the target is included; no mid-phrase cuts).
    """
    if not audio_pairs:
        raise ValueError("No audio chunks to assemble")

    blocks = [build_phrase_block(normal, slow) for normal, slow in audio_pairs]
    combined = blocks[0]
    for block in blocks[1:]:
        if target_ms is not None and len(combined) >= target_ms:
            break
        combined = combined + block

    output = io.BytesIO()
    combined.export(output, format="mp3", bitrate="128k")
    return output.getvalue()
