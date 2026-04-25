"""
StemSplit VS — Ponto de entrada principal
==========================================
Execute este arquivo para processar uma música:
    python main.py

O script vai pedir o link do YouTube e cuidar de tudo:
  1. Download do áudio
  2. Detecção de BPM e tom
  3. Separação de stems (Demucs)
  4. Detecção de seções (intro, verso, refrão, etc.)
  5. Geração do click track
  6. Geração da voz guia sintetizada
  7. Exportação de todos os arquivos WAV organizados
"""

import sys
from pathlib import Path

# Garante que o Python encontra os módulos da pasta core/
sys.path.insert(0, str(Path(__file__).parent))

from core.downloader   import download_audio
from core.analyzer     import analyze_track
from core.separator    import separate_stems
from core.click_track  import generate_click_track
from core.exporter     import export_all
from core.utils        import print_banner, print_step, print_success, print_error


def main():
    print_banner()

    # ── 1. Recebe o link do YouTube ──────────────────────────────────────────
    url = input("\n🔗 Cole o link do YouTube: ").strip()
    if not url:
        print_error("Nenhum link fornecido. Encerrando.")
        sys.exit(1)

    try:
        # ── 2. Download ──────────────────────────────────────────────────────
        print_step(1, "Baixando áudio do YouTube...")
        audio_path = download_audio(url)
        print_success(f"Áudio salvo em: {audio_path}")

        # ── 3. Análise de BPM, tom e seções ─────────────────────────────────
        print_step(2, "Analisando BPM, tom e estrutura da música...")
        track_info = analyze_track(audio_path)
        print_success(
            f"BPM: {track_info['bpm']:.1f} | "
            f"Tom: {track_info['key']} | "
            f"Seções detectadas: {len(track_info['sections'])}"
        )

        # ── 4. Separação de stems com Demucs ─────────────────────────────────
        print_step(3, "Separando instrumentos (isso pode levar alguns minutos)...")
        stems = separate_stems(audio_path)
        print_success(f"Stems gerados: {', '.join(stems.keys())}")

        # ── 5. Click track ───────────────────────────────────────────────────
        print_step(4, "Gerando click track sincronizado...")
        click_path = generate_click_track(track_info, audio_path)
        print_success(f"Click track: {click_path}")

        # ── 6. Exportação final ───────────────────────────────────────────────
        print_step(5, "Organizando e exportando todos os arquivos...")
        output_dir = export_all(audio_path, stems, click_path, None, track_info)
        print_success(f"Projeto exportado em: {output_dir}")

        print("\n✅ Pronto! Arraste os WAVs para sua DAW e bora tocar! 🎛️\n")

    except KeyboardInterrupt:
        print("\n\nProcesso cancelado pelo usuário.")
        sys.exit(0)
    except Exception as e:
        print_error(f"Erro inesperado: {e}")
        raise  # mostra o traceback completo para debug


if __name__ == "__main__":
    main()
