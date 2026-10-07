# Run VDO on GitHub

VDO now has a second execution mode: run the complete documentary agent from GitHub Actions.

## 1. GitHub-hosted mode

The repository is public, so the workflow can use GitHub's standard hosted runner. GitHub currently documents standard GitHub-hosted runners as free and unlimited for public repositories.

Use:

1. Open **Actions** in the VDO repository.
2. Select **VDO Documentary Runner**.
3. Click **Run workflow**.
4. Enter one-line **topic** and **minutes**.
5. Select **github** as the runner.
6. Download the **vdo-documentary** artifact when the job finishes.

The production intro workflow is intentionally deterministic and CPU-friendly: Kokoro narration, Wikimedia Commons media, FFmpeg rendering, faster-whisper captions and a local ambient bed. Full documentary mode can still use Ollama/Qwen3 on a larger self-hosted runner.

## 2. Self-hosted open-source mode

Select **self-hosted** in the same workflow after registering a GitHub Actions self-hosted runner.

This is the preferred mode for longer documentaries, larger local models, GPU acceleration, larger media caches and high-throughput production. GitHub does not charge for self-hosted runner execution; you provide the machine.

Recommended production machine:
- Linux
- 16+ GB RAM
- 4+ CPU cores
- SSD
- NVIDIA GPU optional for faster local inference

The software stack remains open-source/local:
- Qwen3 + Ollama
- Piper
- faster-whisper
- FFmpeg
- Wikimedia Commons
- Python / FastAPI

## Notes

GitHub-hosted runners are ephemeral, so model and media caches are restored only when the GitHub cache is available. Self-hosted runners can keep models and media locally between jobs.

For public distribution, verify the license of every Wikimedia Commons asset and every voice model used in the final documentary.


## Production intro quality build

The repository includes **VDO Production Intro Quality** at `.github/workflows/vdo-production-intro.yml`. It is a repeatable benchmark for the product demo, not a hosted AI-video dependency.

The workflow installs the open local stack, renders `python main.py --intro`, verifies the resulting media with `scripts/quality_check.py`, and uploads the MP4 plus the evidence files.

This makes the intro reproducible without a per-video hosted generation quota: render locally or on an eligible public/self-hosted GitHub Actions runner.
