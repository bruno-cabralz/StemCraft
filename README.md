# 🎛️ StemSplit VS

Gerador automático de multitracks profissionais a partir de qualquer vídeo do YouTube.

---

## O que o app faz

1. **Baixa o áudio** do YouTube em máxima qualidade
2. **Detecta o BPM e o tom** da música automaticamente
3. **Separa os instrumentos** em faixas individuais (Demucs 6 stems):
   - 🎤 Voz
   - 🥁 Bateria
   - 🎸 Baixo
   - 🎹 Piano / Teclado
   - 🎵 Guitarra
   - 🎼 Outros
4. **Gera o click track** sincronizado com o BPM real da música
5. **Gera a voz guia** em português com marcadores de seção:
   - Contagem antes da intro ("Um, Dois, Três, Quatro")
   - Anúncio de cada seção ("Introdução", "Versão", "Refrão", "Ponte", "Final")
6. **Exporta tudo** em WAV 24-bit organizados e prontos para a DAW

---

## Instalação

### Pré-requisitos

#### 1. Python 3.11 ou superior
- Baixe em: https://www.python.org/downloads/
- No terminal: `python --version` deve mostrar 3.11+

#### 2. ffmpeg
Necessário para conversão de áudio.

**Mac:**
```bash
brew install ffmpeg
```

**Windows:**
```bash
winget install ffmpeg
```
Ou baixe em https://ffmpeg.org/download.html e adicione ao PATH.

**Linux:**
```bash
sudo apt install ffmpeg
```

#### 3. PyTorch (necessário para o Demucs)
Acesse https://pytorch.org/get-started/locally/ e escolha sua configuração.

**Mac (Apple Silicon ou Intel):**
```bash
pip install torch torchaudio
```

**Windows/Linux com GPU NVIDIA:**
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**Windows/Linux sem GPU:**
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### Instalação das dependências Python

Na pasta do projeto:
```bash
pip install -r requirements.txt
```

---

## Como usar

```bash
python main.py
```

O app vai pedir o link do YouTube e processar tudo automaticamente.

### Exemplo de saída

```
output/Never_Gonna_Give_You_Up/
  ├── 00_VOZ_GUIA.wav          ← voz guia com anúncios de seção
  ├── 01_CLICK_113bpm.wav      ← metrônomo sincronizado
  ├── 02_Voz.wav
  ├── 03_Bateria.wav
  ├── 04_Baixo.wav
  ├── 05_Piano.wav
  ├── 06_Guitarra.wav
  ├── 07_Outros.wav
  └── INFO.txt                 ← BPM, tom, estrutura da música
```

---

## Como usar na DAW

1. Abra um projeto novo no **Ableton Live**, **Pro Tools**, ou **Reaper**
2. Configure o BPM do projeto para o valor indicado no `INFO.txt`
3. Arraste todos os WAVs para trilhas separadas
4. Roteamento recomendado para shows ao vivo:
   - `VOZ_GUIA` + `CLICK` → **IEM do músico** (monitor in-ear)
   - Stems → **mesa de som principal**

---

## Tempo estimado de processamento

| Etapa            | Tempo (música de 4 min) |
|------------------|------------------------|
| Download         | 10–30 segundos         |
| Análise BPM/Tom  | 20–40 segundos         |
| Demucs (CPU)     | 5–15 minutos           |
| Demucs (GPU)     | 30–90 segundos         |
| Click + Voz guia | 30–60 segundos         |
| Exportação       | 5–10 segundos          |

> 💡 **Dica:** Com uma GPU NVIDIA, o Demucs é ~10x mais rápido.

---

## Estrutura do projeto

```
StemSplit/
  ├── main.py              ← ponto de entrada, orquestra todo o fluxo
  ├── requirements.txt     ← dependências Python
  ├── core/
  │   ├── downloader.py    ← download do YouTube (yt-dlp)
  │   ├── analyzer.py      ← BPM, tom e detecção de seções (librosa)
  │   ├── separator.py     ← separação de stems (Demucs)
  │   ├── click_track.py   ← geração do metrônomo sincronizado
  │   ├── guide_voice.py   ← geração da voz guia (edge-tts)
  │   ├── exporter.py      ← organização e exportação dos arquivos
  │   └── utils.py         ← constantes e helpers compartilhados
  ├── output/              ← stems exportados (gerado automaticamente)
  └── .tmp/                ← arquivos temporários (gerado automaticamente)
```

---

## Problemas comuns

**"yt-dlp não encontrado"**
→ Instale com `pip install yt-dlp` ou `brew install yt-dlp`

**"ffmpeg não encontrado"**
→ Instale o ffmpeg e certifique-se que está no PATH do sistema

**"Demucs demorou muito"**
→ Normal em CPU. Considere rodar com GPU ou deixar rodando em segundo plano.

**"edge-tts falhou"**
→ Requer conexão com internet para a primeira síntese. Verifique sua conexão.

**A separação ficou com qualidade ruim**
→ O modelo `htdemucs_6s` tem melhor resultado em músicas com instrumentação clara. Músicas com muita reverb ou produção densa podem ter resultado inferior.

---

## Licenças

- **Demucs**: MIT License — Facebook Research
- **yt-dlp**: Unlicense — open source
- **edge-tts**: uso gratuito para fins não comerciais
- **librosa**: ISC License

> ⚠️ Respeite os direitos autorais. Use apenas para prática musical pessoal.
