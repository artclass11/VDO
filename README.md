# OpenDocu-AI 🎬🤖

**Zero-Cost, Fully Automated AI Documentary Generator**

Transform any topic into a professional-quality video documentary with AI-generated narration, synchronized captions, automated b-roll generation, and background music—all using 100% free and open-source tools.

---

## 🎯 Project Overview

OpenDocu-AI is a complete CLI and API pipeline that:
- Takes a single topic string (e.g., "The History of Wall Street")
- Generates a structured documentary script with timed chapters
- Synthesizes professional voiceover narration
- Generates synchronized SRT subtitles
- Creates AI-generated visual b-roll
- Composes everything into a polished MP4 documentary

**Total Cost:** $0 (all tools are free and open-source)

---

## 🛠️ Technology Stack

### Core Components
- **Language:** Python 3.10+
- **Script Generation:** Ollama (Llama 3 / DeepSeek) or OpenRouter free tier
- **Text-to-Speech:** edge-tts or Kokoro-TTS
- **Subtitle Generation:** faster-whisper
- **Video B-Roll Generation:** Gradio Client → Hugging Face Spaces (FLUX.1, LTX-Video, Wan 2.2)
- **Video Composition:** FFmpeg CLI

### Python Dependencies
```
gradio-client>=0.8.0
faster-whisper>=1.0.0
edge-tts>=6.1.0
requests>=2.31.0
pydantic>=2.0.0
rich>=13.0.0
tqdm>=4.66.0
httpx>=0.24.0
```

---

## 📁 Repository Structure

```
OpenDocu-AI/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container setup
├── docker-compose.yml        # Multi-container orchestration
├── config.py                 # Global configuration
├── main.py                   # CLI entry point
│
├── modules/
│   ├── __init__.py
│   ├── scriptwriter.py       # Script & shotlist generator
│   ├── audio.py              # TTS & subtitle generation
│   ├── visuals.py            # B-roll generation via HF Spaces
│   ├── composer.py           # FFmpeg video stitching
│   └── logger.py             # Logging utilities
│
├── outputs/                  # Generated files (gitignored)
│   ├── scripts/
│   ├── audio/
│   ├── subtitles/
│   ├── visuals/
│   └── final/
│
└── .gitignore
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- FFmpeg installed (`brew install ffmpeg` or `apt-get install ffmpeg`)
- Docker (optional, for containerized setup)

### Local Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/artclass11/VDO.git
   cd VDO
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure settings** (optional):
   - Edit `config.py` to set API endpoints, output directories, or voice preferences
   - Default settings work out-of-the-box with free tier APIs

5. **Generate your first documentary:**
   ```bash
   python main.py --topic "The History of Wall Street" --length-minutes 10 --output-dir ./outputs
   ```

### Docker Setup (Recommended)

```bash
docker-compose up --build
```

This handles FFmpeg and all dependencies automatically.

---

## 📖 Usage

### CLI Command

```bash
python main.py \
  --topic "Your Documentary Topic" \
  --length-minutes 15 \
  --output-dir ./outputs \
  --voice-model edge-tts \
  --language en-US
```

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--topic` | string | **required** | Documentary subject |
| `--length-minutes` | int | 10 | Target documentary length |
| `--output-dir` | path | `./outputs` | Output directory for files |
| `--voice-model` | string | `edge-tts` | TTS engine (`edge-tts` or `kokoro`) |
| `--language` | string | `en-US` | Narration language code |
| `--skip-audio` | flag | - | Skip TTS (use existing audio) |
| `--skip-visuals` | flag | - | Skip b-roll generation |
| `--num-workers` | int | 4 | Parallel b-roll generation workers |

### Example Output Structure

After running, your `outputs/` directory will contain:

```
outputs/
├── final/
│   └── documentary_20241007_152314.mp4  ✅ Final video
├── scripts/
│   └── script_20241007_152314.json      # Generated script
├── audio/
│   └── narration_20241007_152314.wav
├── subtitles/
│   └── subtitles_20241007_152314.srt
└── visuals/
    ├── scene_001_keyframe.png
    ├── scene_001_video.mp4
    ├── scene_002_keyframe.png
    └── ...
```

---

## 🔧 Pipeline Architecture

```
Topic Input
    ↓
┌─────────────────────────────────────┐
│ 1. Script Generation (scriptwriter) │  Ollama/LLM
│    - Generate chapters              │  → JSON script
│    - Create visual prompts           │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 2. Audio Generation (audio.py)       │  edge-tts/Kokoro
│    - TTS narration                   │  → WAV file
│    - Align timestamps                 │  → SRT captions
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 3. Visual Generation (visuals.py)    │  Gradio Client
│    - Query HF Spaces                  │  → MP4 + PNG assets
│    - Retry failed requests            │
│    - Download b-roll                  │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 4. Video Composition (composer.py)   │  FFmpeg
│    - Concatenate clips                │  → Final MP4
│    - Burn subtitles                   │
│    - Mix audio layers                 │
│    - Add background music             │
└─────────────────────────────────────┘
    ↓
✅ Documentary.mp4
```

---

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# API Endpoints
OLLAMA_API_URL = "http://localhost:11434"  # Local Ollama
OPENROUTER_API_KEY = ""  # Optional: for cloud inference

# TTS Settings
TTS_ENGINE = "edge-tts"  # or "kokoro"
TTS_VOICE = "en-US-AriaNeural"
TTS_RATE = 1.0

# Video Generation
VIDEO_RESOLUTION = "1920x1080"
VIDEO_FPS = 30
VIDEO_BITRATE = "8000k"
MAX_SCENE_DURATION = 5  # seconds per scene

# Output
OUTPUT_DIR = "./outputs"
KEEP_INTERMEDIATE_FILES = False
```

---

## 🎬 Free Video Generation APIs (Hugging Face Spaces)

OpenDocu-AI integrates with free Hugging Face Spaces:

- **FLUX.1** - High-quality image-to-video synthesis
- **LTX-Video** - Long-form video generation (up to 5 min)
- **Wan 2.2** - Fast, reliable video generation
- **Stable Diffusion XL** - Fallback image generation

No API keys required—Gradio Client handles authentication automatically.

---

## 🔐 Error Handling & Retry Logic

- **API Rate Limiting:** Automatic exponential backoff (3-30 second delays)
- **Failed B-Roll:** Graceful fallback to static images with Ken Burns effects
- **Network Issues:** Retry with increasing timeouts
- **Long Jobs:** Async background workers prevent UI freezing

All errors logged to `logs/` directory with full stack traces.

---

## 📊 Performance Considerations

| Component | Typical Time | Notes |
|-----------|--------------|-------|
| Script Generation | 2-3 min | Depends on LLM |
| Audio Generation | 1-2 min | Parallel processing |
| B-Roll Generation | 5-15 min | Per video (parallelized) |
| Video Composition | 3-5 min | FFmpeg CPU-bound |
| **Total** | **12-25 min** | For 10-min documentary |

---

## 🐳 Docker Deployment

### Single Container

```bash
docker build -t opendocu-ai .
docker run -it \
  -v $(pwd)/outputs:/app/outputs \
  opendocu-ai python main.py --topic "Your Topic"
```

### Docker Compose (Recommended)

```bash
docker-compose up
```

Includes:
- Python 3.10 + all dependencies
- FFmpeg pre-compiled
- Volume mounts for persistent outputs
- Health checks and logging

---

## 🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Code Standards
- Type hints on all functions
- Docstrings for modules and classes
- Unit tests for new modules
- Follow PEP 8 style guide

---

## 📝 License

This project is licensed under the MIT License—see the LICENSE file for details.

---

## ⚠️ Limitations & Future Work

### Current Limitations
- B-roll generation quality depends on prompt engineering
- Free tier APIs have rate limits (adjust `--num-workers` if hitting limits)
- Long documentaries (30+ min) may require splitting into episodes
- Music selection is currently randomized from free CC0 libraries

### Roadmap
- [ ] Web UI dashboard (Streamlit/Gradio)
- [ ] Custom music selection and licensing
- [ ] Multi-language support (auto-translate scripts)
- [ ] Scene-level style customization (documentary, educational, promotional)
- [ ] Real-time progress streaming
- [ ] S3/cloud storage integration
- [ ] Batch job scheduling

---

## 🆘 Troubleshooting

### FFmpeg not found
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (with Chocolatey)
choco install ffmpeg
```

### Ollama connection refused
Ensure Ollama is running:
```bash
ollama serve
# In another terminal:
ollama pull llama2  # or your preferred model
```

### Hugging Face Space timeout
- Increase `REQUEST_TIMEOUT` in `config.py`
- Reduce `--num-workers` to decrease concurrent requests
- Check Space status: https://huggingface.co/spaces

### API rate limit exceeded
Wait 1-2 hours or upgrade to a paid tier (not required for basic usage).

---

## 📞 Support & Community

- **Issues:** Report bugs on GitHub Issues
- **Discussions:** Share ideas and ask questions in Discussions
- **Email:** support@opendocu-ai.com (placeholder)

---

## 🙏 Acknowledgments

Built with:
- [Ollama](https://ollama.ai) - Local LLM inference
- [FFmpeg](https://ffmpeg.org) - Video composition
- [faster-whisper](https://github.com/openai/whisper) - Speech-to-text
- [edge-tts](https://github.com/rany2/edge-tts) - Text-to-speech
- [Gradio](https://gradio.app) - API client
- [Hugging Face](https://huggingface.co) - Model hosting

---

**Made with ❤️ for the open-source community**
