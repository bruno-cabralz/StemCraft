"""
post_download.py — Extrai e normaliza nomes após o download do Google Drive
============================================================================
Executa dois passos em sequência:

  1. EXTRAÇÃO  — encontra todos os .rar / .zip / .7z em --drive e extrai
                 cada um numa subpasta  <out>/<ARTISTA>/<MUSICA>/
  2. NORMALIZAÇÃO — renomeia os arquivos de áudio usando o STEM_MAP de
                    prepare_dataset.py  (ex: "EG 1.wav" → "guitar.wav")
  3. RELATÓRIO — imprime e salva quais nomes foram mapeados e quais
                 precisam ser adicionados ao STEM_MAP

Uso:
  # rodar manualmente depois que o rclone terminar
  python scripts/post_download.py --drive "F:\\dataset_raw" --out "F:\\dataset_stems"

  # só extrair, sem renomear
  python scripts/post_download.py --drive "F:\\dataset_raw" --out "F:\\dataset_stems" --extract-only

  # só normalizar uma pasta já extraída
  python scripts/post_download.py --drive "F:\\dataset_raw" --out "F:\\dataset_stems" --normalize-only
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from prepare_dataset import AUDIO_EXTS, SKIP_STEMS, STEM_MAP, normalize_stem_name


# ─────────────────────────────────────────────────────────────────────────────
# PASSO 1 — Extração
# ─────────────────────────────────────────────────────────────────────────────

ARCHIVE_EXTS = {".rar", ".zip", ".7z"}


def find_archives(drive_root: Path) -> list[tuple[str, Path]]:
    """Retorna lista de (nome_artista, caminho_arquivo) para todos os arquivos comprimidos."""
    results: list[tuple[str, Path]] = []
    artistas = sorted(d for d in drive_root.iterdir() if d.is_dir())
    if not artistas:
        artistas = [drive_root]
    for artista_dir in artistas:
        for arq in sorted(artista_dir.iterdir()):
            if arq.suffix.lower() in ARCHIVE_EXTS:
                results.append((artista_dir.name, arq))
    return results


def extract_archive(archive_path: Path, dest_dir: Path) -> list[Path]:
    """Extrai o arquivo para dest_dir. Retorna lista de arquivos de áudio extraídos."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = archive_path.suffix.lower()

    try:
        if ext == ".zip":
            import zipfile
            with zipfile.ZipFile(str(archive_path)) as zf:
                zf.extractall(str(dest_dir))

        elif ext == ".rar":
            try:
                import rarfile
                with rarfile.RarFile(str(archive_path)) as rf:
                    rf.extractall(str(dest_dir))
            except ImportError:
                print("  ✕ rarfile não instalado: pip install rarfile")
                return []

        elif ext == ".7z":
            try:
                import py7zr
                with py7zr.SevenZipFile(str(archive_path), mode="r") as sz:
                    sz.extractall(path=str(dest_dir))
            except ImportError:
                print("  ✕ py7zr não instalado: pip install py7zr")
                return []

    except Exception as exc:
        print(f"  ✕ Erro ao extrair {archive_path.name}: {exc}")
        return []

    return [f for f in dest_dir.rglob("*") if f.suffix.lower() in AUDIO_EXTS]


def run_extraction(drive_root: Path, out_root: Path) -> dict[Path, list[Path]]:
    """
    Extrai todos os arquivos comprimidos de drive_root para out_root.
    Retorna mapa {pasta_extraida: [arquivos_de_audio]}.
    """
    archives = find_archives(drive_root)
    total = len(archives)
    print(f"\n{'═'*68}")
    print(f"  PASSO 1 — EXTRAÇÃO  ({total} arquivos encontrados)")
    print(f"{'═'*68}")

    extracted_map: dict[Path, list[Path]] = {}
    ok = erro = pulados = 0

    for i, (artista, arq_path) in enumerate(archives, 1):
        dest = out_root / artista / arq_path.stem
        prefix = f"  [{i:>3}/{total}]"

        if dest.exists() and any(dest.rglob("*")):
            print(f"{prefix} ↷ Já extraído: {artista}/{arq_path.name}")
            audio_files = [f for f in dest.rglob("*") if f.suffix.lower() in AUDIO_EXTS]
            extracted_map[dest] = audio_files
            pulados += 1
            continue

        print(f"{prefix} ⬛ {artista}/{arq_path.name}")
        audio_files = extract_archive(arq_path, dest)

        if audio_files:
            print(f"         ✓ {len(audio_files)} arquivo(s) de áudio extraídos")
            extracted_map[dest] = audio_files
            ok += 1
        else:
            print(f"         ✕ Nenhum áudio encontrado")
            erro += 1

    print(f"\n  Extraídos agora : {ok}")
    print(f"  Já existiam     : {pulados}")
    print(f"  Com erro        : {erro}")
    return extracted_map


# ─────────────────────────────────────────────────────────────────────────────
# PASSO 2 — Normalização de nomes
# ─────────────────────────────────────────────────────────────────────────────

def normalize_folder(song_dir: Path) -> dict:
    """
    Renomeia arquivos de áudio dentro de song_dir usando STEM_MAP.
    Retorna estatísticas: {ok, ignorados, nao_mapeados, colisoes}.
    """
    stats = {"ok": [], "ignorados": [], "nao_mapeados": [], "colisoes": []}
    seen_classes: Counter = Counter()

    audio_files = sorted(f for f in song_dir.rglob("*") if f.suffix.lower() in AUDIO_EXTS)

    for af in audio_files:
        # Ignora arquivos que já foram normalizados (nome canônico)
        stem = af.stem.lower()
        canon = normalize_stem_name(af.name)

        if canon is None:
            # Click track, guide, peaks — move para subpasta _ignorados
            ignored_dir = song_dir / "_ignorados"
            ignored_dir.mkdir(exist_ok=True)
            af.rename(ignored_dir / af.name)
            stats["ignorados"].append(af.name)
            continue

        seen_classes[canon] += 1
        suffix = f"_{seen_classes[canon]}" if seen_classes[canon] > 1 else ""
        new_name = f"{canon}{suffix}{af.suffix}"
        new_path = af.parent / new_name

        if af.name == new_name:
            # Já está com o nome correto
            stats["ok"].append(new_name)
            continue

        if new_path.exists() and new_path != af:
            stats["colisoes"].append(f"{af.name} → {new_name} (já existe)")
            continue

        af.rename(new_path)

        if canon == "other":
            stats["nao_mapeados"].append(f"{af.stem} → other")
        else:
            stats["ok"].append(f"{af.stem} → {new_name}")

    return stats


def run_normalization(out_root: Path) -> tuple[Counter, list[str]]:
    """
    Percorre todas as subpastas de out_root e normaliza os nomes.
    Retorna (frequencia_por_classe, lista_nomes_nao_mapeados).
    """
    print(f"\n{'═'*68}")
    print("  PASSO 2 — NORMALIZAÇÃO DE NOMES")
    print(f"{'═'*68}")

    # Descobre pastas de músicas (2 níveis: artista/musica/)
    song_dirs: list[Path] = []
    for artista_dir in sorted(out_root.iterdir()):
        if not artista_dir.is_dir() or artista_dir.name.startswith("_"):
            continue
        for musica_dir in sorted(artista_dir.iterdir()):
            if musica_dir.is_dir():
                song_dirs.append(musica_dir)

    if not song_dirs:
        # Pasta plana (sem subpastas de artista)
        song_dirs = [d for d in out_root.iterdir() if d.is_dir() and not d.name.startswith("_")]

    freq: Counter = Counter()
    all_unmapped: list[str] = []
    total = len(song_dirs)

    for i, song_dir in enumerate(song_dirs, 1):
        stats = normalize_folder(song_dir)
        rel = song_dir.relative_to(out_root)
        print(f"  [{i:>3}/{total}] {rel}")

        for entry in stats["ok"]:
            classe = entry.split("→")[-1].strip().split(".")[0].split("_")[0]
            freq[classe] += 1

        for entry in stats["ignorados"]:
            print(f"          ⊘ ignorado : {entry}")

        for entry in stats["nao_mapeados"]:
            raw = entry.split("→")[0].strip()
            all_unmapped.append(raw)
            freq["other"] += 1
            print(f"          ⚠  other   : {entry}")

        for entry in stats["colisoes"]:
            print(f"          ⚡ colisão  : {entry}")

    return freq, all_unmapped


# ─────────────────────────────────────────────────────────────────────────────
# PASSO 3 — Relatório
# ─────────────────────────────────────────────────────────────────────────────

def print_final_report(freq: Counter, unmapped: list[str], out_root: Path):
    unmapped_counter = Counter(unmapped)
    max_val = max(freq.values()) if freq else 1

    print(f"\n{'═'*68}")
    print("  RELATÓRIO FINAL")
    print(f"{'═'*68}")
    print("  Frequência por classe:")
    for classe, count in freq.most_common():
        bar = "█" * (count * 30 // max_val)
        print(f"  {classe:<18} {count:>4}  {bar}")

    if unmapped_counter:
        print(f"\n  ⚠  NOMES NÃO MAPEADOS (caíram em 'other') — adicionar ao STEM_MAP:")
        print(f"  {'─'*60}")
        for name, count in unmapped_counter.most_common():
            print(f"  {name:<35} {count:>4}×")
        print(f"\n  Edite scripts/prepare_dataset.py → STEM_MAP para mapear esses nomes.")
    else:
        print("\n  ✓ Todos os nomes foram mapeados com sucesso!")

    # Salva JSON
    report = {
        "frequencia_por_classe": dict(freq.most_common()),
        "nomes_nao_mapeados":    dict(unmapped_counter.most_common()),
    }
    report_path = out_root / "normalization_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n  Relatório salvo em: {report_path}")
    print(f"{'═'*68}\n")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extrai e normaliza nomes de stems após o download do Google Drive"
    )
    parser.add_argument(
        "--drive", required=True,
        help="Pasta com os arquivos baixados (ex: F:\\dataset_raw)"
    )
    parser.add_argument(
        "--out", default="F:\\dataset_stems",
        help="Pasta de saída para os stems extraídos e renomeados"
    )
    parser.add_argument(
        "--extract-only", action="store_true",
        help="Apenas extrai os arquivos, sem renomear"
    )
    parser.add_argument(
        "--normalize-only", action="store_true",
        help="Apenas normaliza nomes numa pasta já extraída (--out deve existir)"
    )
    args = parser.parse_args()

    drive_root = Path(args.drive)
    out_root   = Path(args.out)

    if not drive_root.exists():
        print(f"ERRO: Pasta não encontrada: {drive_root}")
        sys.exit(1)

    out_root.mkdir(parents=True, exist_ok=True)

    # ── Passo 1: Extração ────────────────────────────────────────────────────
    if not args.normalize_only:
        run_extraction(drive_root, out_root)

    # ── Passo 2: Normalização ────────────────────────────────────────────────
    if not args.extract_only:
        freq, unmapped = run_normalization(out_root)
        print_final_report(freq, unmapped, out_root)

        if unmapped:
            print("  Próximo passo:")
            print("    1. Abra scripts/prepare_dataset.py")
            print("    2. Adicione os nomes não mapeados ao STEM_MAP")
            print("    3. Reexecute: python scripts/post_download.py --normalize-only \\")
            print(f'                  --drive "{drive_root}" --out "{out_root}"')
        else:
            print("  Próximo passo — gerar mixtures e dividir train/valid:")
            print(f'    python scripts/prepare_dataset.py --drive "{out_root}" --out "F:\\dataset"')


if __name__ == "__main__":
    main()
