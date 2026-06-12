"""
scan_stems.py — Extrai e normaliza todos os nomes de stem do dataset
=====================================================================
Varre os arquivos .rar/.zip/.7z em --drive SEM extrair os arquivos,
apenas lendo o índice interno de cada arquivo.

Gera:
  stem_names_report.csv  — uma linha por nome bruto único, com contagem e
                           mapeamento canônico (fácil de editar no Excel)
  stem_names_report.txt  — relatório legível no terminal

Uso:
  python scripts/scan_stems.py --drive "F:\\dataset_raw"
  python scripts/scan_stems.py --drive "F:\\dataset_raw" --out "relatorios/"
  python scripts/scan_stems.py --drive "F:\\dataset_raw" --show-archives
"""

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# ─── importa STEM_MAP e helpers do prepare_dataset ───────────────────────────
# Adiciona scripts/ ao path para import relativo funcionar de qualquer CWD
sys.path.insert(0, str(Path(__file__).parent))
from prepare_dataset import STEM_MAP, SKIP_STEMS, AUDIO_EXTS, normalize_stem_name


# ─────────────────────────────────────────────────────────────────────────────
# Funções de listagem (sem extração)
# ─────────────────────────────────────────────────────────────────────────────

def list_archive_contents(archive_path: Path) -> list[str]:
    """Retorna lista de nomes de arquivo dentro do arquivo comprimido."""
    ext = archive_path.suffix.lower()
    names: list[str] = []

    try:
        if ext == ".zip":
            import zipfile
            with zipfile.ZipFile(str(archive_path)) as zf:
                names = [info.filename for info in zf.infolist() if not info.is_dir()]

        elif ext == ".rar":
            try:
                import rarfile
                with rarfile.RarFile(str(archive_path)) as rf:
                    names = [info.filename for info in rf.infolist() if not info.isdir()]
            except ImportError:
                print(f"  ⚠  rarfile não instalado — pulando {archive_path.name}")

        elif ext == ".7z":
            try:
                import py7zr
                with py7zr.SevenZipFile(str(archive_path), mode="r") as sz:
                    names = [f.filename for f in sz.list() if not f.is_directory]
            except ImportError:
                print(f"  ⚠  py7zr não instalado — pulando {archive_path.name}")

    except Exception as exc:
        print(f"  ✕ Erro ao ler {archive_path.name}: {exc}")

    # Filtra apenas extensões de áudio
    return [n for n in names if Path(n).suffix.lower() in AUDIO_EXTS]


def scan_drive(drive_root: Path, show_archives: bool = False):
    """
    Varre todas as pastas de artista → arquivos comprimidos → lista conteúdo.

    Retorna:
        raw_counter    Counter  {nome_bruto: contagem_total}
        mapped         dict     {nome_bruto: classe_canônica | None}
        per_archive    dict     {arquivo_path: [nomes_brutos]}
    """
    raw_counter: Counter = Counter()
    mapped: dict[str, str | None] = {}
    per_archive: dict[Path, list[str]] = {}

    archive_exts = ("*.rar", "*.zip", "*.7z")
    artistas = sorted(d for d in drive_root.iterdir() if d.is_dir())

    if not artistas:
        # Drive sem subpastas — busca diretamente na raiz
        artistas = [drive_root]

    total_archives = 0
    for artista_dir in artistas:
        arquivos: list[Path] = []
        for pat in archive_exts:
            arquivos.extend(sorted(artista_dir.glob(pat)))

        for arq in arquivos:
            total_archives += 1
            contents = list_archive_contents(arq)

            if show_archives and contents:
                print(f"\n  {arq.relative_to(drive_root)}")
                for name in contents:
                    stem = Path(name).stem
                    canon = normalize_stem_name(name)
                    tag = f"→ {canon}" if canon else "⊘ ignorado"
                    print(f"    {stem:<30}  {tag}")

            per_archive[arq] = contents
            for full_name in contents:
                stem_basename = Path(full_name).stem  # sem extensão, sem path
                raw_counter[stem_basename] += 1
                if stem_basename not in mapped:
                    mapped[stem_basename] = normalize_stem_name(full_name)

    print(f"\n  Arquivos comprimidos varridos : {total_archives}")
    print(f"  Nomes brutos únicos encontrados: {len(raw_counter)}")
    return raw_counter, mapped, per_archive


# ─────────────────────────────────────────────────────────────────────────────
# Relatórios
# ─────────────────────────────────────────────────────────────────────────────

def build_report(raw_counter: Counter, mapped: dict) -> dict:
    """Organiza os nomes em categorias para exibição."""
    ignored  = {n: c for n, c in raw_counter.items() if mapped[n] is None}
    unmapped = {n: c for n, c in raw_counter.items() if mapped[n] == "other"}
    known    = {n: c for n, c in raw_counter.items() if mapped[n] not in (None, "other")}

    # Agrupa por classe canônica
    by_class: dict[str, Counter] = defaultdict(Counter)
    for name, canon in mapped.items():
        if canon and canon != "other":
            by_class[canon][name] += raw_counter[name]

    return {
        "known":    known,
        "unmapped": unmapped,
        "ignored":  ignored,
        "by_class": by_class,
    }


def print_report(raw_counter: Counter, mapped: dict, report: dict):
    sep = "─" * 68

    # ── Por classe canônica ─────────────────────────────────────────────────
    print(f"\n{'═'*68}")
    print("  MAPEAMENTOS CONFIRMADOS (raw name → classe canônica)")
    print(f"{'═'*68}")
    for canon in sorted(report["by_class"]):
        names = report["by_class"][canon]
        print(f"\n  [{canon}]")
        for name, count in names.most_common():
            print(f"    {name:<35} {count:>4}×")

    # ── Ignorados ──────────────────────────────────────────────────────────
    if report["ignored"]:
        print(f"\n{'═'*68}")
        print("  IGNORADOS (click track, guide vocal, peaks…)")
        print(f"{'═'*68}")
        for name, count in sorted(report["ignored"].items(), key=lambda x: -x[1]):
            print(f"    {name:<35} {count:>4}×")

    # ── Não mapeados → "other" ─────────────────────────────────────────────
    if report["unmapped"]:
        print(f"\n{'═'*68}")
        print("  NÃO MAPEADOS → caindo em \"other\"  ← REVISAR")
        print(f"{'═'*68}")
        for name, count in sorted(report["unmapped"].items(), key=lambda x: -x[1]):
            hint = _guess_class(name)
            print(f"    {name:<35} {count:>4}×  {hint}")
    else:
        print(f"\n  ✓ Todos os nomes estão mapeados — nada cai em \"other\".")

    # ── Resumo ─────────────────────────────────────────────────────────────
    print(f"\n{'═'*68}")
    print("  RESUMO")
    print(f"{'═'*68}")
    class_totals = {c: sum(v.values()) for c, v in report["by_class"].items()}
    for canon, total in sorted(class_totals.items(), key=lambda x: -x[1]):
        bar = "█" * (total * 30 // max(class_totals.values()))
        print(f"  {canon:<18} {total:>4}  {bar}")
    print(f"\n  Ignorados : {sum(report['ignored'].values()):>4}")
    print(f"  Other     : {sum(report['unmapped'].values()):>4}  ← adicionar ao STEM_MAP")
    print(f"{'═'*68}\n")


def _guess_class(name: str) -> str:
    """Tenta adivinhar a classe de um nome não mapeado para sugerir ao usuário."""
    n = name.lower()
    hints = [
        (["voz", "voc", "lead", "canto", "singer"], "→ vocals?"),
        (["back", "coro", "choir", "bg"], "→ backing_vocals?"),
        (["drum", "batt", "perc", "kick", "snare"], "→ drums?"),
        (["bass", "baixo"], "→ bass?"),
        (["guitar", "gt", "gtr", "violao", "acoustic"], "→ guitar/violao?"),
        (["piano", "keys", "teclad", "organ", "synth", "pad"], "→ piano?"),
        (["sax", "trompete", "horn", "brass", "flauta", "sopro"], "→ sopros?"),
        (["click", "metrono", "click track"], "→ SKIP?"),
        (["guide", "guia", "ref"], "→ SKIP?"),
    ]
    for keywords, tag in hints:
        if any(k in n for k in keywords):
            return tag
    return ""


def save_csv(raw_counter: Counter, mapped: dict, out_path: Path):
    """Salva CSV com: nome_bruto, contagem, classe_canônica, status."""
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["nome_bruto", "contagem", "classe_canonica", "status"])
        for name, count in raw_counter.most_common():
            canon = mapped[name]
            if canon is None:
                status = "ignorado"
            elif canon == "other":
                status = "NAO_MAPEADO"
            else:
                status = "ok"
            writer.writerow([name, count, canon or "", status])
    print(f"  CSV salvo em: {out_path}")


def save_txt(raw_counter: Counter, mapped: dict, report: dict, out_path: Path):
    """Salva versão texto do relatório."""
    lines: list[str] = []

    lines.append("MAPEAMENTOS CONFIRMADOS")
    lines.append("=" * 60)
    for canon in sorted(report["by_class"]):
        lines.append(f"\n[{canon}]")
        for name, count in report["by_class"][canon].most_common():
            lines.append(f"  {name:<35} {count}×")

    lines.append("\nNOMES IGNORADOS (click/guide/peaks)")
    lines.append("=" * 60)
    for name, count in sorted(report["ignored"].items(), key=lambda x: -x[1]):
        lines.append(f"  {name:<35} {count}×")

    lines.append("\nNAO MAPEADOS (cai em 'other')")
    lines.append("=" * 60)
    for name, count in sorted(report["unmapped"].items(), key=lambda x: -x[1]):
        lines.append(f"  {name:<35} {count}×  {_guess_class(name)}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  TXT salvo em: {out_path}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extrai e normaliza todos os nomes de stem do dataset"
    )
    parser.add_argument(
        "--drive", required=True,
        help="Pasta raiz do dataset (ex: F:\\dataset_raw)"
    )
    parser.add_argument(
        "--out", default=".",
        help="Pasta de saída dos relatórios (padrão: diretório atual)"
    )
    parser.add_argument(
        "--show-archives", action="store_true",
        help="Mostra o conteúdo de cada arquivo individualmente"
    )
    args = parser.parse_args()

    drive_root = Path(args.drive)
    out_dir    = Path(args.out)

    if not drive_root.exists():
        print(f"ERRO: Pasta não encontrada: {drive_root}")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Varrendo: {drive_root}")
    raw_counter, mapped, per_archive = scan_drive(drive_root, args.show_archives)

    report = build_report(raw_counter, mapped)
    print_report(raw_counter, mapped, report)

    save_csv(raw_counter, mapped, out_dir / "stem_names_report.csv")
    save_txt(raw_counter, mapped, report, out_dir / "stem_names_report.txt")


if __name__ == "__main__":
    main()
