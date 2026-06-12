# StemCraft

> **Gerador automático de multitracks profissionais** a partir de qualquer vídeo do YouTube.  
> Separa os instrumentos em faixas individuais com IA, detecta BPM e tom, e entrega tudo pronto para sua DAW.  
> Inclui pipeline completo de fine-tuning do Demucs com dataset gospel próprio.

---

## Funcionalidades

| Recurso | Detalhe |
|---|---|
| Download do YouTube | Qualidade máxima via yt-dlp + ffmpeg |
| Detecção automática | BPM, tom musical e seções da música |
| Separacao de stems | Bateria, Baixo, Guitarra, Piano, Voz — via Demucs HTDemucs |
| Click Track | Metronomo sincronizado com o BPM real da faixa |
| Exportacao para DAW | WAV organizados e numerados prontos para importar |
| Interface grafica | GUI com tema escuro via customtkinter |
| Fine-tuning | Pipeline completo para treinar o Demucs com dataset proprio |

---

## Modelos disponíveis

| Modelo | Stems | Quando usar |
|---|---|---|
| `htdemucs_6s` *(padrão)* | Voz, Bateria, Baixo, Guitarra, Piano, Outros | Uso geral |
| `htdemucs_ft` | Voz, Bateria, Baixo, Outros | Prioridade na qualidade vocal |
| `mdx_extra_q` | Voz, Bateria, Baixo, Outros | Maximo isolamento de voz |
| modelo fine-tunado | igual ao htdemucs_6s | Gospel — treinado com 500+ multitracks |

---

## Requisitos

- **Python** 3.11 ou superior
- **ffmpeg** instalado no sistema (`winget install ffmpeg`)
- **7-Zip** para extrair RAR5 (`winget install 7zip.7zip`)
- **PyTorch** com CUDA (GPU NVIDIA recomendada — pelo menos 4 GB VRAM)

---

## Instalação

### 1. Clone o repositório

```bash
git clone https://github.com/bruno-cabralz/StemCraft.git
cd StemCraft
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv .venv

# Windows
.venv\Scripts\Activate.ps1

# Linux / Mac
source .venv/bin/activate
```

### 3. Instale o PyTorch com CUDA

```bash
# GPU NVIDIA (CUDA 12.4):
pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu124

# Sem GPU:
pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cpu
```

### 4. Instale as dependências do projeto

```bash
pip install -r requirements.txt
```

> Apos instalar o `audio-separator`, reinstale o PyTorch com o comando acima para garantir que o CUDA nao seja sobrescrito.

---

## Como usar

### Interface Grafica (recomendada)

```bash
python gui.py
```

1. Cole o link do YouTube no campo de URL
2. Escolha o modelo de separacao
3. Clique em **Processar Musica**
4. Acompanhe o progresso em tempo real
5. Clique em **Abrir Pasta de Saida** ao concluir

### Linha de Comando

```bash
python main.py
```

### Exemplo de saida

```
output/Nome_da_Musica/
  00_CLICK_120bpm.wav
  01_Voz.wav
  02_Bateria.wav
  03_Baixo.wav
  04_Guitarra.wav
  05_Piano.wav
  06_Outros.wav
```

---

## Tempo estimado (musica de 4 min)

| Etapa | GPU RTX 3060 | CPU |
|---|---|---|
| Download | 15–30s | 15–30s |
| Analise BPM/Tom | 20–40s | 20–40s |
| Separacao Demucs | ~60s | 8–15 min |
| Click Track + Exportacao | ~15s | ~15s |

---

## Pipeline de Fine-tuning

Para especializar o modelo em musica gospel, o projeto inclui scripts completos de preparacao de dataset e treinamento.

### Estrutura esperada do dataset bruto

```
dataset_raw/
  ARTISTA/
    musica.zip   <- stems individuais compactados
    musica.rar
```

Suporta `.zip`, `.rar` (incluindo RAR5), `.7z` e arquivos aninhados.  
Suporta `.wav`, `.mp3`, `.flac`, `.m4a`, `.wma`, `.aif`.

### Passo 1 — Preparar o dataset

```bash
python scripts/prepare_dataset.py --drive "F:\dataset_raw" --out "F:\dataset" --valid-ratio 0.1
```

O script faz automaticamente:
- Extrai os arquivos comprimidos
- Normaliza nomes dos stems (`EG 1.wav` -> `guitar.wav`, `Choir.wav` -> `backing_vocals.wav`, etc.)
- Descarta clicks, guides, resource forks do macOS (`._*`), mixdowns completos
- Gera `mixture.wav` somando todos os stems
- Divide em `train/` (90%) e `valid/` (10%)

| Argumento | Padrao | Descricao |
|---|---|---|
| `--drive` | obrigatorio | Pasta raiz com os multitracks |
| `--out` | `./dataset` | Pasta de saida |
| `--valid-ratio` | `0.1` | Proporcao de validacao |
| `--analyze-only` | — | So escaneia, sem extrair |

### Passo 2 — Treinar

```bash
# Dry-run: ver configuracao sem executar
python scripts/train_demucs.py --dataset "F:\dataset" --dry-run

# Fine-tuning a partir do htdemucs_6s pre-treinado (recomendado)
python scripts/train_demucs.py --dataset "F:\dataset" --mode finetune --batch-size 4 --num-workers 2 --epochs 100
```

| Argumento | Padrao | Descricao |
|---|---|---|
| `--mode` | `finetune` | `finetune` (rapido) ou `scratch` (do zero) |
| `--batch-size` | auto pela VRAM | 4 para 12 GB, 2 para 6–8 GB |
| `--num-workers` | `4` | Workers de dados; use `2` se usar o PC durante o treino |
| `--epochs` | `100` | Epocas de treinamento |

Checkpoints sao salvos a cada 5 epocas em `outputs/`. Para pausar: `Ctrl+C`. Para retomar: rode o mesmo comando novamente.

### Passo 3 — Usar o modelo treinado

Edite `stemcraft/config.py`:

```python
DEFAULT_MODEL = "outputs/htdemucs-abc1234"  # nome da pasta gerada em outputs/
```

A partir dai o `main.py` e a GUI usam o modelo fine-tunado automaticamente.

---

## Estrutura do projeto

```
StemCraft/
  gui.py                    <- Interface grafica (customtkinter)
  main.py                   <- Interface CLI
  pyproject.toml
  requirements.txt
  stemcraft/                <- Pacote principal
    config.py               <- Constantes centralizadas
    analyzer.py             <- Deteccao de BPM, tom e secoes
    downloader.py           <- Download do YouTube (yt-dlp)
    separator.py            <- Separacao de stems (Demucs)
    click_track.py          <- Geracao do metronomo
    exporter.py             <- Organizacao e exportacao dos arquivos
    utils.py                <- Helpers compartilhados
  scripts/
    prepare_dataset.py      <- Preparador de dataset para fine-tuning
    train_demucs.py         <- Treinamento / fine-tuning do Demucs
    download_gdrive.py      <- Download de pastas do Google Drive
    post_download.py        <- Extracao e normalizacao pos-download
    scan_stems.py           <- Escaneia stems sem extrair
  tests/
    test_config.py
  assets/
```

---

## Problemas comuns

**"ffmpeg nao encontrado"**  
Instale com `winget install ffmpeg` e reinicie o terminal.

**"Cannot find working tool" ao extrair .rar**  
Instale o 7-Zip: `winget install 7zip.7zip`

**"OOM / Out of Memory" durante o treino**  
Reduza o batch size: `--batch-size 2`

**"Demucs demorou muito"**  
Normal em CPU. Com RTX 3060 a separacao de uma musica de 4 min leva ~60 segundos.

**"audio-separator quebrou o CUDA"**  
Reinstale o PyTorch apos instalar as dependencias:  
`pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu124`

---

## Tecnologias

- [Demucs](https://github.com/facebookresearch/demucs) — separacao de fontes de audio com IA
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — download de audio do YouTube
- [librosa](https://librosa.org/) — analise de audio (BPM, tom)
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — interface grafica moderna
- [PyTorch](https://pytorch.org/) — inferencia neural com GPU
- [pydub](https://github.com/jiaaro/pydub) — conversao de formatos de audio via ffmpeg
- [soundfile](https://python-soundfile.readthedocs.io/) — leitura e escrita de WAV/FLAC

---

## Direitos Autorais

© 2026 Bruno Cabral. Todos os direitos reservados.

Este software e propriedade intelectual do autor. E expressamente proibida a copia, redistribuicao, modificacao ou uso comercial sem autorizacao previa por escrito.

> Desenvolvido para musicos e produtores gospel.
