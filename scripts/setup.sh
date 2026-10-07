#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install -r requirements.txt
mkdir -p models outputs

if command -v ollama >/dev/null 2>&1; then
  ollama pull qwen3:8b
else
  echo "Ollama is not installed. Install Ollama, then run: ollama pull qwen3:8b"
fi


echo
echo "Setup complete."
echo "Default TTS: NVIDIA/CUDA -> Qwen3-TTS 1.7B; CPU-only -> Kokoro."
echo "Piper is legacy and disabled unless VDO_ALLOW_PIPER_FALLBACK=1."
echo "Generate a documentary with:"
echo "  python main.py "The history of the global gold market" --minutes 10"
