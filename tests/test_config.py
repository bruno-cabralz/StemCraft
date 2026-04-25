"""
tests/test_config.py — Testes de sanidade das configurações
============================================================
Verifica que as constantes em core/config.py são válidas.
Execute com:  python -m pytest tests/
"""

import sys
from pathlib import Path

# Garante que o pacote stemcraft/ é encontrado ao rodar da raiz
sys.path.insert(0, str(Path(__file__).parent.parent))

from stemcraft.config import (
    BASE_DIR,
    TEMP_DIR,
    OUTPUT_DIR,
    DEFAULT_MODEL,
    AVAILABLE_MODELS,
    STEM_LABELS,
    STEMS_6S,
)


def test_base_dir_is_project_root():
    """BASE_DIR deve apontar para a raiz do projeto (onde fica gui.py)."""
    assert (BASE_DIR / "gui.py").exists(), f"gui.py não encontrado em BASE_DIR={BASE_DIR}"


def test_temp_and_output_are_inside_project():
    """TEMP_DIR e OUTPUT_DIR devem ser subpastas de BASE_DIR."""
    assert str(TEMP_DIR).startswith(str(BASE_DIR))
    assert str(OUTPUT_DIR).startswith(str(BASE_DIR))


def test_default_model_is_available():
    """DEFAULT_MODEL deve estar na lista AVAILABLE_MODELS."""
    ids = [m[0] for m in AVAILABLE_MODELS]
    assert DEFAULT_MODEL in ids, f"{DEFAULT_MODEL!r} não está em AVAILABLE_MODELS: {ids}"


def test_stem_labels_has_expected_keys():
    """STEM_LABELS deve conter todas as chaves principais."""
    required = {"vocals", "drums", "bass", "guitar", "piano", "other"}
    missing = required - set(STEM_LABELS.keys())
    assert not missing, f"STEM_LABELS está faltando: {missing}"


def test_stems_6s_subset_of_stem_labels():
    """Todos os stems do modelo 6S devem ter um label definido."""
    unlabeled = STEMS_6S - set(STEM_LABELS.keys())
    assert not unlabeled, f"Stems sem label: {unlabeled}"


def test_available_models_format():
    """Cada entrada de AVAILABLE_MODELS deve ser tupla de 3 strings."""
    for entry in AVAILABLE_MODELS:
        assert len(entry) == 3, f"Entrada inválida: {entry}"
        assert all(isinstance(s, str) for s in entry), f"Valores não-string: {entry}"
