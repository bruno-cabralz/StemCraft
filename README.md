# 🎛️ StemCraft

> **Gerador automático de multitracks profissionais** a partir de qualquer vídeo do YouTube.  
> Separa os instrumentos em faixas individuais com IA, detecta BPM e tom, e entrega tudo pronto para sua DAW.

---

## Funcionalidades

| Recurso | Detalhe |
|---|---|
| 📥 Download do YouTube | Qualidade máxima via yt-dlp |
| 🔍 Detecção automática | BPM, tom musical e seções da música |
| 🎛️ Separação de stems | Bateria, Baixo, Guitarra, Piano, Voz — via Demucs 4 |
| 🎤 Voz principal + backing | Separação em duas camadas vocais independentes |
| 🥁 Click Track | Metrônomo sincronizado com o BPM real da faixa |
| 💾 Exportação para DAW | WAV 24-bit organizados e numerados |
| 🗂️ Preparador de dataset | Script para fine-tuning de modelos Demucs personalizados |

---

## Modelos disponíveis

| Modelo | Stems | Quando usar |
|---|---|---|
| `htdemucs_6s` *(padrão)* | Voz, Bateria, Baixo, Guitarra, Piano, Outros | Melhor para a maioria dos casos |
| `htdemucs_ft` | Voz, Bateria, Baixo, Outros + 2ª passagem | Prioridade na qualidade vocal |
| `mdx_extra_q` | Voz, Bateria, Baixo, Outros + 2ª passagem | Máximo isolamento de voz (MDX 2021) |

> Modelos de 4 stems executam automaticamente uma 2ª passagem com `htdemucs_6s` para extrair guitarra e piano do stem "outros".

---

## Requisitos

- **Python** 3.11 ou superior
- **ffmpeg** instalado no sistema e no PATH
- **PyTorch** (com CUDA para GPU NVIDIA — fortemente recomendado)
- GPU NVIDIA com pelo menos 4 GB de VRAM (ou CPU, mas será muito mais lento)

---

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/bruno-cabralz/StemCraft.git
cd StemCraft
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
```

### 3. Instale o PyTorch

**GPU NVIDIA (recomendado — CUDA 12.4):**
```bash
pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu124
```

**Sem GPU:**
```bash
pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cpu
```

### 4. Instale as dependências do projeto

```bash
pip install -r requirements.txt
```

---

## Como usar

### Interface Gráfica (recomendada)

```bash
python gui.py
```

1. Cole o link do YouTube no campo de URL
2. Escolha o modelo de separação
3. Clique em **⚡ Processar Música**
4. Acompanhe o progresso em tempo real
5. Clique em **📁 Abrir Pasta de Saída** ao concluir

### Linha de Comando (CLI)

```bash
python main.py
```

### Exemplo de saída

```
output/Nome_da_Musica/
  ├── 00_CLICK_120bpm.wav        ← metrônomo sincronizado
  ├── 01_Voz_Principal.wav
  ├── 02_Voz_Backing.wav
  ├── 03_Bateria.wav
  ├── 04_Baixo.wav
  ├── 05_Guitarra.wav
  ├── 06_Piano.wav
  └── 07_Outros.wav
```

---

## Tempo estimado de processamento

| Etapa | Tempo (música de 4 min) |
|---|---|
| Download | 10–30 segundos |
| Análise BPM/Tom | 20–40 segundos |
| Demucs (GPU — GTX 1650+) | 30–90 segundos |
| Demucs (CPU) | 5–15 minutos |
| Separação vocal (lead/backing) | 1–3 minutos |
| Click Track | 5–15 segundos |
| Exportação | 5–10 segundos |

> Com GPU NVIDIA o Demucs é ~10× mais rápido que em CPU.

---

## Preparação de Dataset (fine-tuning)

Script para processar multitracks do Google Drive e gerar um dataset compatível com fine-tuning do Demucs.

```bash
# Apenas escanear sem extrair
python prepare_dataset.py --drive "G:\Meu Drive\Multitracks" --analyze-only

# Preparar dataset completo
python prepare_dataset.py --drive "G:\Meu Drive\Multitracks" --out "D:\dataset"
```

| Argumento | Padrão | Descrição |
|---|---|---|
| `--drive` | obrigatório | Caminho raiz dos multitracks |
| `--out` | `./dataset` | Pasta de saída |
| `--analyze-only` | — | Apenas escaneia sem extrair |
| `--valid-ratio` | `0.1` | Proporção de validação (10%) |

---

## Estrutura do projeto

```
StemCraft/
  ├── gui.py               ← Interface gráfica (customtkinter)
  ├── main.py              ← Interface CLI
  ├── prepare_dataset.py   ← Preparador de dataset para treinamento
  ├── requirements.txt
  ├── core/
  │   ├── analyzer.py      ← Detecção de BPM, tom e seções
  │   ├── downloader.py    ← Download do YouTube (yt-dlp)
  │   ├── separator.py     ← Separação de stems (Demucs + audio-separator)
  │   ├── click_track.py   ← Geração do metrônomo
  │   ├── exporter.py      ← Organização e exportação dos arquivos
  │   └── utils.py         ← Constantes e helpers
  └── assets/              ← Ícones e recursos da interface
```

---

## Problemas comuns

**"ffmpeg não encontrado"**  
→ Instale com `winget install ffmpeg` (Windows) ou `brew install ffmpeg` (Mac) e reinicie o terminal.

**"Demucs demorou muito"**  
→ Normal em CPU. Use GPU ou deixe em segundo plano. Com GPU a separação de uma música de 4 min leva ~1 min.

**"audio-separator quebrou o PyTorch CUDA"**  
→ Reinstale o torch depois de instalar as dependências:  
`pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu124`

**"A separação ficou com qualidade ruim"**  
→ Tente o modelo `htdemucs_ft` para melhor qualidade vocal, ou `mdx_extra_q` para máximo isolamento.

---

## Tecnologias

- [Demucs](https://github.com/facebookresearch/demucs) — separação de fontes de áudio com IA
- [audio-separator](https://github.com/karaokenerds/python-audio-separator) — separação de voz principal e backing
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — download de áudio do YouTube
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — interface gráfica moderna
- [librosa](https://librosa.org/) — análise de áudio (BPM, tom)
- [PyTorch](https://pytorch.org/) — inferência neural com GPU

---

## Direitos Autorais

© 2026 Bruno Cabral. Todos os direitos reservados.

Este software é propriedade intelectual do autor. É **expressamente proibida** a cópia, redistribuição, modificação ou uso comercial sem autorização prévia por escrito.

> Desenvolvido para músicos e produtores gospel.
