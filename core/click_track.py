"""
core/click_track.py — Geração do click track sincronizado
==========================================================
Gera uma faixa de metrônomo (click track) baseada no BPM
detectado, com:
  - Batida forte no tempo 1 (acento do compasso)
  - Batida suave nos tempos 2, 3, 4
  - Sincronizada com o beat_times real da música (não BPM fixo)
  - Duração idêntica à música original

Dependências: numpy, scipy, soundfile
"""

import numpy as np
import soundfile as sf
from pathlib import Path

from .utils import TEMP_DIR


# ── Parâmetros do click ───────────────────────────────────────────────────────
SAMPLE_RATE     = 44100   # Hz — padrão DAW
CLICK_FREQ_1    = 1000    # Hz — tom do tempo forte (mais alto e brilhante)
CLICK_FREQ_2    = 800     # Hz — tom dos tempos fracos
CLICK_DURATION  = 0.02    # segundos — duração de cada click (20ms)
CLICK_VOL_STRONG = 0.8    # amplitude do tempo 1 (0.0–1.0)
CLICK_VOL_WEAK   = 0.5    # amplitude dos tempos 2, 3, 4


def generate_click_track(track_info: dict, audio_path) -> Path:
    """
    Gera o click track e salva como WAV.

    Args:
        track_info: Dicionário retornado pelo analyzer (contém beat_times, bpm, duration).
        audio_path: Path do áudio original (usado para nomear o arquivo).

    Returns:
        Path para o arquivo WAV do click track.
    """

    sr          = SAMPLE_RATE
    duration    = track_info["duration"]
    bpm         = track_info["bpm"]

    # Gera batidas em intervalos constantes baseados no BPM detectado.
    # Isso garante um click estável do início ao fim, sem variações de tempo.
    beat_interval = 60.0 / bpm
    beat_times    = np.arange(0, duration, beat_interval)

    # ── Cria buffer de silêncio com a duração total da música ─────────────────
    total_samples = int(duration * sr)
    click_buffer  = np.zeros(total_samples, dtype=np.float32)

    # ── Amostras de click: forte e fraco ─────────────────────────────────────
    click_strong = _make_click(CLICK_FREQ_1, CLICK_DURATION, sr, CLICK_VOL_STRONG)
    click_weak   = _make_click(CLICK_FREQ_2, CLICK_DURATION, sr, CLICK_VOL_WEAK)

    # ── Posiciona cada click no buffer ────────────────────────────────────────
    for i, beat_time in enumerate(beat_times):
        sample_pos = int(beat_time * sr)

        # Verifica se ainda está dentro do buffer
        if sample_pos >= total_samples:
            break

        # Tempo 1 de cada compasso = múltiplo de 4 beats → click forte
        is_downbeat = (i % 4 == 0)
        click = click_strong if is_downbeat else click_weak

        # Garante que o click cabe no buffer sem ultrapassar o fim
        end_pos = min(sample_pos + len(click), total_samples)
        click_buffer[sample_pos:end_pos] += click[:end_pos - sample_pos]

    # ── Normaliza para evitar clipping (distorção por volume alto) ────────────
    peak = np.max(np.abs(click_buffer))
    if peak > 0.95:
        click_buffer = click_buffer / peak * 0.95

    # ── Converte para estéreo (copia o canal) ────────────────────────────────
    stereo = np.column_stack([click_buffer, click_buffer])

    # ── Salva o arquivo WAV ───────────────────────────────────────────────────
    bpm_str  = f"{int(round(bpm))}bpm"
    out_path = TEMP_DIR / f"click_{bpm_str}.wav"
    sf.write(str(out_path), stereo, sr, subtype="PCM_16")

    print(f"  ↳ Click track gerado: {bpm_str}, {len(beat_times)} batidas")
    return out_path


def _make_click(freq: float, duration: float,
                sr: int, volume: float) -> np.ndarray:
    """
    Gera uma única amostra de click: onda senoidal com envelope ADSR simples.

    O envelope aplica fade-out rápido para evitar o "clique" de artefato
    causado por corte abrupto na onda.

    Args:
        freq:     Frequência do tom em Hz.
        duration: Duração em segundos.
        sr:       Taxa de amostragem.
        volume:   Amplitude máxima (0.0–1.0).

    Returns:
        Array numpy com as amostras do click.
    """

    n_samples = int(duration * sr)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    # Onda senoidal pura
    wave = np.sin(2 * np.pi * freq * t)

    # Envelope exponencial: começa forte, decai rapidamente
    # Simula o som de uma baqueta ou woodblock
    envelope = np.exp(-t / (duration * 0.3))

    return (wave * envelope * volume).astype(np.float32)
