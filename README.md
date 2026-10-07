# VDO — Open Documentary Maker

VDO turns one line of text into a complete documentary.

Example:

    python main.py "The rise of artificial intelligence" --minutes 10

The engine is local-first, resumable and designed around free/open-source software.
It researches the topic, builds a documentary structure, writes narration,
generates local neural voiceover, finds open-license/archive visuals, creates
cinematic motion from stills, assembles the film with FFmpeg, and produces
burned-in subtitles.

## What the first production release does

Input:
    one topic line

Pipeline:
    topic
      -> local research
      -> Qwen3 planning/script
      -> chapter and scene plan
      -> Piper narration
      -> Wikimedia Commons visual retrieval
      -> parallel asset download
      -> cinematic Ken Burns motion
      -> FFmpeg assembly
      -> faster-whisper subtitles
      -> final 1080p MP4

Every stage is resumable. Re-running the same topic reuses completed research,
media, audio and rendered scenes instead of starting again.

## Open-source stack

- Qwen3 + Ollama for local documentary planning and narration writing.
- Piper for fast local neural TTS.
- faster-whisper for subtitle transcription.
- FFmpeg for rendering, encoding and muxing.
- Wikimedia Commons for openly licensed archive imagery.
- Python, Pydantic, HTTPX, FastAPI and pytest.

Qwen3 open-weight models are Apache 2.0. The current piper-tts package is
GPL-3.0-or-later, while the older archived Piper repository was MIT; VDO uses
the current package for a simple cross-platform setup. Individual Piper voice
models have their own model-card licensing and must be checked before
redistribution. See each upstream project and asset record for exact terms.

## Fast setup

Linux/macOS:

    git clone https://github.com/artclass11/VDO.git
    cd VDO
    bash scripts/setup.sh

Start Ollama if it is not already running:

    ollama serve

Then:

    python main.py "The history of the global gold market" --minutes 10

Windows:

    py -m pip install -r requirements.txt
    py -m piper.download_voices en_US-lessac-medium --data-dir .\models
    ollama pull qwen3:8b
    py main.py "The history of the global gold market" --minutes 10

You must have FFmpeg available on PATH.

## Output

Each topic gets its own resumable job directory:

    outputs/<job-id>/
      documentary.json
      research.json
      media/
      audio/
      scenes/
      narration.wav
      captions.srt
      final/
        documentary_clean.mp4
        documentary.mp4
      job.json

The final file is:

    outputs/<job-id>/final/documentary.mp4

## Performance design

The expensive work is parallelized:

- multiple visual searches/downloads run concurrently;
- multiple Piper scene narrations run concurrently;
- completed artifacts are reused;
- image rendering is local and avoids waiting for hosted video-generation queues;
- FFmpeg uses a fast H.264 preset;
- subtitle transcription defaults to a CPU-friendly base model.

For stronger subtitle accuracy, set VDO_WHISPER_MODEL=small.
For NVIDIA GPUs, set VDO_WHISPER_DEVICE=cuda and choose an appropriate compute type.

The system deliberately prefers reliable archive imagery plus motion over
making every scene with a hosted text-to-video model. That is the main reason
long documentaries remain practical and restartable.

## Run fully from GitHub

VDO also includes a one-click GitHub Actions execution mode. Open **Actions → VDO Documentary Runner → Run workflow**, enter a one-line topic and duration, then choose:

- `github`: uses a standard GitHub-hosted runner for the complete pipeline.
- `self-hosted`: uses your own GitHub Actions runner, recommended for larger models, GPUs and longer documentaries.

The GitHub mode is tuned for a small Qwen3 model so a 1-minute sample can run within hosted CPU/storage limits. The generated MP4 and documentary metadata are uploaded as a workflow artifact.

See [docs/RUN_GITHUB.md](docs/RUN_GITHUB.md) for the setup and self-hosted configuration.

## API mode

Run:

    uvicorn server:app --host 0.0.0.0 --port 8000

Health:

    GET /health

Generate:

    POST /generate

Body:

    {
      "topic": "The history of space exploration",
      "minutes": 15
    }

The filesystem is the durable job store. A queue such as Redis/RQ can be added
later for multi-worker servers without changing the core pipeline.

## Asset licensing

VDO does not claim that every internet asset is automatically reusable.

For retrieved archive media, VDO stores the source page, author and reported
license in media metadata. Verify the individual Wikimedia Commons file
license and attribution requirements before publishing the finished film.

Do not automatically download or redistribute copyrighted footage from random
video platforms.

## Roadmap

- Real archive-video provider with size/codec-aware selection.
- Optional local generative image provider through ComfyUI.
- Optional local video generation provider.
- Background music provider with license tracking.
- Multi-language documentary translation.
- Shot-level fact checking.
- GPU worker pool and distributed queue.
- Browser dashboard.
- ChatGPT agent/plugin adapter.
- Direct integration with the MOV media repository.

## License

VDO application code is MIT licensed.

Third-party models, TTS packages, codecs, fonts and media can have different
licenses. Their own licenses remain authoritative.

## Status

Open-source production foundation. The local pipeline is designed to keep
working when a remote model or hosted generation service is unavailable.
