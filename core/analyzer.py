"""
core/analyzer.py — Análise musical: BPM, tom e seções
=======================================================
Usa librosa para detectar:
  - BPM (beats per minute) com precisão de tempo
  - Tom da música (ex: Lá maior, Ré menor)
  - Estrutura: intro, verso, refrão, ponte, final

Dependências: librosa, numpy
"""

import numpy as np
import librosa

from .utils import TEMP_DIR


# ── Nomes das notas em português ─────────────────────────────────────────────
NOTE_NAMES_PT = ["Dó", "Dó#", "Ré", "Ré#", "Mi", "Fá",
                 "Fá#", "Sol", "Sol#", "Lá", "Lá#", "Si"]


def analyze_track(audio_path) -> dict:
    """
    Analisa um arquivo de áudio e retorna suas características musicais.

    Args:
        audio_path: Path para o arquivo WAV.

    Returns:
        Dicionário com:
            - bpm (float): Batidas por minuto
            - key (str): Tom detectado em português (ex: "Lá maior")
            - beat_times (np.ndarray): Timestamps de cada batida em segundos
            - sections (list[dict]): Lista de seções com label e timestamps
            - duration (float): Duração total em segundos
    """

    # ── Carrega o áudio com librosa ───────────────────────────────────────────
    # sr=None preserva a taxa original; mono=True facilita a análise
    print("  ↳ Carregando áudio para análise...")
    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    # ── Detecção de BPM e beats ───────────────────────────────────────────────
    print("  ↳ Detectando BPM e batidas...")
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    bpm = float(np.atleast_1d(tempo)[0])

    # Converte frames para segundos (útil para posicionar click e voz guia)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    # ── Detecção de tom ───────────────────────────────────────────────────────
    print("  ↳ Detectando tom...")
    key_label = _detect_key(y, sr)

    # ── Detecção de seções ────────────────────────────────────────────────────
    print("  ↳ Detectando estrutura da música (intro, verso, refrão...)...")
    sections = _detect_sections(y, sr, duration, bpm)

    return {
        "bpm":        bpm,
        "key":        key_label,
        "beat_times": beat_times,
        "sections":   sections,
        "duration":   duration,
        "sr":         sr,
    }


def _detect_key(y: np.ndarray, sr: int) -> str:
    """
    Detecta o tom da música usando o perfil de Krumhansl-Schmuckler
    via chroma features do librosa.

    Returns:
        String como "Lá maior" ou "Ré menor".
    """

    # Chroma CQT: representa a energia de cada nota (Dó, Dó#, ... Si)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)  # média por nota ao longo do tempo

    # Perfis de Krumhansl para maior e menor
    # (distribuição esperada de cada nota num dado modo)
    major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                               2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                               2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

    # Testa todas as 12 tonalidades maiores e 12 menores
    best_score = -np.inf
    best_key = "Dó maior"

    for root in range(12):
        # Rotaciona os perfis para testar cada tonalidade
        maj = np.roll(major_profile, root)
        mn  = np.roll(minor_profile, root)

        # Correlação de Pearson: quanto o áudio se parece com cada perfil
        score_maj = np.corrcoef(chroma_mean, maj)[0, 1]
        score_mn  = np.corrcoef(chroma_mean, mn)[0, 1]

        if score_maj > best_score:
            best_score = score_maj
            best_key   = f"{NOTE_NAMES_PT[root]} maior"

        if score_mn > best_score:
            best_score = score_mn
            best_key   = f"{NOTE_NAMES_PT[root]} menor"

    return best_key


def _detect_sections(y: np.ndarray, sr: int,
                     duration: float, bpm: float) -> list[dict]:
    """
    Detecta seções estruturais da música usando análise de recorrência
    (Recurrence Matrix via librosa).

    Estratégia:
      1. Extrai MFCCs (timbre) e chroma (harmonia)
      2. Combina em uma feature composta
      3. Usa segmentação espectral para encontrar fronteiras
      4. Classifica as seções por posição e similaridade

    Returns:
        Lista de dicts: [{"label": "Intro", "start": 0.0, "end": 14.3}, ...]
    """

    # ── Feature composta: MFCCs + Chroma ─────────────────────────────────────
    mfcc   = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

    # Normaliza e empilha as features
    mfcc_n   = librosa.util.normalize(mfcc,   axis=1)
    chroma_n = librosa.util.normalize(chroma, axis=1)
    features = np.vstack([mfcc_n, chroma_n])

    # ── Segmentação via Laplacian spectral ────────────────────────────────────
    # k = número de segmentos estimado (aprox. 1 seção a cada 30s)
    n_segments = max(4, int(duration / 30))

    try:
        boundaries, _ = librosa.segment.agglomerative(features, k=n_segments)
        boundary_times = librosa.frames_to_time(boundaries, sr=sr)
    except Exception:
        # Fallback: divide a música em partes iguais
        boundary_times = np.linspace(0, duration, n_segments + 1)

    # Garante que começa em 0 e termina na duração total
    boundary_times = np.unique(np.concatenate([[0.0], boundary_times, [duration]]))

    # ── Rotula cada seção pela posição relativa na música ─────────────────────
    sections = _label_sections(boundary_times, duration)

    return sections


def _label_sections(boundaries: np.ndarray, duration: float) -> list[dict]:
    """
    Atribui labels semânticos (Intro, Versão, Refrão, Ponte, Final)
    com base na posição relativa de cada seção na música.

    Lógica heurística baseada em estruturas musicais típicas pop/rock:
      - Início (0–15%): Intro
      - Final (85–100%): Final / Outro
      - Seções pares no meio: tendência de Refrão
      - Seções ímpares no meio: tendência de Versão
    """

    sections = []
    n = len(boundaries) - 1  # número de seções

    # Contadores para nomear seções repetidas
    verse_count   = 0
    chorus_count  = 0
    bridge_done   = False

    for i in range(n):
        start = float(boundaries[i])
        end   = float(boundaries[i + 1])
        pos   = start / duration  # posição relativa (0.0 a 1.0)

        # ── Classifica por posição ────────────────────────────────────────────
        if i == 0:
            label = "Intro"

        elif pos >= 0.85 or i == n - 1:
            label = "Final"

        elif pos >= 0.60 and not bridge_done and n >= 6:
            # Ponte aparece tipicamente nos últimos 40% (mas antes do final)
            bridge_done = True
            label = "Ponte"

        elif i % 2 == 1:
            # Seções ímpares → Verso
            verse_count += 1
            label = f"Versão {verse_count}"

        else:
            # Seções pares → Refrão
            chorus_count += 1
            label = f"Refrão {chorus_count}" if chorus_count > 1 else "Refrão"

        sections.append({
            "label": label,
            "start": round(start, 3),
            "end":   round(end,   3),
        })

    return sections
