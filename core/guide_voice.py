"""
core/guide_voice.py — Contagem BPM sincronizada
=================================================
Gera uma faixa de audio com "Um, Dois, Tres, Quatro" repetido
em loop na grade do BPM detectado.

Sempre perfeitamente sincronizada — baseada em BPM fixo, sem
deteccao de secoes.

Dependencias: edge-tts, numpy, soundfile, ffmpeg
"""

import sys
import asyncio
import tempfile
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from .utils import TEMP_DIR


VOICE_NAME   = "pt-BR-FranciscaNeural"
SAMPLE_RATE  = 44100
GUIDE_VOLUME = 0.80

COUNT_WORDS = ["Um", "Dois", "Três", "Quatro"]


def generate_guide_voice(track_info: dict, audio_path) -> Path | None:
    """
    Gera a faixa de contagem (1-2-3-4) no BPM detectado.

    Returns:
        Path para o WAV gerado, ou None se o TTS falhar.
    """

    duration      = track_info["duration"]
    bpm           = track_info["bpm"]
    beat_interval = 60.0 / bpm

    print(f"  ↳ Sintetizando números (Um, Dois, Três, Quatro)...")

    # Gera os 4 clipes de TTS uma única vez
    count_audios: list[np.ndarray | None] = []
    for word in COUNT_WORDS:
        count_audios.append(_synthesize_speech(word))

    if all(a is None for a in count_audios):
        print("  ⚠ TTS indisponível — contagem pulada.")
        return None

    total_samples = int(duration * SAMPLE_RATE)
    guide_buffer  = np.zeros((total_samples, 2), dtype=np.float32)

    beat_time = 0.0
    beat_idx  = 0
    while beat_time < duration:
        audio = count_audios[beat_idx % 4]
        if audio is not None:
            _mix_into_buffer(guide_buffer, audio, beat_time)
        beat_time += beat_interval
        beat_idx  += 1

    # Normaliza volume
    peak = np.max(np.abs(guide_buffer))
    if peak > 0:
        guide_buffer = guide_buffer / peak * GUIDE_VOLUME

    out_path = TEMP_DIR / "guide_voice.wav"
    sf.write(str(out_path), guide_buffer, SAMPLE_RATE, subtype="PCM_16")

    print(f"  ↳ Contagem gerada: {beat_idx // 4} compassos a {bpm:.1f} BPM")
    return out_path


def _synthesize_speech(text: str) -> np.ndarray | None:
    try:
        tmp_mp3 = Path(tempfile.mktemp(suffix=".mp3"))
        tmp_wav = Path(tempfile.mktemp(suffix=".wav"))

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(_run_tts(text, str(tmp_mp3)))

        subprocess.run(
            ["ffmpeg", "-y", "-i", str(tmp_mp3),
             "-ar", str(SAMPLE_RATE), "-ac", "2", str(tmp_wav)],
            capture_output=True, check=True
        )

        audio, _ = sf.read(str(tmp_wav), dtype="float32")
        if audio.ndim == 1:
            audio = np.column_stack([audio, audio])

        tmp_mp3.unlink(missing_ok=True)
        tmp_wav.unlink(missing_ok=True)
        return audio

    except Exception as e:
        print(f"  ⚠ TTS falhou para '{text}': {e}")
        return None


async def _run_tts(text: str, output_path: str) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=VOICE_NAME)
    await communicate.save(output_path)


def _mix_into_buffer(buffer: np.ndarray,
                     audio: np.ndarray,
                     position_sec: float) -> None:
    start    = int(position_sec * SAMPLE_RATE)
    end      = min(start + len(audio), len(buffer))
    if start >= len(buffer) or end <= 0:
        return
    buffer[start:end] += audio[:end - start]
