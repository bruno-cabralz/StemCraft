"""
core/downloader.py — Download de áudio do YouTube
===================================================
Usa yt-dlp para baixar o áudio em máxima qualidade
e converte para WAV 44.1kHz estéreo usando ffmpeg.

Dependências: yt-dlp, ffmpeg (instalado no sistema)
"""

import re
import sys
import subprocess
from pathlib import Path

from .utils import TEMP_DIR, sanitize_filename


def download_audio(url: str) -> Path:
    """
    Baixa o áudio de uma URL do YouTube e salva como WAV.

    Args:
        url: Link completo do YouTube (ex: https://youtube.com/watch?v=...)

    Returns:
        Path para o arquivo WAV baixado.

    Raises:
        RuntimeError: Se o download ou a conversão falhar.
    """

    # ── Cria a pasta temporária se não existir ────────────────────────────────
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    # ── Descobre o título da música antes de baixar ───────────────────────────
    title = _get_video_title(url)
    safe_title = sanitize_filename(title)
    output_path = TEMP_DIR / f"{safe_title}.wav"

    # Se já foi baixado antes, reutiliza (evita baixar duas vezes)
    if output_path.exists():
        print(f"  ↩ Arquivo já existe, reutilizando: {output_path.name}")
        return output_path

    # ── Monta o comando yt-dlp ────────────────────────────────────────────────
    # -x              → extrai apenas o áudio
    # --audio-format  → formato intermediário (melhor qualidade)
    # --audio-quality → 0 = melhor qualidade disponível
    # -o              → caminho de saída com template
    temp_audio = TEMP_DIR / f"{safe_title}.%(ext)s"

    cmd_download = [
        sys.executable, "-m", "yt_dlp",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--no-playlist",          # ignora playlist, baixa só o vídeo
        "--output", str(temp_audio),
        url,
    ]

    result = subprocess.run(cmd_download, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp falhou ao baixar o áudio.\n"
            f"Erro: {result.stderr}"
        )

    # ── Localiza o arquivo baixado ────────────────────────────────────────────
    # yt-dlp pode gerar .wav diretamente ou precisar de conversão
    downloaded = _find_downloaded_file(TEMP_DIR, safe_title)
    if downloaded is None:
        raise RuntimeError("Arquivo baixado não encontrado após o download.")

    # ── Converte para WAV 44100Hz estéreo (padrão DAW) ───────────────────────
    if downloaded.suffix.lower() != ".wav":
        output_path = _convert_to_wav(downloaded, output_path)
        downloaded.unlink()  # remove o arquivo intermediário
    else:
        downloaded.rename(output_path)

    return output_path


def _get_video_title(url: str) -> str:
    """
    Usa yt-dlp para obter apenas o título do vídeo sem baixar.

    Returns:
        Título do vídeo como string, ou 'audio' em caso de falha.
    """
    cmd = [sys.executable, "-m", "yt_dlp", "--get-title", "--no-playlist", url]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "audio"


def _find_downloaded_file(directory: Path, name_stem: str) -> Path | None:
    """
    Procura o arquivo baixado pelo yt-dlp dentro de um diretório.
    yt-dlp pode salvar com extensão diferente dependendo da disponibilidade.
    """
    for ext in ("wav", "mp3", "m4a", "opus", "webm", "ogg"):
        candidate = directory / f"{name_stem}.{ext}"
        if candidate.exists():
            return candidate
    return None


def _convert_to_wav(input_path: Path, output_path: Path) -> Path:
    """
    Converte qualquer áudio para WAV 44100Hz estéreo usando ffmpeg.
    Esse formato é universalmente aceito por DAWs.
    """
    cmd = [
        "ffmpeg",
        "-i", str(input_path),
        "-ar", "44100",      # sample rate: 44100 Hz (padrão CD/DAW)
        "-ac", "2",          # canais: 2 (estéreo)
        "-sample_fmt", "s16", # 16-bit (compatível com tudo)
        "-y",                # sobrescreve se já existir
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg falhou na conversão para WAV.\n"
            f"Erro: {result.stderr}"
        )
    return output_path
