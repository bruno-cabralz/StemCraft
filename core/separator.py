"""
core/separator.py — Separação de stems com Demucs
===================================================
Usa o modelo htdemucs_6s do Facebook/Meta para separar:
  vocals, drums, bass, piano, guitar, other

O processamento roda localmente (sem internet após instalação).
Com GPU (CUDA) é ~10x mais rápido. Sem GPU usa CPU normalmente.

Dependências: demucs (pip install demucs)
"""

import sys
import logging
import subprocess
import shutil
from pathlib import Path

from .utils import TEMP_DIR, OUTPUT_DIR


# Modelo padrão (usado quando nenhum é especificado)
DEFAULT_MODEL = "htdemucs_ft"

# Stems possíveis por modelo
STEMS_6 = {"vocals", "drums", "bass", "piano", "guitar", "other"}

# Mapeamento dos nomes internos do Demucs → nomes legíveis em pt-BR
STEM_LABELS = {
    "vocals": "Voz",
    "drums":  "Bateria",
    "bass":   "Baixo",
    "piano":  "Piano",
    "guitar": "Guitarra",
    "other":  "Outros",
}


def separate_stems(audio_path, model: str = None) -> dict:
    """
    Roda o Demucs para separar os instrumentos em faixas individuais.

    Args:
        audio_path: Path para o arquivo WAV original.
        model:      Nome do modelo Demucs (ex: 'htdemucs_ft', 'mdx_extra_q').
                    Usa DEFAULT_MODEL se None.

    Returns:
        Dicionário mapeando nome do stem → Path do arquivo WAV gerado.

    Raises:
        RuntimeError: Se o Demucs retornar erro.
        FileNotFoundError: Se os arquivos de saída não forem encontrados.
    """

    demucs_model = model or DEFAULT_MODEL
    demucs_out = TEMP_DIR / "demucs"
    demucs_out.mkdir(parents=True, exist_ok=True)

    # ── Monta o comando Demucs ────────────────────────────────────────────────
    # -n: modelo a usar
    # --out: pasta de saída
    # --mp3: desabilitado (queremos WAV)
    # --two-stems: desabilitado (queremos todos os stems)
    # Detecta se CUDA está disponível e usa GPU automaticamente
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    device_label = f"GPU ({torch.cuda.get_device_name(0)})" if device == "cuda" else "CPU"

    cmd = [
        sys.executable, "-m", "demucs",
        "-n",       demucs_model,
        "-d",       device,
        "--out",    str(demucs_out),
        str(audio_path),
    ]

    print(f"  → Rodando Demucs ({demucs_model}) em {device_label}... aguarde.")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"Demucs falhou na separação.\n"
            f"Stderr: {result.stderr[-2000:]}"  # últimos 2000 chars do erro
        )

    # ── Localiza os arquivos gerados ──────────────────────────────────────────
    # Demucs salva em: <out>/<modelo>/<nome_do_arquivo>/<stem>.wav
    song_name = audio_path.stem
    stems_dir = demucs_out / demucs_model / song_name

    if not stems_dir.exists():
        raise FileNotFoundError(
            f"Pasta de stems não encontrada: {stems_dir}\n"
            f"Verifique se o Demucs está instalado corretamente."
        )

    # ── Coleta e renomeia os stems ────────────────────────────────────────────
    stems = {}
    for stem_key, label in STEM_LABELS.items():
        src = stems_dir / f"{stem_key}.wav"
        if src.exists():
            stems[stem_key] = src
            print(f"  ↳ Stem encontrado: {label} ({src.name})")
        else:
            print(f"  ⚠ Stem não gerado: {stem_key} (modelo pode não suportá-lo)")

    if not stems:
        raise FileNotFoundError("Nenhum stem foi gerado pelo Demucs.")

    return stems


def separate_vocals_layers(vocals_path: Path) -> tuple:
    """
    Separa a faixa de vocais em voz principal (lead) e backing vocal.

    Usa o modelo UVR-BVE-4B_SN-44100-1 (Backing Vocal Extractor) via audio-separator.

    Args:
        vocals_path: Path para o WAV de vocais gerado pelo Demucs.

    Returns:
        (lead_path, backing_path) — backing_path pode ser None se falhar.
    """
    try:
        from audio_separator.separator import Separator

        out_dir = TEMP_DIR / "vocals_layers"
        out_dir.mkdir(parents=True, exist_ok=True)

        print("  → Separando camadas vocais (BVE)... aguarde.")
        sep = Separator(output_dir=str(out_dir), log_level=logging.WARNING)
        sep.load_model("UVR-BVE-4B_SN-44100-1")
        outputs = sep.separate(str(vocals_path))

        # audio-separator retorna lista de caminhos dos arquivos gerados
        out_paths = [Path(f) for f in outputs]

        if len(out_paths) >= 2:
            lead_path    = out_paths[0]
            backing_path = out_paths[1]
            print(f"  ↳ Voz principal : {lead_path.name}")
            print(f"  ↳ Backing vocal : {backing_path.name}")
            return lead_path, backing_path

        elif len(out_paths) == 1:
            print(f"  ↳ Apenas um stem gerado: {out_paths[0].name}")
            return out_paths[0], None

        else:
            print("  ⚠ Nenhum stem gerado pelo BVE; mantendo vocal combinado.")
            return vocals_path, None

    except Exception as exc:
        print(f"  ⚠ Separação de camadas vocais falhou: {exc}")
        return vocals_path, None


def extract_guitar_piano(other_path: Path) -> dict:
    """
    Extrai guitarra e piano do stem 'other' usando htdemucs_6s (2ª passagem).

    Usado quando o modelo principal é de 4 stems e não gera guitar/piano.
    Só os stems guitar, piano e other são aproveitados; os demais são descartados
    pois o áudio de entrada já não contém voz/bateria/baixo.

    Args:
        other_path: Path do WAV 'other' gerado pelo Demucs na 1ª passagem.

    Returns:
        Dict com as chaves 'guitar', 'piano' e/ou 'other' que foram encontradas.
        Retorna {} se falhar (o caller mantém o 'other' original).
    """
    try:
        import torch

        demucs_out = TEMP_DIR / "demucs_extras"
        demucs_out.mkdir(parents=True, exist_ok=True)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        device_label = f"GPU ({torch.cuda.get_device_name(0)})" if device == "cuda" else "CPU"

        cmd = [
            sys.executable, "-m", "demucs",
            "-n",    "htdemucs_6s",
            "-d",    device,
            "--out", str(demucs_out),
            str(other_path),
        ]

        print(f"  → 2ª passagem htdemucs_6s em {device_label} para extrair guitarra/teclado...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"  ⚠ 2ª passagem falhou: {result.stderr[-500:]}")
            return {}

        stems_dir = demucs_out / "htdemucs_6s" / other_path.stem
        extras = {}
        for key in ("guitar", "piano", "other"):
            src = stems_dir / f"{key}.wav"
            if src.exists():
                extras[key] = src
                label = {"guitar": "Guitarra", "piano": "Piano/Teclado", "other": "Outros"}[key]
                print(f"  ↳ Extraído: {label} ({src.name})")

        return extras

    except Exception as exc:
        print(f"  ⚠ Extração de guitarra/piano falhou: {exc}")
        return {}
