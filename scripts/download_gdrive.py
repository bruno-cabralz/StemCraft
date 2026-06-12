"""
download_gdrive.py — Sincroniza o dataset de multitracks do Google Drive
=========================================================================
Detecta o Google Drive Desktop montado ou faz download via gdown/rclone.

Opções de acesso
----------------
  A) Google Drive Desktop (mais rápido — recomendado)
       Os arquivos já estão locais.
       Use diretamente:
         python scripts/prepare_dataset.py --drive "G:\\Multitracks Gospel" --out dataset/

  B) Download pela URL de pasta compartilhada  (usa gdown)
       python scripts/download_gdrive.py --url "https://drive.google.com/drive/folders/XXXX"
         → baixa para dataset_raw/ e já executa prepare_dataset.py

  C) Rclone  (melhor para > 10 GB ou "Compartilhados comigo")
       Veja instruções com:
         python scripts/download_gdrive.py --rclone-help

Uso rápido
----------
  # detecta Drive Desktop montado e mostra o caminho
  python scripts/download_gdrive.py --find-drive

  # download via URL + prepara dataset em seguida
  python scripts/download_gdrive.py --url "https://drive.google.com/drive/folders/XXXX"

  # só mostra instruções do rclone
  python scripts/download_gdrive.py --rclone-help
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


# ── A) Google Drive Desktop ───────────────────────────────────────────────────

def find_gdrive_desktop_windows() -> Path | None:
    """
    Tenta localizar a raiz do Google Drive Desktop em Windows.
    O Drive Desktop monta como letra de drive (G:\\, H:\\, etc).
    """
    import string

    # Primeiro tenta variável de ambiente que o Drive Desktop define às vezes
    import os
    gdrive_env = os.environ.get("GOOGLE_DRIVE_SYNC_FOLDER")
    if gdrive_env and Path(gdrive_env).exists():
        return Path(gdrive_env)

    for letter in string.ascii_uppercase[6:]:   # começa em G para poupar tempo
        root = Path(f"{letter}:\\")
        if not root.exists():
            continue
        # Verifica subpastas típicas do Drive Desktop
        for marker in ("My Drive", "Meu Drive", "Shared drives", "Drives compartilhados"):
            if (root / marker).exists():
                return root
        # Verificação via nome do volume (sem dependências extras)
        try:
            out = subprocess.run(
                ["cmd", "/c", f"vol {letter}:"],
                capture_output=True, text=True, timeout=3,
            ).stdout
            if "google" in out.lower():
                return root
        except Exception:
            pass

    return None


def locate_multitracks_folder(drive_root: Path, folder_name: str = "Multitracks Gospel") -> Path | None:
    """
    Busca a pasta do dataset dentro do Drive montado.
    Verifica até dois níveis de profundidade.
    """
    for depth0 in (drive_root,):
        # Nível 0 — raiz do drive
        candidate = depth0 / folder_name
        if candidate.exists():
            return candidate
        # Nível 1 — dentro de "My Drive", "Meu Drive", "Shared drives" etc.
        try:
            for sub in depth0.iterdir():
                if sub.is_dir() and (sub / folder_name).exists():
                    return sub / folder_name
        except PermissionError:
            pass
    return None


# ── B) gdown ──────────────────────────────────────────────────────────────────

def extract_folder_id(url: str) -> str | None:
    """Extrai o ID da pasta de uma URL do Google Drive."""
    patterns = [
        r"drive\.google\.com/drive/folders/([a-zA-Z0-9_-]+)",
        r"drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def download_folder_gdown(folder_id: str, out_dir: Path) -> None:
    """
    Baixa uma pasta compartilhada do Google Drive usando gdown.
    Funciona para pastas com link público ("Qualquer pessoa com o link").
    Para "Compartilhados comigo" prefira o rclone.
    """
    try:
        import gdown  # noqa: F401
    except ImportError:
        print("  ✕ gdown não instalado. Executando instalação...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "gdown"],
            check=True,
        )
        import gdown  # noqa: F811

    out_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://drive.google.com/drive/folders/{folder_id}"

    print(f"\nBaixando pasta do Google Drive...")
    print(f"  URL     : {url}")
    print(f"  Destino : {out_dir}")
    print()

    import gdown
    gdown.download_folder(
        url=url,
        output=str(out_dir),
        quiet=False,
        use_cookies=True,   # usa cookies do browser para "Compartilhados comigo"
    )

    n_archives = len(list(out_dir.rglob("*.rar"))) + \
                 len(list(out_dir.rglob("*.zip"))) + \
                 len(list(out_dir.rglob("*.7z")))
    print(f"\n✓ Download concluído: {n_archives} arquivos compactados em {out_dir}")


# ── C) rclone ─────────────────────────────────────────────────────────────────

RCLONE_INSTRUCTIONS = """\
╔══════════════════════════════════════════════════════════════════════╗
║  DOWNLOAD VIA RCLONE  (recomendado para "Compartilhados comigo")    ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  1. Instale o rclone:                                                ║
║       https://rclone.org/downloads/  (baixe e coloque no PATH)      ║
║       ou via winget:  winget install Rclone.Rclone                  ║
║                                                                      ║
║  2. Configure o remote do Google Drive:                              ║
║       rclone config                                                  ║
║       → Escolha "n" (new remote)                                    ║
║       → Nome: gdrive                                                 ║
║       → Tipo: drive (Google Drive)                                  ║
║       → Siga as instruções de OAuth2 (abrirá o browser)             ║
║                                                                      ║
║  3. Liste os arquivos compartilhados:                                ║
║       rclone ls "gdrive:Multitracks Gospel" --drive-shared-with-me  ║
║                                                                      ║
║  4. Baixe o dataset completo:                                        ║
║       rclone copy "gdrive:Multitracks Gospel" dataset_raw\\          ║
║         --drive-shared-with-me -P                                    ║
║                                                                      ║
║  5. Prepare o dataset:                                               ║
║       python scripts/prepare_dataset.py                             ║
║         --drive dataset_raw --out dataset/                          ║
╚══════════════════════════════════════════════════════════════════════╝
"""


# ── Prepara o dataset automaticamente após download ──────────────────────────

def run_prepare_dataset(raw_path: Path, out_path: Path) -> None:
    python = Path(sys.executable)
    script = Path(__file__).parent / "prepare_dataset.py"
    cmd = [
        str(python), str(script),
        "--drive", str(raw_path),
        "--out",   str(out_path),
    ]
    print(f"\nExecutando prepare_dataset.py...")
    print("  " + " ".join(str(c) for c in cmd) + "\n")
    subprocess.run(cmd)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza o dataset de multitracks do Google Drive",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--find-drive", action="store_true",
        help="Detecta o Google Drive Desktop montado e mostra como usá-lo",
    )
    parser.add_argument(
        "--url",
        help="URL da pasta compartilhada no Google Drive",
    )
    parser.add_argument(
        "--folder-id",
        help="ID da pasta no Google Drive (alternativa à --url)",
    )
    parser.add_argument(
        "--out", default="dataset_raw",
        help="Pasta de destino do download (padrão: dataset_raw/)",
    )
    parser.add_argument(
        "--prepare", action="store_true",
        help="Executa prepare_dataset.py automaticamente após o download",
    )
    parser.add_argument(
        "--dataset-out", default="dataset",
        help="Pasta de saída do dataset preparado (padrão: dataset/)",
    )
    parser.add_argument(
        "--rclone-help", action="store_true",
        help="Mostra instruções detalhadas para download via rclone",
    )
    args = parser.parse_args()

    if args.rclone_help:
        print(RCLONE_INSTRUCTIONS)
        return

    # ── Opção A: detectar Drive Desktop ──────────────────────────────────────
    if args.find_drive or (not args.url and not args.folder_id):
        print("\nProcurando Google Drive Desktop montado em Windows...")

        if sys.platform != "win32":
            print("  Detecção automática disponível apenas em Windows.")
            print("  No Linux/macOS, verifique onde o Drive está montado.")
            print(RCLONE_INSTRUCTIONS)
            return

        drive_root = find_gdrive_desktop_windows()

        if drive_root is None:
            print("\n  Google Drive Desktop não detectado.\n")
            print("  Opções:")
            print("  1. Instale o Google Drive Desktop e faça login")
            print("     → https://www.google.com/drive/download/")
            print("  2. Use --url com o link da pasta compartilhada")
            print("  3. Use --rclone-help para download pelo terminal")
            print()
            print(RCLONE_INSTRUCTIONS)
            return

        print(f"\n✓ Google Drive encontrado em: {drive_root}")
        mt = locate_multitracks_folder(drive_root)

        if mt:
            print(f"✓ Pasta 'Multitracks Gospel' encontrada:")
            print(f"  {mt}")
            print()
            print("  Próximo passo — preparar o dataset:")
            print(f'  python scripts/prepare_dataset.py --drive "{mt}" --out dataset/')
            print()
            print("  Depois de preparado, inicie o treino:")
            print("  python scripts/train_demucs.py --dataset dataset/")
        else:
            print()
            print("  ⚠ Pasta 'Multitracks Gospel' não encontrada automaticamente.")
            print(f"  Navegue pelo Drive montado em {drive_root} e copie o caminho.")
            print()
            print("  Depois use:")
            print('  python scripts/prepare_dataset.py --drive "<caminho>" --out dataset/')

        return

    # ── Opção B: download via gdown ───────────────────────────────────────────
    folder_id = args.folder_id

    if not folder_id and args.url:
        folder_id = extract_folder_id(args.url)
        if not folder_id:
            print(f"✗ Não foi possível extrair o ID da URL: {args.url}")
            print("  Certifique-se de que é uma URL de pasta do Google Drive.")
            print("  Exemplo: https://drive.google.com/drive/folders/1AbCdEfGhIjK...")
            sys.exit(1)

    out_dir = Path(args.out)
    download_folder_gdown(folder_id, out_dir)

    if args.prepare:
        run_prepare_dataset(out_dir, Path(args.dataset_out))
        print(f"\nTudo pronto! Dataset em: {args.dataset_out}/")
        print("Inicie o treino com:")
        print(f"  python scripts/train_demucs.py --dataset {args.dataset_out}/")
    else:
        print(f"\nPróximo passo:")
        print(f'  python scripts/prepare_dataset.py --drive "{out_dir}" --out dataset/')
        print("  python scripts/train_demucs.py --dataset dataset/")


if __name__ == "__main__":
    main()
