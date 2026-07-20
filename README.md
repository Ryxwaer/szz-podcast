# SZZ podcast

Generátor audio podcastov na opakovanie okruhov k ústnej štátnej záverečnej
skúške (VUT FIT). Zo scenára (transcript) vznikne cez zvolený TTS backend audio s
dvoma hlasmi, nahrá sa na Cloudflare R2 a `./szzpod` **vráti verejnú URL**.
Prehrávač do poznámky vkladá orchestrujúci agent.

Nástroj je úzky: **scenár → audio → upload → URL**. Nehľadá poznámku, neodvodzuje
predmet ani nevkladá prehrávač - o tom všetkom rozhoduje agent (`name`, R2 kľúč,
embed). Dva audio súbory (výklad + otázky komisie) vyrobíš jednoducho dvoma behmi
s iným `name` a iným R2 kľúčom.

## Architektúra

- **Dispatcher** - wrapper `./szzpod`: `tts` posiela na TTS backend zvolený cez
  `backend:` v [config.yaml](config.yaml); `validate` + `upload` robí
  backend-agnostický balík `src/szzpod/` (bez stavového súboru).
- **TTS backendy** - každý samostatný, s vlastným `config.yaml` a `.env`:
  - `elevenlabs_speech/` - ElevenLabs Text to Dialogue (`eleven_v3`), default.
  - `gemini_speech/` - Gemini multi-speaker TTS.
  - `azure_speech/` - Azure neurónové hlasy.
  Všetky čítajú `transcripts/` a píšu do zdieľaného `audio/<name>.mp3`.
- **Agenti** (Cursor):
  - `transcript-writer` subagent (`.cursor/agents/`) - píše scenár v izolovanom kontexte.
  - `docs/writing-style.md` - zdieľané pravidlá písania scenára.
- **Runbook orchestrácie** - [AGENTS.md](AGENTS.md).

## Požiadavky

- Python 3.10+
- `ffmpeg` (skladanie audia, používajú backendy) - v systéme na `PATH`
- Node / `npx` + `wrangler` (upload na R2), prihlásený cez `npx wrangler login`
- API kľúč pre zvolený TTS backend (napr. ElevenLabs)


## Konfigurácia

1. **Globálne** (koreň): skopíruj `.env.example` na `.env` (`CLOUDFLARE_ACCOUNT_ID`
   pre R2). V [config.yaml](config.yaml) je len globálne: `backend`, zdieľané
   `paths` (vrátane `obsidian_szz`) a `r2`.

2. **Backend** (napr. `elevenlabs_speech/`): skopíruj jeho `.env.example` na `.env`
   a doplň API kľúč (napr. `ELEVENLABS_API_KEY`). Engine-specifické nastavenia
   (hlasy, model, `stability`, `seed`, mastering) sú v jeho `config.yaml`.

```bash
cp .env.example .env                         # CLOUDFLARE_ACCOUNT_ID
cp elevenlabs_speech/.env.example elevenlabs_speech/.env   # ELEVENLABS_API_KEY
```

## Použitie

Spúšťaj cez wrapper `./szzpod` z koreňa repozitára. `tts` ide na backend zvolený v
`config.yaml`; `validate`/`upload` beží cez `python -m szzpod.cli`. `name` je voľný
identifikátor artefaktu (žiadny vynútený formát); odporúčaná konvencia je
`Q{číslo}_{slug}_{cast}`. R2 kľúč zadávaš ty cez `--r2-key`.

```bash
# scenár napíše transcript-writer subagent -> transcripts/<name>.txt
./szzpod validate Q21_klasifikacia_jazykov_vyklad     # kontrola formátu (bez API)
./szzpod tts      Q21_klasifikacia_jazykov_vyklad     # audio (cache + zloženie)
./szzpod upload   Q21_klasifikacia_jazykov_vyklad --r2-key TIN/Q21_klasifikacia_jazykov_vyklad.mp3
```

`upload` vypíše na poslednom riadku **verejnú URL** - tú agent vloží do poznámky
ako `<audio controls src="…"></audio>`.

Druhý súbor (otázky komisie) je len ďalšia dvojica `tts` + `upload` s iným `name`
a R2 kľúčom (napr. `…_komisia`).

`./szzpod tts <name> --reassemble` len znova zloží audio z cachnutých chunkov bez
volania API (užitočné po zmene `target_lufs` / `normalize`).

## Znovuspustiteľnosť

Chunky audia sa cachujú podľa obsahu v `.cache/{name}/` **daného backendu** (napr.
`elevenlabs_speech/.cache/`). Po prerušení (napr. vyčerpaná kvóta) stačí `tts`
spustiť znova - dogeneruje len chýbajúce chunky. Žiadny stavový súbor sa nevedie.

## ElevenLabs MCP (voliteľné)

Pre prácu s ElevenLabs cez MCP (Cursor) slúži `scripts/run-elevenlabs-mcp.sh`,
ktorý načíta `.env` a spustí `uvx elevenlabs-mcp`.

## Štruktúra repozitára

```
szzpod                           dispatcher + CLI (./szzpod …, bez inštalácie)
config.yaml                      globálna konfigurácia (backend, paths, r2)
AGENTS.md                        runbook orchestrácie
docs/writing-style.md            pravidlá písania scenára
.cursor/agents/transcript-writer.md   subagent (scenár)
src/szzpod/                      backend-agnostický balík (validate + upload)
elevenlabs_speech/               TTS backend - ElevenLabs (default), vlastný config + .env
gemini_speech/                   TTS backend - Gemini, vlastný config + .env
azure_speech/                    TTS backend - Azure, vlastný config + .env
transcripts/                     scenáre (Person1:/Person2:), {name}.txt
audio/                           vygenerované mp3, zdieľané všetkými backendmi (mimo gitu)
archive/                         staré artefakty presunuté agentom (mimo gitu)
scripts/run-elevenlabs-mcp.sh    spúšťač ElevenLabs MCP
```
