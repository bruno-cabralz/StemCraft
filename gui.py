"""
StemSplit VS - Interface Grafica Moderna
=========================================
Execute com:  python gui.py  (ou  .\\venv\\Scripts\\python gui.py)
"""

import sys
import os
import io
import queue
import threading
import subprocess
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

# Garante que os módulos core/ são encontrados
sys.path.insert(0, str(Path(__file__).parent))

# ── Tema global ────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Paleta de cores ────────────────────────────────────────────────────────────
BG       = "#0d0d12"   # fundo da janela
CARD     = "#15151d"   # fundo dos cards
BORDER   = "#272736"   # bordas e separadores
ACCENT   = "#7c3aed"   # roxo principal
ACCENT_H = "#6d28d9"   # roxo escuro (hover)
ACCENT_L = "#9f3cf7"   # roxo claro (active)
TEXT     = "#f0f0f5"   # texto principal
SUBTEXT  = "#7a7a99"   # texto secundário
INPUT_BG = "#1c1c28"   # fundo de campos
SUCCESS  = "#22d47a"   # verde sucesso
ERROR    = "#f05454"   # vermelho erro
INACTIVE = "#3a3a55"   # cinza inativo


# ── Modelos disponíveis ──────────────────────────────────────────────────────
MODELS = [
    ("htdemucs_6s", "htdemucs_6s", "6 stems nativos  •  Guitarra e teclado incluísos"),
    ("htdemucs_ft",  "htdemucs_ft",  "Alta qualidade vocal  •  + guitarra/teclado via 2ª passagem"),
    ("mdx_extra_q",  "mdx_extra_q",  "Melhor voz  •  MDX 2021  •  + guitarra/teclado via 2ª passagem"),
]

# ── Definição dos passos do pipeline ──────────────────────────────────────────
STEPS = [
    ("Download",       "Baixando o áudio do YouTube"),
    ("Análise",        "Detectando BPM, tom e seções"),
    ("Separação",      "Separando os instrumentos com Demucs"),
    ("Camadas Vocais", "Separando voz principal e backing vocal"),
    ("Click Track",    "Gerando o metrônomo sincronizado"),
    ("Exportação",     "Organizando os arquivos para a DAW"),
]


# ── Componente: linha de passo ─────────────────────────────────────────────────
class StepRow(ctk.CTkFrame):
    """Card de passo individual com indicador de estado animado."""

    def __init__(self, parent, index: int, title: str, desc: str, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._state = "idle"
        self._index = index
        self._title = title
        self._desc  = desc
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)

        # ── Ícone circular ─────────────────────────────────────────────────
        self.icon = ctk.CTkLabel(
            self,
            text=str(self._index + 1),
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=INACTIVE,
            width=34, height=34,
            fg_color=INPUT_BG,
            corner_radius=17,
        )
        self.icon.grid(row=0, column=0, rowspan=2, padx=(0, 16), pady=6, sticky="ns")

        # ── Título ─────────────────────────────────────────────────────────
        self.lbl_title = ctk.CTkLabel(
            self,
            text=self._title,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=INACTIVE,
            anchor="w",
        )
        self.lbl_title.grid(row=0, column=1, sticky="ew", pady=(6, 0))

        # ── Descrição / detalhe ────────────────────────────────────────────
        self.lbl_desc = ctk.CTkLabel(
            self,
            text=self._desc,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color=SUBTEXT,
            anchor="w",
        )
        self.lbl_desc.grid(row=1, column=1, sticky="ew", pady=(0, 2))

        # ── Barra de progresso indeterminada (oculta) ──────────────────────
        self.progress = ctk.CTkProgressBar(
            self, height=3, fg_color=BORDER, progress_color=ACCENT_L,
        )
        self.progress.set(0)

    def set_state(self, state: str, detail: str = ""):
        """Atualiza o visual do passo. state: 'idle' | 'active' | 'done' | 'error'"""
        self._state = state

        if state == "idle":
            self.icon.configure(text=str(self._index + 1), text_color=INACTIVE, fg_color=INPUT_BG)
            self.lbl_title.configure(text_color=INACTIVE)
            self.lbl_desc.configure(text=self._desc, text_color=SUBTEXT)
            self.progress.grid_forget()
            self.progress.stop()

        elif state == "active":
            self.icon.configure(text="◉", text_color=ACCENT_L, fg_color="#1e1228")
            self.lbl_title.configure(text_color=TEXT)
            self.lbl_desc.configure(text=self._desc, text_color=SUBTEXT)
            self.progress.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 4))
            self.progress.configure(mode="indeterminate", progress_color=ACCENT_L)
            self.progress.start()

        elif state == "done":
            self.progress.stop()
            self.progress.grid_forget()
            self.icon.configure(text="✓", text_color=SUCCESS, fg_color="#0d2a1c")
            self.lbl_title.configure(text_color=TEXT)
            self.lbl_desc.configure(
                text=detail if detail else self._desc,
                text_color=SUCCESS,
            )

        elif state == "error":
            self.progress.stop()
            self.progress.grid_forget()
            self.icon.configure(text="✕", text_color=ERROR, fg_color="#2a0d0d")
            self.lbl_title.configure(text_color=ERROR)
            self.lbl_desc.configure(
                text=detail[:90] if detail else "Erro durante o processamento",
                text_color=ERROR,
            )


# ── Janela principal ───────────────────────────────────────────────────────────
class StemSplitApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("StemSplit VS")
        self.geometry("740x900")
        self.minsize(660, 700)
        self.configure(fg_color=BG)

        # Ícone da janela (se existir)
        icon_path = Path(__file__).parent / "assets" / "icon.ico"
        if icon_path.exists():
            self.iconbitmap(str(icon_path))

        # Estado interno
        self._log_queue   = queue.Queue()
        self._processing  = False
        self._output_dir  = None
        self._current_step = -1

        self._build_ui()
        self._poll_log()  # inicia o ciclo de atualização do log

    # ── Construção da UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()
        self._build_body()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=76)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)
        header.grid_columnconfigure(0, weight=1)

        # Linha decorativa no topo
        accent_bar = ctk.CTkFrame(header, fg_color=ACCENT, height=3, corner_radius=0)
        accent_bar.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(
            header,
            text="StemSplit VS",
            font=ctk.CTkFont("Segoe UI", 22, "bold"),
            text_color=TEXT,
        ).grid(row=1, column=0, pady=(10, 2))

        ctk.CTkLabel(
            header,
            text="Gerador de Multitracks Profissional",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=SUBTEXT,
        ).grid(row=2, column=0, pady=(0, 10))

    def _build_body(self):
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=BG,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=INACTIVE,
        )
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        self._scroll = scroll

        r = 0

        # ── Card: URL ──────────────────────────────────────────────────────
        url_card = self._card(scroll, r); r += 1

        ctk.CTkLabel(
            url_card, text="Link do YouTube",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=TEXT, anchor="w",
        ).pack(fill="x", padx=24, pady=(20, 6))

        input_row = ctk.CTkFrame(url_card, fg_color="transparent")
        input_row.pack(fill="x", padx=24, pady=(0, 20))
        input_row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="https://www.youtube.com/watch?v=...",
            font=ctk.CTkFont("Segoe UI", 13),
            height=46,
            fg_color=INPUT_BG,
            border_color=BORDER,
            border_width=1,
            text_color=TEXT,
        )
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.url_entry.bind("<Return>", lambda _: self._start_processing())

        ctk.CTkButton(
            input_row, text="Colar", width=74, height=46,
            fg_color=INPUT_BG, hover_color=BORDER,
            text_color=SUBTEXT,
            border_width=1, border_color=BORDER,
            font=ctk.CTkFont("Segoe UI", 13),
            command=self._paste_url,
        ).grid(row=0, column=1)

        # ── Card: Modelo ───────────────────────────────────────────────────
        model_card = self._card(scroll, r); r += 1

        ctk.CTkLabel(
            model_card, text="Modelo de Separação",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=TEXT, anchor="w",
        ).pack(fill="x", padx=24, pady=(20, 12))

        self._model_var = ctk.StringVar(value=MODELS[0][1])

        for display, value, hint in MODELS:
            row_f = ctk.CTkFrame(model_card, fg_color="transparent")
            row_f.pack(fill="x", padx=24, pady=3)

            ctk.CTkRadioButton(
                row_f,
                text=display,
                variable=self._model_var,
                value=value,
                font=ctk.CTkFont("Segoe UI", 13, "bold"),
                text_color=TEXT,
                fg_color=ACCENT,
                hover_color=ACCENT_H,
            ).pack(side="left")

            ctk.CTkLabel(
                row_f, text=hint,
                font=ctk.CTkFont("Segoe UI", 11),
                text_color=SUBTEXT,
            ).pack(side="left", padx=(12, 0))

        ctk.CTkLabel(model_card, text="", height=8).pack()

        # ── Botão principal ────────────────────────────────────────────────
        btn_wrap = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_wrap.grid(row=r, column=0, padx=28, pady=(0, 4), sticky="ew")
        btn_wrap.grid_columnconfigure(0, weight=1)
        r += 1

        self.process_btn = ctk.CTkButton(
            btn_wrap,
            text="⚡   Processar Música",
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            height=54, corner_radius=12,
            fg_color=ACCENT, hover_color=ACCENT_H,
            command=self._start_processing,
        )
        self.process_btn.grid(row=0, column=0, sticky="ew")

        # ── Card: Progresso ────────────────────────────────────────────────
        steps_card = self._card(scroll, r); r += 1

        ctk.CTkLabel(
            steps_card, text="Progresso",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=TEXT, anchor="w",
        ).pack(fill="x", padx=24, pady=(20, 8))

        self.step_rows: list[StepRow] = []
        for i, (title, desc) in enumerate(STEPS):
            sr = StepRow(steps_card, i, title, desc)
            sr.pack(fill="x", padx=24, pady=3)
            self.step_rows.append(sr)

            if i < len(STEPS) - 1:
                ctk.CTkFrame(steps_card, fg_color=BORDER, height=1).pack(
                    fill="x", padx=24, pady=2
                )

        ctk.CTkLabel(steps_card, text="", height=8).pack()

        # ── Card: Console ──────────────────────────────────────────────────
        log_card = self._card(scroll, r); r += 1

        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=24, pady=(20, 8))

        ctk.CTkLabel(
            log_header, text="Console",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=TEXT,
        ).pack(side="left")

        ctk.CTkButton(
            log_header, text="Limpar", width=68, height=28,
            fg_color="transparent", hover_color=BORDER,
            text_color=SUBTEXT, border_width=1, border_color=BORDER,
            font=ctk.CTkFont("Segoe UI", 12),
            command=self._clear_log,
        ).pack(side="right")

        self.log_box = ctk.CTkTextbox(
            log_card, height=190,
            font=ctk.CTkFont("Consolas", 11),
            fg_color=INPUT_BG,
            text_color="#b0b4cc",
            border_width=1, border_color=BORDER,
            wrap="word",
        )
        self.log_box.pack(fill="x", padx=24, pady=(0, 20))
        self.log_box.configure(state="disabled")

        # ── Card: Resultado (oculto até concluir) ──────────────────────────
        self.result_card = self._card(scroll, r); r += 1
        self.result_card.grid_remove()

        ctk.CTkLabel(
            self.result_card,
            text="✓   Processamento Concluído!",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
            text_color=SUCCESS,
        ).pack(pady=(24, 4))

        self.result_subtext = ctk.CTkLabel(
            self.result_card, text="",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=SUBTEXT,
        )
        self.result_subtext.pack(pady=(0, 16))

        ctk.CTkButton(
            self.result_card,
            text="📁   Abrir Pasta de Saída",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            height=48, corner_radius=10,
            fg_color="#0d2a1c", hover_color="#1a4030",
            text_color=SUCCESS,
            border_width=1, border_color=SUCCESS,
            command=self._open_output_folder,
        ).pack(padx=28, pady=(0, 24), fill="x")

    def _card(self, parent, row: int) -> ctk.CTkFrame:
        f = ctk.CTkFrame(
            parent, fg_color=CARD,
            corner_radius=14,
            border_width=1, border_color=BORDER,
        )
        f.grid(row=row, column=0, sticky="ew", padx=28, pady=8)
        f.grid_columnconfigure(0, weight=1)
        return f

    # ── Ações da UI ────────────────────────────────────────────────────────────

    def _paste_url(self):
        try:
            text = self.clipboard_get().strip()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text)
        except Exception:
            pass

    def _start_processing(self):
        if self._processing:
            return

        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("URL vazia", "Cole o link do YouTube antes de continuar.")
            return

        self._processing   = True
        self._current_step = -1
        self._output_dir   = None
        self._model        = self._model_var.get()

        self.process_btn.configure(state="disabled", text="Processando...")
        self.result_card.grid_remove()

        for sr in self.step_rows:
            sr.set_state("idle")

        self._append_log(f"Iniciando pipeline para: {url}\n")
        threading.Thread(target=self._run_pipeline, args=(url,), daemon=True).start()

    # ── Pipeline (thread de background) ───────────────────────────────────────

    def _run_pipeline(self, url: str):
        """Executa todos os passos em background e enfileira mensagens de log."""

        def log(msg: str):
            self._log_queue.put(str(msg))

        def set_step(idx: int, state: str, detail: str = ""):
            self._current_step = idx
            self.after(0, lambda: self.step_rows[idx].set_state(state, detail))

        # Redireciona stdout para o log da GUI
        class _LogWriter(io.TextIOBase):
            def write(self_, s):
                if s.strip():
                    log(s)
                return len(s)

        _real_stdout = sys.stdout
        sys.stdout = _LogWriter()

        try:
            # ── 1. Download ────────────────────────────────────────────────
            set_step(0, "active")
            from core.downloader import download_audio
            audio_path = download_audio(url)
            set_step(0, "done", f"Salvo: {audio_path.name}")
            log(f"✓ Áudio salvo: {audio_path.name}")

            # ── 2. Análise ─────────────────────────────────────────────────
            set_step(1, "active")
            from core.analyzer import analyze_track
            track_info = analyze_track(audio_path)
            detail = (
                f"BPM: {track_info['bpm']:.1f}  •  "
                f"Tom: {track_info['key']}  •  "
                f"{len(track_info['sections'])} seções"
            )
            set_step(1, "done", detail)
            log(f"✓ {detail}")

            # ── 3. Separação de stems ──────────────────────────────────────
            set_step(2, "active")
            from core.separator import separate_stems, extract_guitar_piano
            stems = separate_stems(audio_path, model=self._model)
            # Se o modelo não gerou guitar/piano, faz 2ª passagem no stem "other"
            if "guitar" not in stems and "other" in stems:
                log("  → Extraindo guitarra/teclado via 2ª passagem (htdemucs_6s)...")
                extras = extract_guitar_piano(stems["other"])
                if extras:
                    stems.update(extras)
            stem_names = ", ".join(stems.keys())
            set_step(2, "done", f"Stems: {stem_names}")
            log(f"✓ Stems gerados: {stem_names}")

            # ── 4. Camadas vocais (lead / backing) ────────────────────────
            set_step(3, "active")
            from core.separator import separate_vocals_layers
            if "vocals" in stems:
                lead_path, backing_path = separate_vocals_layers(stems["vocals"])
                del stems["vocals"]
                stems["lead_vocals"] = lead_path
                if backing_path:
                    stems["backing_vocals"] = backing_path
                bck_msg = "+ backing" if backing_path else "sem backing"
                set_step(3, "done", f"Voz principal separada {bck_msg}")
            else:
                set_step(3, "done", "Pulado (sem faixa vocal)")
            log(f"✓ Camadas vocais processadas")

            # ── 5. Click track ─────────────────────────────────────────────
            set_step(4, "active")
            from core.click_track import generate_click_track
            click_path = generate_click_track(track_info, audio_path)
            set_step(4, "done", f"{int(round(track_info['bpm']))} BPM")
            log(f"✓ Click track gerado")

            # ── 6. Exportação ──────────────────────────────────────────────
            set_step(5, "active")
            from core.exporter import export_all
            output_dir = export_all(audio_path, stems, click_path, None, track_info)
            set_step(5, "done", f"output/{output_dir.name}")
            log(f"✓ Exportado em: {output_dir}")

            self._output_dir = output_dir
            self.after(0, self._on_success, output_dir)

        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            log(f"\n✕ Erro: {exc}\n{tb}")
            if self._current_step >= 0:
                detail = str(exc)[:90]
                idx = self._current_step
                self.after(0, lambda: self.step_rows[idx].set_state("error", detail))
            self.after(0, self._on_error)

        finally:
            sys.stdout = _real_stdout

    # ── Callbacks pós-pipeline ─────────────────────────────────────────────────

    def _on_success(self, output_dir: Path):
        self.result_subtext.configure(text=f"Arquivos em: output/{output_dir.name}")
        self.result_card.grid()
        self._processing = False
        self.process_btn.configure(state="normal", text="⚡   Processar Música")

    def _on_error(self):
        self._processing = False
        self.process_btn.configure(state="normal", text="⚡   Tentar Novamente")

    def _open_output_folder(self):
        if self._output_dir and self._output_dir.exists():
            subprocess.Popen(f'explorer "{self._output_dir}"')

    # ── Log em tempo real ──────────────────────────────────────────────────────

    def _poll_log(self):
        """Drena a fila de mensagens e atualiza o widget de texto a cada 100 ms."""
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self._append_log(msg)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

    def _append_log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text.rstrip("\n") + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")


# ── Ponto de entrada ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = StemSplitApp()
    app.mainloop()
