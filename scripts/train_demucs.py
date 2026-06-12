"""
train_demucs.py — Fine-tuning do Demucs com o dataset de multitracks gospel
==============================================================================
Treina (ou fine-tuna) um modelo HTDemucs com as suas 500+ músicas do Drive.

Modos de operação
-----------------
  finetune (padrão)
      Parte do htdemucs_6s pré-treinado e especializa para gospel.
      Fontes: drums · bass · vocals · piano · guitar · other
      Tempo estimado (RTX 3060 12 GB, 500 músicas, 100 épocas): ~24–48 h

  scratch
      Treina do zero com até 9 fontes — máxima separação por classe.
      Fontes: drums · bass · vocals · backing_vocals · guitar · piano
              violao · sopros · other
      Requer ≥ 40 músicas por classe para convergir bem.
      Tempo estimado: ~5–10× mais que fine-tuning.

Pré-requisitos
--------------
  1. Dataset preparado:
       python scripts/prepare_dataset.py --drive <caminho> --out dataset/
  2. Ambiente virtual ativado:
       .venv\\Scripts\\Activate.ps1

Uso
---
  python scripts/train_demucs.py --dataset dataset/
  python scripts/train_demucs.py --dataset dataset/ --epochs 150
  python scripts/train_demucs.py --dataset dataset/ --mode scratch
  python scripts/train_demucs.py --dataset dataset/ --dry-run
  python scripts/train_demucs.py --dataset dataset/ --batch-size 2  # GPU < 8 GB
"""

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

# ── Fontes por modo ───────────────────────────────────────────────────────────
SOURCES_FINETUNE = ["drums", "bass", "vocals", "piano", "guitar", "other"]

# Para treino do zero incluímos todas as classes com dados suficientes
SOURCES_SCRATCH = [
    "drums", "bass", "vocals", "backing_vocals",
    "guitar", "piano", "violao", "sopros", "other",
]

# Threshold mínimo de cobertura para manter uma fonte no treino do zero
MIN_COVERAGE_PCT = 30.0  # 30% das músicas devem ter o stem

# Parâmetros base (otimizados para RTX 3060 12 GB + Ryzen 7 5700X)
DEFAULTS = {
    "batch_size":  4,       # seguro para 12 GB VRAM; use 2 se der OOM
    "epochs":      100,
    "segment":     6,       # janela de 6 s
    "samplerate":  44100,
    "channels":    2,
    "num_workers": 4,       # 4 de 8 cores livres para I/O
    "lr_finetune": 3e-4,    # LR baixo para não destruir pesos pré-treinados
    "lr_scratch":  1e-3,    # LR maior para treino do zero
    "seed":        42,
}


# ── Utilitários ───────────────────────────────────────────────────────────────

def venv_python() -> Path:
    """Retorna o Python do venv (fallback: Python atual)."""
    for p in [
        Path(".venv/Scripts/python.exe"),   # Windows
        Path(".venv/bin/python"),            # Linux / macOS
    ]:
        if p.exists():
            return p
    return Path(sys.executable)


def check_cuda() -> tuple[bool, str, int]:
    """Retorna (disponível, nome_gpu, vram_mb)."""
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory // (1024 ** 2)
            return True, name, vram
    except ImportError:
        pass
    return False, "CPU", 0


def suggest_batch_size(vram_mb: int) -> int:
    if vram_mb >= 12000:
        return 4
    if vram_mb >= 8000:
        return 3
    if vram_mb >= 6000:
        return 2
    return 1


# ── Validação do dataset ──────────────────────────────────────────────────────

def scan_dataset(dataset_path: Path, sources: list[str]) -> dict:
    """
    Percorre train/ e valid/, conta quantas músicas têm cada stem.
    Retorna estatísticas e lista de músicas sem mixture.wav.
    """
    train_dir = dataset_path / "train"
    valid_dir = dataset_path / "valid"

    if not train_dir.exists():
        raise FileNotFoundError(
            f"Pasta train/ não encontrada em: {dataset_path}\n"
            "Execute primeiro:\n"
            "  python scripts/prepare_dataset.py --drive <caminho> --out dataset/"
        )
    if not valid_dir.exists():
        raise FileNotFoundError(f"Pasta valid/ não encontrada em: {dataset_path}")

    train_songs = sorted(d for d in train_dir.iterdir() if d.is_dir())
    valid_songs  = sorted(d for d in valid_dir.iterdir() if d.is_dir())

    coverage: Counter = Counter()
    missing_mix: list[str] = []

    for song in train_songs:
        if not (song / "mixture.wav").exists():
            missing_mix.append(song.name)
        for src in sources:
            if (song / f"{src}.wav").exists():
                coverage[src] += 1

    return {
        "train":       len(train_songs),
        "valid":       len(valid_songs),
        "coverage":    dict(coverage),
        "missing_mix": missing_mix,
    }


def filter_sources_by_coverage(
    stats: dict,
    sources: list[str],
    min_pct: float,
) -> list[str]:
    """
    Remove fontes com cobertura insuficiente (< min_pct%).
    Garante que 'other' sempre permanece como catch-all.
    """
    total = stats["train"]
    kept = []
    for src in sources:
        n   = stats["coverage"].get(src, 0)
        pct = n / total * 100 if total else 0
        if pct >= min_pct or src == "other":
            kept.append(src)
    return kept


def print_dataset_report(stats: dict, sources: list[str]) -> None:
    total = stats["train"]
    print("\n" + "=" * 64)
    print("  DATASET")
    print("=" * 64)
    print(f"  Músicas treino    : {total}")
    print(f"  Músicas validação : {stats['valid']}")
    print()
    print("  Cobertura de stems (treino):")
    for src in sources:
        n   = stats["coverage"].get(src, 0)
        pct = n / total * 100 if total else 0
        bar = "#" * int(pct / 5)
        warn = "  <- BAIXA - sera mesclado em 'other'" if pct < MIN_COVERAGE_PCT else ""
        print(f"    {src:<18} {n:>4}/{total}  {pct:5.1f}%  {bar}{warn}")

    if stats["missing_mix"]:
        print(f"\n  [AVISO] {len(stats['missing_mix'])} musicas sem mixture.wav (serao ignoradas)")

    if total < 30:
        print(f"\n  [AVISO] Dataset muito pequeno ({total} musicas).")
        print("    Recomendado: >= 50 para fine-tuning, >= 150 para scratch.")


# ── Remapeamento de stems não suportados ──────────────────────────────────────

def remap_unsupported_stems(dataset_path: Path, sources: list[str]) -> None:
    """
    Para o modo finetune (6 fontes), renomeia/copia stems que o htdemucs_6s
    não conhece para 'other':
      - backing_vocals → mesclado em other (já feito pelo prepare_dataset se não constar)
      - violao, sopros, keys → ignorados (caem em 'other' automaticamente)

    Esta função NÃO modifica o dataset; serve apenas para informar.
    O Demucs ignora arquivos de stem desconhecidos na pasta da música.
    """
    ignored = [s for s in ["backing_vocals", "violao", "sopros", "keys"]
               if s not in sources]
    if ignored:
        print(f"\n  [INFO] Stems nao usados no treino (irao para 'other'):")
        for s in ignored:
            print(f"    - {s}")


# ── Construção do comando de treino ───────────────────────────────────────────

def build_command(
    python: Path,
    dataset_path: Path,
    sources: list[str],
    cfg: dict,
    mode: str,
    cuda: bool,
) -> list[str]:
    """
    Monta a lista de argumentos para:
        python -m demucs.train [overrides Hydra]
    """
    src_str   = "[" + ",".join(sources) + "]"
    dset_path = str(dataset_path).replace("\\", "/")  # Hydra precisa de /

    cmd = [str(python), "-m", "demucs.train"]

    # ── Modo fine-tuning ──────────────────────────────────────────────────────
    if mode == "finetune":
        cmd += [
            "continue_pretrained=htdemucs_6s",
            "fine_tune=true",
        ]

    # ── Arquitetura ───────────────────────────────────────────────────────────
    cmd += [
        "model=htdemucs",
        f"sources={src_str}",
    ]

    # ── Dataset (wav) ─────────────────────────────────────────────────────────
    cmd += [
        f"dset.wav={dset_path}",
        f"dset.samplerate={cfg['samplerate']}",
        f"dset.channels={cfg['channels']}",
        f"dset.segment={cfg['segment']}",
        "dset.shift=1",
        "dset.normalize=true",
    ]

    # ── Otimizador ────────────────────────────────────────────────────────────
    lr = cfg["lr_finetune"] if mode == "finetune" else cfg["lr_scratch"]
    cmd += [
        f"optim.lr={lr}",
        "optim.momentum=0.9",
    ]

    # ── Hardware / Performance ────────────────────────────────────────────────
    cmd += [
        f"batch_size={cfg['batch_size']}",
        f"num_workers={cfg['num_workers']}",
        f"device={'cuda' if cuda else 'cpu'}",
        f"epochs={cfg['epochs']}",
        f"seed={cfg['seed']}",
        "save_every=5",  # checkpoint a cada 5 épocas
    ]

    return cmd


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Treino / fine-tuning do Demucs para separação de instrumentos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dataset", default="dataset",
        help="Pasta do dataset (padrão: dataset/)",
    )
    parser.add_argument(
        "--mode", choices=["finetune", "scratch"], default="finetune",
        help=(
            "finetune = parte do htdemucs_6s pré-treinado (rápido, recomendado)\n"
            "scratch  = treina do zero com mais fontes (lento, máxima separação)"
        ),
    )
    parser.add_argument(
        "--epochs", type=int, default=DEFAULTS["epochs"],
        help=f"Épocas (padrão: {DEFAULTS['epochs']})",
    )
    parser.add_argument(
        "--batch-size", type=int, default=None,
        help="Batch size (padrão: automático pela VRAM)",
    )
    parser.add_argument(
        "--lr", type=float, default=None,
        help="Learning rate (padrão: 3e-4 finetune / 1e-3 scratch)",
    )
    parser.add_argument(
        "--num-workers", type=int, default=DEFAULTS["num_workers"],
        help=f"Workers de dados (padrão: {DEFAULTS['num_workers']})",
    )
    parser.add_argument(
        "--segment", type=int, default=DEFAULTS["segment"],
        help=f"Duração do segmento em segundos (padrão: {DEFAULTS['segment']})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Imprime o comando sem executar",
    )
    args = parser.parse_args()

    # ── 1. Hardware ───────────────────────────────────────────────────────────
    cuda_ok, gpu_name, vram_mb = check_cuda()
    batch = args.batch_size or (suggest_batch_size(vram_mb) if cuda_ok else 1)

    print("\n" + "=" * 64)
    print("  HARDWARE")
    print("=" * 64)
    if cuda_ok:
        print(f"  GPU    : {gpu_name}  ({vram_mb} MB VRAM)")
        print(f"  Batch  : {batch}  (sugerido para {vram_mb} MB VRAM)")
    else:
        print("  [AVISO] CUDA nao disponivel - CPU e muito lento para treinar!")
        print("    Verifique os drivers NVIDIA e a instalacao do PyTorch CUDA.")

    # ── 2. Fontes conforme o modo ─────────────────────────────────────────────
    sources_all = SOURCES_FINETUNE if args.mode == "finetune" else SOURCES_SCRATCH

    # ── 3. Valida o dataset ───────────────────────────────────────────────────
    dataset_path = Path(args.dataset).resolve()
    try:
        stats = scan_dataset(dataset_path, sources_all)
    except FileNotFoundError as exc:
        print(f"\n[ERRO] {exc}")
        sys.exit(1)

    print_dataset_report(stats, sources_all)

    # No modo scratch, filtra fontes com cobertura insuficiente
    if args.mode == "scratch":
        sources = filter_sources_by_coverage(stats, sources_all, MIN_COVERAGE_PCT)
        removed = [s for s in sources_all if s not in sources]
        if removed:
            print(f"\n  Fontes removidas por baixa cobertura: {removed}")
            print(f"  Fontes finais: {sources}")
    else:
        sources = sources_all
        remap_unsupported_stems(dataset_path, sources)

    if len(sources) < 2:
        print("\n[ERRO] Nao ha fontes suficientes com cobertura minima. Verifique o dataset.")
        sys.exit(1)

    # ── 4. Configura ──────────────────────────────────────────────────────────
    cfg = {
        "batch_size":  batch,
        "epochs":      args.epochs,
        "segment":     args.segment,
        "samplerate":  DEFAULTS["samplerate"],
        "channels":    DEFAULTS["channels"],
        "num_workers": args.num_workers,
        "lr_finetune": args.lr or DEFAULTS["lr_finetune"],
        "lr_scratch":  args.lr or DEFAULTS["lr_scratch"],
        "seed":        DEFAULTS["seed"],
    }

    python = venv_python()
    cmd    = build_command(python, dataset_path, sources, cfg, args.mode, cuda_ok)

    lr_display = cfg["lr_finetune"] if args.mode == "finetune" else cfg["lr_scratch"]

    print("\n" + "=" * 64)
    print("  CONFIGURAÇÃO DO TREINO")
    print("=" * 64)
    print(f"  Modo        : {args.mode}")
    if args.mode == "finetune":
        print(f"  Base        : htdemucs_6s (Facebook/Meta — pré-treinado)")
    else:
        print(f"  Base        : do zero (HTDemucs architecture)")
    print(f"  Fontes      : {', '.join(sources)}")
    print(f"  Épocas      : {cfg['epochs']}")
    print(f"  Batch size  : {cfg['batch_size']}")
    print(f"  Segmento    : {cfg['segment']} s")
    print(f"  LR          : {lr_display}")
    print(f"  Workers     : {cfg['num_workers']}")
    print(f"  Dataset     : {dataset_path}")
    print(f"  Checkpoints : outputs/  (salva a cada 5 épocas)")
    print()

    if args.mode == "finetune":
        print("  [INFO] FINE-TUNING: o Demucs baixara os pesos do htdemucs_6s")
        print("    automaticamente na primeira execucao (~300 MB).")
    else:
        print("  [INFO] SCRATCH: treino do zero - pode levar dias na RTX 3060.")
        print("    Considere comecar com --mode finetune para validar o pipeline.")

    print()

    if args.dry_run:
        print("  [DRY RUN] Comando que seria executado:")
        print("  " + " \\\n    ".join(str(c) for c in cmd))
        print()
        print("  Para executar de verdade, remova o --dry-run.")
        return

    # ── 5. Treina ─────────────────────────────────────────────────────────────
    print("=" * 64)
    print("  Iniciando treino... (Ctrl+C para pausar e retomar depois)")
    print("=" * 64 + "\n")

    try:
        result = subprocess.run(cmd, cwd=str(Path(__file__).parent.parent))
    except KeyboardInterrupt:
        print("\n\nTreino pausado.")
        print("  Execute novamente para retomar do ultimo checkpoint.")
        sys.exit(0)

    if result.returncode != 0:
        print(f"\n[ERRO] Demucs encerrou com codigo {result.returncode}")
        print("  Causas comuns:")
        print("  - OOM de VRAM -> tente --batch-size 2")
        print("  - Dataset corrompido -> re-execute prepare_dataset.py")
        print("  - Demucs nao encontrado -> ative o venv (.venv\\Scripts\\Activate.ps1)")
        sys.exit(result.returncode)
    else:
        print("\n[OK] Treino concluido!")
        print("  Modelo salvo em: outputs/<signature>/models/")
        print()
        print("  Para usar o modelo no StemCraft, edite stemcraft/config.py:")
        print('  DEFAULT_MODEL = "outputs/<signature>"')


if __name__ == "__main__":
    main()
