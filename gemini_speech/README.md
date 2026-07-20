# gemini_speech — standalone Gemini multi-speaker TTS renderer

A self-contained experiment for rendering the SZZ two-speaker transcripts with
**Gemini TTS** (native multi-speaker dialogue). Fully independent of `szzpod`
(ElevenLabs) and `azure_speech` — it only reads `../transcripts/*.txt` read-only and
writes its own `audio/` and `.cache/`.

## Why

Gemini `gemini-2.5-flash-preview-tts` renders a genuine two-speaker conversation in
one call (Slovak supported, `sk` auto-detected), is prompt-steerable for tone, and is
the closest cheap option to ElevenLabs v3 quality — with a **free tier** to try it.
Rough cost past the free tier is ~$0.30 per 20-min episode vs. ~$2 on ElevenLabs.

## Setup

```bash
cd gemini_speech
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add GEMINI_API_KEY from https://aistudio.google.com/apikey
```

Requires `ffmpeg` on PATH.

## Usage

```bash
./run list
./run tts Q26_casova_a_pametova_slozitost_vyklad
./run reassemble Q26_casova_a_pametova_slozitost_vyklad   # rebuild from cache, no API
```

Output: `audio/<name>.mp3`. Chunks are cached as WAV in `.cache/<name>/`, so a rerun
after a rate limit only fetches what is missing.

## How it works

1. **Parse** the transcript into `Person1/Person2` turns (`transcript.py`).
2. **Chunk** turns to `max_chars_per_request` (`transcript.py`).
3. **Synthesize** each chunk with one `generateContent` call: the turns become a
   labeled conversation prompt and both speakers bind to Gemini prebuilt voices via
   `multiSpeakerVoiceConfig`. The base64 PCM response is wrapped to WAV and cached
   (`synth.py`).
4. **Assemble**: concatenate chunks, optional whole-episode `loudnorm` + master
   (`audio.py`).

## Configuration

See `config.yaml`: model, per-speaker `alias` + prebuilt `voice`, a natural-language
`style_prompt` (Gemini has no SSML — tone is steered by the prompt), chunk size,
output encoding, and mastering toggles.

## Notes / limits

- **Free tier rate limits are low** (a few requests per minute/day). An episode is a
  handful of chunks; caching + rerun handles 429s gracefully. For all ~40 episodes,
  move to the paid tier (still ~$0.30/episode).
- **Multiple keys / rotation.** Supply several keys and the renderer switches to the
  next one immediately on a 429 (only backing off once *all* keys are rate-limited),
  which stretches the free tier across accounts. List them comma-separated in
  `GEMINI_API_KEY` or as `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`, ... The key(s) may
  live in this folder's `.env` or the repo-root `.env` (read as a fallback).
- Multi-speaker supports **exactly 2 speakers** — matches this use case.
- No R2 upload / note embedding here; that stays in the `szzpod` workflow.
