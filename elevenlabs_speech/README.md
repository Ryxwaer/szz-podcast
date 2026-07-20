# elevenlabs_speech — standalone ElevenLabs Text to Dialogue renderer

The default SZZ podcast renderer: turns a two-speaker transcript into audio with
**ElevenLabs Text to Dialogue** (`eleven_v3`). Self-contained like `gemini_speech`
and `azure_speech` — it reads `../transcripts/*.txt` read-only and writes the
episode to the shared repo-root `../audio/<name>.mp3`.

Selected by `backend: elevenlabs` in the repo-root `config.yaml`. Normally you run
it through the root dispatcher (`./szzpod tts <name>`); the commands below are for
direct/standalone use.

## Setup

```bash
cd elevenlabs_speech
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add ELEVENLABS_API_KEY
```

Requires `ffmpeg` on PATH.

## Usage

```bash
./run list
./run tts Q19_neuronove_site_strukturovana_data_vyklad
./run tts Q19_neuronove_site_strukturovana_data_vyklad --reassemble  # rebuild from cache, no API
./run reassemble Q19_neuronove_site_strukturovana_data_vyklad         # same, explicit
```

Output: `../audio/<name>.mp3`. Chunks are cached as mp3 (+ per-chunk
`voice_segments` JSON) in `.cache/<name>/`, so a rerun after a quota/rate limit only
fetches what is missing.

## How it works

1. **Parse** the transcript into `Person1/Person2` turns (`transcript.py`).
2. **Chunk** turns to `max_chars_per_request` (`transcript.py`).
3. **Synthesize** each chunk with one Text to Dialogue call (native voice
   alternation + prosody), cached by content hash (`tts.py`).
4. **Assemble**: per-speaker loudness leveling to `target_lufs`, concatenation, and
   an optional whole-episode mastering chain (`audio.py`).

## Configuration

See `config.yaml`: `model_id`, per-speaker `voices`, `language_code`, `output_format`,
chunk size, `seed`, and the mastering toggles (`normalize`, `target_lufs`, `dynamics`).

## Notes / limits

- No R2 upload / note embedding here; those stay in the root `szzpod` workflow
  (`./szzpod upload`), driven by the global repo-root `config.yaml`.
- Text to Dialogue supports **exactly 2 speakers** — matches this use case.
