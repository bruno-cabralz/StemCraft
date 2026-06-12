"""
prepare_dataset.py — Preparação do dataset para treino do Demucs
================================================================
Lê a estrutura do Google Drive:
  Drive/
    ARTISTA/
      musica.rar   ← stems individuais compactados

E gera:
  dataset/
    train/  (90%)
    valid/  (10%)
      musica_001/
        mixture.wav      ← soma de todos os stems
        vocals.wav
        guitar.wav
        ...

Também gera um relatório de frequência dos instrumentos para
ajudar a definir as classes do modelo.

Uso:
  python prepare_dataset.py --drive "C:/caminho/para/drive" --out dataset/
  python prepare_dataset.py --drive "C:/caminho/para/drive" --out dataset/ --analyze-only
"""

import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf

# ── Mapeamento de nomes comuns → classe canônica ──────────────────────────────
# Adicione mais variações conforme encontrar nos seus arquivos
STEM_MAP = {
    # Vozes
    "voz":           "vocals",
    "voz1":          "vocals",
    "vocal":         "vocals",
    "vocals":        "vocals",
    "lead":          "vocals",
    "lead vocal":    "vocals",
    "lead_vocal":    "vocals",
    "voz principal": "vocals",
    "voz_principal": "vocals",

    "voz2":          "backing_vocals",
    "bg":            "backing_vocals",
    "bgvs":          "backing_vocals",
    "bgvs 2":        "backing_vocals",
    "back":          "backing_vocals",
    "backing":       "backing_vocals",
    "backing vocal": "backing_vocals",
    "coro":          "backing_vocals",
    "vozes":         "backing_vocals",
    "choir":         "backing_vocals",
    "tenor":         "backing_vocals",
    "alto":          "backing_vocals",
    "soprano":       "backing_vocals",
    "oohs":          "backing_vocals",
    "vox fx":        "backing_vocals",
    "vox chop":      "backing_vocals",

    # Bateria / Percussão
    "bateria":     "drums",
    "drums":       "drums",
    "drum":        "drums",
    "batt":        "drums",
    "perc":        "drums",
    "percussao":   "drums",
    "percussão":   "drums",
    "shaker":      "drums",
    "clap":        "drums",
    "kick":        "drums",
    "bumbo":       "drums",
    "kit":         "drums",
    "tambourine":  "drums",

    # Baixo
    "baixo":  "bass",
    "bass":   "bass",

    # Teclado / Piano  →  "piano" é o nome que o htdemucs_6s usa como stem
    "teclado":  "piano",
    "keys":     "piano",
    "piano":    "piano",
    "pad":      "piano",
    "synth":    "piano",
    "synt":     "piano",
    "orgao":    "piano",
    "organ":    "piano",
    "órgão":    "piano",
    "strings":  "piano",
    "string":   "piano",
    "rhodes":   "piano",
    "bells":    "piano",
    "bell":     "piano",
    "cello":    "piano",
    "violino":  "piano",
    "violinos": "piano",

    # Guitarra elétrica
    "guitarra":       "guitar",
    "guitar":         "guitar",
    "gt":             "guitar",
    "guitarra eletrica": "guitar",

    # Violão / Instrumentos acústicos de cordas
    "violao":     "violao",
    "violão":     "violao",
    "acoustic":   "violao",
    "banjo":      "violao",
    "bandolin":   "violao",
    "mandolin":   "violao",
    "cavaquinho": "violao",
    "ukulele":    "violao",

    # Sopros
    "gaita":     "sopros",
    "sax":       "sopros",
    "saxofone":  "sopros",
    "trompete":  "sopros",
    "trombone":  "sopros",
    "flauta":    "sopros",
    "sopros":    "sopros",
    "brass":     "sopros",
    "horns":     "sopros",
    "metais":    "sopros",

    # ── Nomes exatos encontrados no dataset gospel ────────────────────────
    # Violão acústico
    "ag":            "violao",   # Acoustic Guitar
    "acoustic guitar": "violao",

    # Guitarras elétricas numeradas (EG 1, EG 2, EG 3 …)
    "eg":            "guitar",   # Electric Guitar
    "eg 1":          "guitar",
    "eg 2":          "guitar",
    "eg 3":          "guitar",
    "eg 4":          "guitar",
    "eg 5":          "guitar",
    "electric guitar": "guitar",

    # Bateria com sufixo "(live)"
    "drums (live)":  "drums",
    "drum (live)":   "drums",
    "bateria (live)": "drums",
}

# ── Stems a ignorar (click track, guide vocal, waveform peaks) ────────────────
# Qualquer arquivo cujo nome contenha uma dessas palavras será descartado.
SKIP_STEMS: frozenset[str] = frozenset({
    # Click / metrônomo
    "click",
    "click track",
    "clicktrack",
    "metronome",
    "metronomo",
    "metrônomo",
    # Guia de voz (pista de referência para o cantor)
    "guide",
    "guide vocal",
    "guide_vocal",
    "guia",
    "voz guia",
    "voz_guia",
    # Arquivos de pico de forma de onda (não são áudio real)
    "peaks",
    # Mix completo (não é um stem separado)
    "master",
    "full mix",
    "mix",
    "cues",
})

# Extensões de áudio aceitas
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".aiff", ".aif", ".ogg", ".m4a", ".wma"}


def read_audio_file(path: Path) -> tuple:
    """
    Le um arquivo de audio e retorna (data_numpy, samplerate).
    Tenta soundfile primeiro; se falhar, usa pydub+ffmpeg como fallback
    (suporta .m4a, .wma, .aac, etc).
    """
    try:
        data, sr = sf.read(str(path), always_2d=True)
        return data, sr
    except Exception:
        pass

    # Fallback: pydub converte via ffmpeg para WAV em memoria
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(str(path))
        sr = audio.frame_rate
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        # Normaliza para [-1, 1]
        samples = samples / (2 ** (audio.sample_width * 8 - 1))
        # Reshape para (frames, channels)
        if audio.channels > 1:
            samples = samples.reshape(-1, audio.channels)
        else:
            samples = samples.reshape(-1, 1)
        return samples, sr
    except Exception as exc:
        raise RuntimeError(f"soundfile e pydub falharam: {exc}") from exc

# ── Normalização de nome de stem ──────────────────────────────────────────────
def normalize_stem_name(filename: str) -> str | None:
    """
    Converte nome de arquivo → chave canônica usando STEM_MAP.
    Retorna None se o arquivo deve ser ignorado (click track, guide, etc).
    """
    name = Path(filename).stem.lower().strip()

    # Ignora resource forks do macOS (._filename)
    if name.startswith("._"):
        return None

    # Verifica se deve ser ignorado antes de normalizar
    if name in SKIP_STEMS:
        return None
    # Verifica por palavras-chave de skip
    for skip in SKIP_STEMS:
        if skip in name:
            return None

    # Remove números no início/fim: "01_voz" → "voz"
    name_clean = re.sub(r"^[\d_\-\s]+|[\d_\-\s]+$", "", name)
    name_clean = name_clean.replace("_", " ").replace("-", " ").strip()

    if name_clean in STEM_MAP:
        return STEM_MAP[name_clean]
    if name in STEM_MAP:
        return STEM_MAP[name]

    # Tenta correspondência parcial
    for key, canon in STEM_MAP.items():
        if name_clean.startswith(key) or key in name_clean:
            return canon

    return "other"


# ── Extração de RAR ───────────────────────────────────────────────────────────

def _find_7zip() -> str | None:
    """Retorna o caminho do executavel 7z se disponivel."""
    import shutil as _shutil
    found = _shutil.which("7z") or _shutil.which("7za")
    if found:
        return found
    # Caminhos padrão de instalação no Windows
    for candidate in [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ]:
        if Path(candidate).exists():
            return candidate
    return None


def extract_archive(archive_path: Path, dest_dir: Path) -> list[Path]:
    """
    Extrai .zip, .rar ou .7z para dest_dir.
    - .zip: usa zipfile da stdlib (sem dependências extras)
    - .rar: usa rarfile (pip install rarfile)
    - .7z : usa py7zr  (pip install py7zr)
    Retorna lista de arquivos de áudio extraídos.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = archive_path.suffix.lower()

    try:
        if ext == ".zip":
            import zipfile
            with zipfile.ZipFile(str(archive_path)) as zf:
                zf.extractall(str(dest_dir))

        elif ext == ".rar":
            extracted = False
            # Tenta rarfile primeiro
            try:
                import rarfile
                with rarfile.RarFile(str(archive_path)) as rf:
                    rf.extractall(str(dest_dir))
                extracted = True
            except ImportError:
                pass
            except Exception:
                pass
            # Fallback: 7-Zip (suporta RAR5)
            if not extracted:
                seven_zip = _find_7zip()
                if seven_zip:
                    result = subprocess.run(
                        [seven_zip, "x", str(archive_path), f"-o{dest_dir}", "-y"],
                        capture_output=True,
                    )
                    if result.returncode != 0:
                        raise RuntimeError(result.stderr.decode(errors="replace").strip())
                else:
                    raise RuntimeError("rarfile falhou e 7-Zip nao encontrado. Instale: winget install 7zip.7zip")

        elif ext == ".7z":
            try:
                import py7zr
                with py7zr.SevenZipFile(str(archive_path), mode="r") as sz:
                    sz.extractall(path=str(dest_dir))
            except ImportError:
                print(f"  [ERRO] Instale py7zr para extrair .7z:  pip install py7zr")
                return []

        else:
            print(f"  [ERRO] Formato nao suportado: {ext}")
            return []

    except Exception as exc:
        print(f"  [ERRO] Erro ao extrair {archive_path.name}: {exc}")
        return []

    # Extrai arquivos aninhados (.rar contendo .zip, etc.)
    for nested in list(dest_dir.rglob("*")):
        if nested.suffix.lower() in {".zip", ".rar", ".7z"}:
            nested_audio = extract_archive(nested, nested.parent / nested.stem)
            if nested_audio:
                nested.unlink(missing_ok=True)

    return [f for f in dest_dir.rglob("*") if f.suffix.lower() in AUDIO_EXTS]


# ── Geração da mixtura ────────────────────────────────────────────────────────
def mix_stems(stem_paths: list[Path], out_path: Path) -> bool:
    """Soma todos os stems para gerar mixture.wav. Normaliza se necessário."""
    try:
        arrays = []
        sr = None
        for p in stem_paths:
            data, file_sr = read_audio_file(p)
            if sr is None:
                sr = file_sr
            elif file_sr != sr:
                print(f"  [AVISO] Sample rate diferente em {p.name}: {file_sr} vs {sr}")
                continue
            arrays.append(data)

        if not arrays:
            return False

        # Alinha tamanhos (trim ao menor)
        min_len = min(a.shape[0] for a in arrays)
        mixture = sum(a[:min_len] for a in arrays)

        # Normaliza para evitar clipping
        peak = np.max(np.abs(mixture))
        if peak > 0.99:
            mixture = mixture / peak * 0.98

        sf.write(str(out_path), mixture, sr)
        return True

    except Exception as exc:
        print(f"  [ERRO] Erro ao gerar mixture: {exc}")
        return False


# ── Análise do Drive (sem extrair) ───────────────────────────────────────────
def analyze_drive(drive_root: Path) -> dict:
    """Varre o Drive e coleta estatísticas sem extrair ou mover nada."""
    stats = {
        "total_artistas": 0,
        "total_musicas":  0,
        "formatos":       Counter(),
        "stem_frequency": Counter(),
        "musicas_por_artista": {},
        "exemplos_stems": defaultdict(list),
    }

    artista_dirs = sorted([d for d in drive_root.iterdir() if d.is_dir()])
    stats["total_artistas"] = len(artista_dirs)

    for artista_dir in artista_dirs:
        arquivos_comprimidos = list(artista_dir.glob("*.rar")) + \
                               list(artista_dir.glob("*.zip")) + \
                               list(artista_dir.glob("*.7z"))
        stats["musicas_por_artista"][artista_dir.name] = len(arquivos_comprimidos)
        stats["total_musicas"] += len(arquivos_comprimidos)
        for f in arquivos_comprimidos:
            stats["formatos"][f.suffix.lower()] += 1

    return stats


# ── Pipeline principal ────────────────────────────────────────────────────────
def prepare(drive_root: Path, out_root: Path, seed: int = 42, valid_ratio: float = 0.1):
    """Extrai, normaliza, gera mixtures e organiza o dataset."""
    random.seed(seed)

    tmp_dir  = out_root / "_extracted"
    train_dir = out_root / "train"
    valid_dir = out_root / "valid"

    artista_dirs = sorted([d for d in drive_root.iterdir() if d.is_dir()])
    all_musicas = []  # lista de (artista, rar_path)

    for artista_dir in artista_dirs:
        for arq in sorted(artista_dir.glob("*.rar")):
            all_musicas.append((artista_dir.name, arq))
        for arq in sorted(artista_dir.glob("*.zip")):
            all_musicas.append((artista_dir.name, arq))
        for arq in sorted(artista_dir.glob("*.7z")):
            all_musicas.append((artista_dir.name, arq))

    random.shuffle(all_musicas)
    split_idx  = max(1, int(len(all_musicas) * valid_ratio))
    valid_set  = set(r.stem for _, r in all_musicas[:split_idx])

    stem_frequency = Counter()
    ok_count = 0
    skip_count = 0

    for artista, rar_path in all_musicas:
        musica_id = f"{artista}_{rar_path.stem}".replace(" ", "_")
        split     = "valid" if rar_path.stem in valid_set else "train"
        dest_song = (valid_dir if split == "valid" else train_dir) / musica_id

        if dest_song.exists():
            print(f"  >> Pulando (ja processada): {musica_id}")
            ok_count += 1
            continue

        print(f"\n[{split}] {artista} / {rar_path.name}")

        # Extrai
        tmp_song = tmp_dir / musica_id
        audio_files = extract_archive(rar_path, tmp_song)
        if not audio_files:
            skip_count += 1
            shutil.rmtree(tmp_song, ignore_errors=True)
            continue

        # Normaliza nomes dos stems
        dest_song.mkdir(parents=True, exist_ok=True)
        stem_paths = []
        seen_classes = Counter()

        for af in audio_files:
            stem_class = normalize_stem_name(af.name)

            # Ignora click track, guide e similares
            if stem_class is None:
                print(f"  [SKIP] Ignorado (nao e stem musical): {af.name}")
                continue

            seen_classes[stem_class] += 1
            # Se houver duplicatas de mesma classe, adiciona sufixo
            suffix = f"_{seen_classes[stem_class]}" if seen_classes[stem_class] > 1 else ""
            out_fname = f"{stem_class}{suffix}.wav"
            out_path  = dest_song / out_fname

            # Converte para WAV 44100 Hz mono/stereo preservado
            try:
                data, sr = read_audio_file(af)
                sf.write(str(out_path), data, sr)
                stem_paths.append(out_path)
                stem_frequency[stem_class] += 1
                print(f"     {af.name}  ->  {out_fname}")
            except Exception as exc:
                print(f"  [ERRO] Nao foi possivel converter {af.name}: {exc}")

        # Gera mixture.wav
        if stem_paths:
            mix_path = dest_song / "mixture.wav"
            if mix_stems(stem_paths, mix_path):
                print(f"  [OK] mixture.wav gerada")
                ok_count += 1
            else:
                shutil.rmtree(dest_song, ignore_errors=True)
                skip_count += 1
        else:
            shutil.rmtree(dest_song, ignore_errors=True)
            skip_count += 1

        shutil.rmtree(tmp_song, ignore_errors=True)

    # Relatório final
    print("\n" + "=" * 60)
    print("  RELATÓRIO DO DATASET")
    print("=" * 60)
    print(f"  Músicas processadas : {ok_count}")
    print(f"  Músicas com erro    : {skip_count}")
    print(f"  Train               : {len(list(train_dir.iterdir())) if train_dir.exists() else 0}")
    print(f"  Valid               : {len(list(valid_dir.iterdir())) if valid_dir.exists() else 0}")
    print()
    print("  Frequência de stems:")
    print("  " + "-" * 40)
    for stem, count in stem_frequency.most_common():
        bar  = "#" * (count * 30 // max(stem_frequency.values()))
        flag = "  <- classe propria recomendada" if count >= 40 else ("  <- agrupar em 'other'" if count < 15 else "")
        print(f"  {stem:<18} {count:>4}  {bar}{flag}")

    # Salva relatório em JSON
    report_path = out_root / "dataset_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_ok":       ok_count,
            "total_erro":     skip_count,
            "stem_frequency": dict(stem_frequency.most_common()),
        }, f, ensure_ascii=False, indent=2)
    print(f"\n  Relatório salvo em: {report_path}")

    # Sugere configuração para o Demucs
    classes = [s for s, c in stem_frequency.items() if c >= 40]
    print("\n  Sugestão de classes para o Demucs:")
    print(f"  --sources {' '.join(classes)} other")


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Prepara dataset de multitracks para treino do Demucs"
    )
    parser.add_argument(
        "--drive", required=True,
        help="Caminho raiz do Google Drive com as pastas de artistas"
    )
    parser.add_argument(
        "--out", default="dataset",
        help="Pasta de saída do dataset organizado (padrão: dataset/)"
    )
    parser.add_argument(
        "--analyze-only", action="store_true",
        help="Apenas analisa a estrutura do Drive sem extrair nada"
    )
    parser.add_argument(
        "--valid-ratio", type=float, default=0.1,
        help="Fração de músicas para validação (padrão: 0.10 = 10%%)"
    )
    args = parser.parse_args()

    drive_root = Path(args.drive)
    if not drive_root.exists():
        print(f"ERRO: Pasta não encontrada: {drive_root}")
        sys.exit(1)

    if args.analyze_only:
        print(f"Analisando: {drive_root}\n")
        stats = analyze_drive(drive_root)
        print(f"Artistas   : {stats['total_artistas']}")
        print(f"Músicas    : {stats['total_musicas']}")
        print(f"Formatos   : {dict(stats['formatos'])}")
        print("\nMúsicas por artista:")
        for artista, count in sorted(stats["musicas_por_artista"].items()):
            print(f"  {artista:<30} {count}")
        return

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"Drive   : {drive_root}")
    print(f"Saída   : {out_root}")
    print(f"Valid   : {int(args.valid_ratio * 100)}%")
    print()

    prepare(drive_root, out_root, valid_ratio=args.valid_ratio)


if __name__ == "__main__":
    main()
