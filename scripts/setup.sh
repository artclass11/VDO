#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

if command -v apt-get >/dev/null 2>&1; then
  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "FFmpeg is required. Install it with: sudo apt-get update && sudo apt-get install -y ffmpeg"
  fi
  if ! command -v espeak-ng >/dev/null 2>&1; then
    echo "Kokoro needs eSpeak-NG. Install it with: sudo apt-get update && sudo apt-get install -y espeak-ng"
  fi
fi

mkdir -p models outputs

if command -v ollama >/dev/null 2>&1; then
  ollama pull qwen3:8b
else
  echo "Ollama is not installed. Install Ollama, then run: ollama pull qwen3:8b"
fi


echo
echo "Setup complete."
echo "Default TTS: NVIDIA/CUDA -> Qwen3-TTS; CPU-only -> Kokoro. Piper is legacy-only."
echo "Piper is legacy and disabled unless VDO_ALLOW_PIPER_FALLBACK=1."
echo "Generate a documentary with:"
echo "  python main.py "The history of the global gold market" --minutes 10"
