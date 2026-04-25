"""
core/exporter.py — Organização e exportação final dos arquivos
==============================================================
Copia todos os stems, click track e voz guia para uma pasta
de saída organizada, pronta para arrastar na DAW.

Estrutura de saída:
  output/<nome_da_musica>/
    ├── 00_GUIDE_VOICE.wav       ← voz guia (anúncios de seção)
    ├── 01_CLICK_113bpm.wav      ← metrônomo sincronizado
    ├── 02_Voz.wav
    ├── 03_Bateria.wav
    ├── 04_Baixo.wav
    ├── 05_Piano.wav
    ├── 06_Guitarra.wav
    ├── 07_Outros.wav
    └── INFO.txt                 ← BPM, tom, seções detectadas

Dependências: shutil (stdlib), soundfile
"""

import shutil
import json
from datetime import datetime
from pathlib import Path

import soundfile as sf

from .utils import OUTPUT_DIR, STEM_LABELS


def export_all(audio_path,
               stems: dict,
               click_path,
               guide_path,
               track_info: dict) -> Path:
    """
    Organiza todos os arquivos gerados em uma pasta de saída limpa.

    Args:
        audio_path:  Path do áudio original.
        stems:       Dict {stem_key: Path} retornado pelo separator.
        click_path:  Path do WAV do click track.
        guide_path:  Path do WAV da voz guia.
        track_info:  Dict com bpm, key, sections, duration.

    Returns:
        Path da pasta de saída criada.
    """

    # ── Nome da pasta de saída baseado no nome da música ─────────────────────
    song_name  = audio_path.stem
    output_dir = OUTPUT_DIR / song_name
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  ↳ Exportando para: {output_dir}")

    # ── 1. Voz guia (sempre primeiro — é o que o músico ouvirá primeiro) ──────
    if guide_path and Path(guide_path).exists():
        dest = output_dir / "00_VOZ_GUIA.wav"
        shutil.copy2(guide_path, dest)
        print(f"  ↳ Exportado: {dest.name}")

    # ── 2. Click track ────────────────────────────────────────────────────────
    if click_path and Path(click_path).exists():
        bpm_str = f"{int(round(track_info['bpm']))}bpm"
        dest    = output_dir / f"01_CLICK_{bpm_str}.wav"
        shutil.copy2(click_path, dest)
        print(f"  ↳ Exportado: {dest.name}")

    # ── 3. Stems instrumentais ────────────────────────────────────────────────
    # Ordem fixa para facilitar o carregamento na DAW
    stem_order = ["lead_vocals", "backing_vocals", "vocals", "drums", "bass", "guitar", "piano", "other"]

    for idx, key in enumerate(stem_order, start=2):
        if key not in stems:
            continue
        src = Path(stems[key])
        if not src.exists():
            continue

        # Nome legível em português
        label = STEM_LABELS.get(key, key.capitalize())
        dest  = output_dir / f"0{idx}_{label}.wav"

        shutil.copy2(src, dest)
        print(f"  ↳ Exportado: {dest.name}")

    # ── 4. Arquivo de informações ─────────────────────────────────────────────
    _write_info_file(output_dir, track_info, song_name)

    return output_dir


def _write_info_file(output_dir: Path,
                     track_info: dict,
                     song_name: str) -> None:
    """
    Gera um arquivo INFO.txt com todas as informações da análise.
    Útil para referência rápida na DAW.
    """

    lines = [
        "=" * 50,
        "  StemSplit VS — Informações da Música",
        "=" * 50,
        f"  Música   : {song_name}",
        f"  BPM      : {track_info['bpm']:.1f}",
        f"  Tom      : {track_info['key']}",
        f"  Duração  : {_format_duration(track_info['duration'])}",
        f"  Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "─" * 50,
        "  Estrutura detectada:",
        "─" * 50,
    ]

    for sec in track_info.get("sections", []):
        start = _format_duration(sec["start"])
        end   = _format_duration(sec["end"])
        lines.append(f"  {sec['label']:<15} {start} → {end}")

    lines += [
        "",
        "─" * 50,
        "  Como usar na DAW:",
        "─" * 50,
        "  1. Abra um projeto novo no Ableton / Pro Tools / Reaper",
        f"  2. Configure o BPM para {track_info['bpm']:.1f}",
        "  3. Arraste todos os WAVs desta pasta para trilhas separadas",
        "  4. A faixa VOZ_GUIA fica no monitor do músico (IEM)",
        "  5. O CLICK vai junto com a voz guia no IEM",
        "  6. Os stems vão para a mesa de som normalmente",
        "=" * 50,
    ]

    info_path = output_dir / "INFO.txt"
    info_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ↳ Exportado: {info_path.name}")


def _format_duration(seconds: float) -> str:
    """Converte segundos para formato mm:ss."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"
