"""
core/config.py — Configurações e constantes centralizadas
=========================================================
Ponto único de verdade (Single Source of Truth) para todas as
configurações do StemCraft.  Nenhum outro módulo deve redefinir
estas constantes — apenas importar daqui.
"""

from pathlib import Path

# ── Caminhos ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent   # raiz do projeto
TEMP_DIR   = BASE_DIR / ".tmp"              # arquivos intermediários (não versionados)
OUTPUT_DIR = BASE_DIR / "output"            # stems exportados (não versionados)
LOGS_DIR   = BASE_DIR / "logs"             # logs de execução  (não versionados)

# ── Modelo Demucs padrão ──────────────────────────────────────────────────────
DEFAULT_MODEL = "htdemucs_6s"

# Tupla: (id_interno, nome_display, descrição curta)
AVAILABLE_MODELS = [
    (
        "htdemucs_6s",
        "htdemucs_6s",
        "6 stems nativos  •  Guitarra e teclado incluídos",
    ),
    (
        "htdemucs_ft",
        "htdemucs_ft",
        "Alta qualidade vocal  •  + guitarra/teclado via 2ª passagem",
    ),
    (
        "mdx_extra_q",
        "mdx_extra_q",
        "Melhor voz  •  MDX 2021  •  + guitarra/teclado via 2ª passagem",
    ),
]

# ── Rótulos de stems (nome interno → label em português) ─────────────────────
STEM_LABELS: dict[str, str] = {
    "lead_vocals":    "Voz_Principal",
    "backing_vocals": "Voz_Backing",
    "vocals":         "Voz",
    "drums":          "Bateria",
    "bass":           "Baixo",
    "guitar":         "Guitarra",
    "piano":          "Piano",
    "other":          "Outros",
}

# Stems gerados pelo modelo de 6 canais
STEMS_6S = frozenset({"vocals", "drums", "bass", "piano", "guitar", "other"})
