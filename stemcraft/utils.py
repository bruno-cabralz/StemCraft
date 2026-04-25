"""
core/utils.py — Helpers de terminal e funções utilitárias
=========================================================
Funções auxiliares compartilhadas por todos os módulos.
Constantes e caminhos vivem em core/config.py.
"""

import re

# Re-exporta as constantes de config para manter compatibilidade com imports
# existentes do tipo: from .utils import TEMP_DIR, OUTPUT_DIR, STEM_LABELS
from .config import (  # noqa: F401
    BASE_DIR,
    TEMP_DIR,
    OUTPUT_DIR,
    STEM_LABELS,
)


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
