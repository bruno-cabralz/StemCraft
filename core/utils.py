"""
core/utils.py — Utilitários compartilhados
==========================================
Constantes globais, helpers de terminal e funções auxiliares
usadas por todos os outros módulos.
"""

import re
from pathlib import Path


# ── Diretórios do projeto ─────────────────────────────────────────────────────
# BASE_DIR aponta para a raiz do projeto (onde está o main.py)
BASE_DIR   = Path(__file__).parent.parent

# Pasta temporária para arquivos intermediários (download, demucs, tts)
TEMP_DIR   = BASE_DIR / ".tmp"

# Pasta final com os stems exportados
OUTPUT_DIR = BASE_DIR / "output"

# Mapeamento de nomes internos → rótulos em português
STEM_LABELS = {
    "lead_vocals":    "Voz_Principal",
    "backing_vocals": "Voz_Backing",
    "vocals":         "Voz",
    "drums":          "Bateria",
    "bass":           "Baixo",
    "guitar":         "Guitarra",
    "piano":          "Piano",
    "other":          "Outros",
}


# ── Helpers de terminal colorido ──────────────────────────────────────────────
# Códigos ANSI para colorir o output no terminal (funciona no Mac/Linux)
class Colors:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    BLUE   = "\033[94m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    GRAY   = "\033[90m"


def print_banner() -> None:
    """Imprime o banner de boas-vindas do app."""
    print(f"""
{Colors.CYAN}{Colors.BOLD}
  ╔══════════════════════════════════════╗
  ║         StemSplit VS  🎛️             ║
  ║   Gerador de Multitracks Profissional ║
  ╚══════════════════════════════════════╝
{Colors.RESET}""")


def print_step(n: int, message: str) -> None:
    """Imprime um passo numerado com destaque."""
    print(f"\n{Colors.BLUE}{Colors.BOLD}[{n}]{Colors.RESET} {message}")


def print_success(message: str) -> None:
    """Imprime uma mensagem de sucesso em verde."""
    print(f"  {Colors.GREEN}✓{Colors.RESET} {message}")


def print_error(message: str) -> None:
    """Imprime uma mensagem de erro em vermelho."""
    print(f"\n{Colors.RED}✗ Erro: {message}{Colors.RESET}")


def sanitize_filename(name: str) -> str:
    """
    Remove caracteres inválidos de um nome de arquivo.

    Mantém letras, números, espaços, hífen e underscore.
    Substitui espaços por underscore para compatibilidade com DAWs.

    Args:
        name: Nome original (ex: título do vídeo do YouTube).

    Returns:
        Nome seguro para usar como nome de arquivo.
    """
    # Remove caracteres inválidos em nomes de arquivo
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)

    # Substitui espaços e hífens múltiplos por underscore
    safe = re.sub(r'[\s\-]+', '_', safe)

    # Remove underscores no início e no final
    safe = safe.strip('_')

    # Limita o tamanho para evitar paths muito longos
    if len(safe) > 80:
        safe = safe[:80]

    # Garante que não está vazio
    return safe or "audio"
