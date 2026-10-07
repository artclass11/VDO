#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install -r requirements.txt
mkdir -p models outputs

if command -v ollama >/dev/null 2>&1; then
  ollama pull qwen3:8b
else
  echo "Ollama is not installed. Install Ollama, then run: ollama pull qwen3:8b"
fi

python3 -m piper.download_voices en_US-lessac-medium --data-dir ./models

echo
echo "Setup complete."
echo "Generate a documentary with:"
echo "  python main.py "The history of the global gold market" --minutes 10"
