# azure_speech — standalone Azure AI Speech dialogue renderer

A self-contained experiment for rendering the SZZ two-speaker transcripts with
**Azure AI Speech** (neural TTS) instead of ElevenLabs. It is **fully independent**
of the `szzpod` tool — nothing here imports or modifies it. It reuses the existing
`../transcripts/*.txt` read-only and writes its own `audio/` and `.cache/`.

## Why

Azure `sk-SK` neural voices at **$16 / 1M chars** with a **500 000 chars/month free
tier** (F0) make a 20-min episode effectively free, vs. ~$2 on ElevenLabs v3. The
trade-off: no native two-speaker dialogue model and no custom cloned voices — each
turn is synthesized with a preset voice and the turns are concatenated.

## Setup

```bash
cd azure_speech
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in AZURE_SPEECH_KEY + AZURE_SPEECH_REGION
```

Requires `ffmpeg` on PATH (already used by the parent project).

Credentials come from the Azure Portal → your Speech resource → **Keys and
Endpoint**. The **Free F0** pricing tier is enough to try this.

## Usage

```bash
./run list                                   # show available transcripts
./run tts Q26_casova_a_pametova_slozitost_vyklad
./run reassemble Q26_casova_a_pametova_slozitost_vyklad   # rebuild from cache, no API
```

Output: `audio/<name>.mp3`. Chunks are cached in `.cache/<name>/`, so a rerun after
a rate-limit only fetches what is missing.

## How it works

1. **Parse** the transcript into `Person1/Person2` turns (`transcript.py`).
2. **Chunk** turns to `max_chars_per_request` (`transcript.py`).
3. **Synthesize** each chunk as one SSML document with alternating `<voice>` blocks
   via the Azure TTS REST endpoint, cached by content hash (`synth.py`).
4. **Assemble**: concatenate chunks, then optional whole-episode `loudnorm` to
   `target_lufs` + a gentle compressor/limiter master (`audio.py`).

## Configuration

See `config.yaml` — voices, language, prosody, pacing-tag break durations, chunk
size, output encoding, and mastering toggles. Two Slovak voices are available:
`sk-SK-LukasNeural` (male) and `sk-SK-ViktoriaNeural` (female).

## Not included (by design)

Upload to R2 and embedding the player into the Obsidian note remain the parent
`szzpod` workflow's job. This tool only produces the local mp3 for A/B comparison.
