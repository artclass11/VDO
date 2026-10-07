# Open-source model strategy

VDO is designed to run without a hosted video-generation API.

## Voice

**Qwen3-TTS** is the preferred GPU narrator. The upstream project is Apache-2.0 and supports instruction-controlled, natural documentary speech. citeturn253875search0turn253875search1

**Kokoro-82M** is the CPU-friendly default. Its weights are Apache-2.0 and its model is deliberately lightweight, making it suitable for repeated local rendering. citeturn162055search11

Piper remains an explicit legacy fallback only.

## Visuals

VDO prefers real moving archive footage and human B-roll for factual documentaries. Wikimedia Commons is the primary open-license source and the asset manifest records the source, author and reported license for later verification.

For locally generated filler shots where real footage is unavailable, **Wan2.1 T2V-1.3B** is the recommended optional open video model. The official Wan2.1 repository says the 1.3B T2V model is Apache-2.0 and requires about 8.19 GB VRAM for inference, making it one of the more practical local open video models for a consumer GPU. citeturn645051search1turn645051search2

VDO intentionally does not force generative video into every scene. Real footage is preferred where factual grounding matters.

## Render

FFmpeg performs the final edit, encoding, audio mix and subtitle burn-in. faster-whisper supplies local subtitle transcription.

The production intro can therefore be rendered repeatedly on a local machine or self-hosted runner without a per-video hosted-generation quota.
