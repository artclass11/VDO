# Open-source model strategy

VDO is designed to run without a hosted video-generation API.

## Voice

**Qwen3-TTS** is the preferred GPU narrator. The upstream project is Apache-2.0 and supports instruction-controlled, natural documentary speech.

VDO intentionally does not force generative video into every scene. Real footage is preferred where factual grounding matters.

## Render

FFmpeg performs the final edit, encoding, audio mix and subtitle burn-in. faster-whisper supplies local subtitle transcription.

The production intro can therefore be rendered repeatedly on a local machine or self-hosted runner without a per-video hosted-generation quota.
