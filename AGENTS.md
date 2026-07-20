# SZZ podcast - orchestrácia

Tento repozitár generuje audio podcasty na opakovanie okruhov k ústnej štátnej
záverečnej skúške (VUT FIT). Zo zdrojovej poznámky okruhu vznikne scenár, ten sa
cez ElevenLabs (`eleven_v3`, Text to Dialogue) prevedie na audio a nahrá na
Cloudflare R2. Prehrávač do poznámky vkladáš **ty (agent)**, nie program.

Tento súbor je **runbook pre hlavného agenta** (orchestrátora). Deterministickú
prácu robí wrapper `./szzpod` (CLI + dispatcher), kreatívnu prácu jeden subagent.

## Rozdelenie zodpovedností

- **Wrapper `./szzpod`** - jediné vstupné rozhranie s tromi príkazmi: `tts` (scenár
  → audio, s cache), `validate` (kontrola formátu) a `upload` (audio → R2 pod
  kľúčom, ktorý mu zadáš, **vráti verejnú URL**). `tts` posiela na zvolený TTS
  backend (viď nižšie); `validate`/`upload` robí backend-agnostický balík
  `src/szzpod/`. Nedrží žiadny stav, nepozná Obsidian, nehľadá poznámku,
  nearchivuje, nevkladá prehrávač.
- **TTS backendy** - každý je samostatný priečinok s vlastným `config.yaml` a
  `.env`: `elevenlabs_speech/` (default), `gemini_speech/`, `azure_speech/`.
- **Hlavný agent (ty)** - rozhoduje o všetkom okolo: nájde poznámku, zvolí `name`
  artefaktu aj **R2 kľúč**, spustí `szzpod`, dostane URL a **sám vloží prehrávač**
  do poznámky.
- **`transcript-writer` subagent** - krok 2, izolovaný kontext, píše iba scenár.
  Definícia: [.cursor/agents/transcript-writer.md](.cursor/agents/transcript-writer.md).
- **Štýl písania** (zdieľaný referenčný dokument): [docs/writing-style.md](docs/writing-style.md).

## Dve časti = dva súbory

Každý okruh má dve nezávislé časti, z ktorých vznikajú **dva audio súbory**:

- **výklad okruhu**,
- **otázky a odpovede komisie**.

Program o „častiach" nevie - sú to len dva samostatné behy s iným `name` a iným
R2 kľúčom. Výklad spravíš hneď, komisiu neskôr (keď ju máš pridelenú). Do poznámky
nakoniec vložíš dva prehrávače.

## Konvencia názvov (volíš ty)

`name` aj R2 kľúč si volíš sám; nie je vynútený žiadny formát. Odporúčaná konvencia:

- `name` artefaktu = `Q{číslo}_{slug}_{cast}`, napr. `Q21_klasifikacia_jazykov_vyklad`.
- R2 kľúč = `{PREDMET}/{name}.mp3`, napr. `TIN/Q21_klasifikacia_jazykov_vyklad.mp3`
  (predmet = priečinok, v ktorom je poznámka v Obsidiane).
- Lokálne: `transcripts/{name}.txt`, `audio/{name}.mp3`, cache `.cache/{name}/`.

## Spúšťanie `szzpod`

Nič sa **neinštaluje** - spúšťa sa lokálne z repozitára cez wrapper `./szzpod`
(z koreňa repa). Pre `validate`/`upload` si sám nastaví `PYTHONPATH=src` a zavolá
`python -m szzpod.cli`; pre `tts` spustí wrapper zvoleného backendu. Každá časť
číta svoj `.env` (koreňový pre R2, backendový pre TTS kľúč).

### Výber TTS backendu

Ktorý generátor renderuje audio, riadi jediný statický prepínač `backend:` v
**koreňovom** `config.yaml` (ten drží len globálne veci - `backend`, zdieľané
`paths`, `r2`). Engine-specifické nastavenia (hlasy, model, mastering, seed) sú vo
`config.yaml` daného backendu:

- `elevenlabs` (default) - `elevenlabs_speech/` (ElevenLabs Text to Dialogue),
- `gemini` - `gemini_speech/` (Gemini multi-speaker TTS),
- `azure` - `azure_speech/` (Azure neurónové hlasy).

Prepínač ovplyvňuje **len `./szzpod tts`** - wrapper podľa neho spustí zvolený
generátor. `./szzpod upload` a `./szzpod validate` bežia vždy cez balík `szzpod`
(sú backend-agnostické: R2 upload a kontrola formátu scenára nezávisia od enginu).
Každý backend zapíše epizódu do koreňového `audio/{name}.mp3`, takže kroky upload a
embed sú rovnaké bez ohľadu na backend. Ak chceš iný engine, zmeň `backend:` pred
krokom 2 a nechaj zvyšok pipeline nezmenený. (Každý backend má vlastný `.env` s
vlastným API kľúčom vo svojom priečinku.)

## Pipeline

```
0. archive      -> TY presunieš existujúce artefakty rovnakého name do archive/
1. transcript   -> deleguj na transcript-writer subagent    (1 súbor = 1 časť)
2. tts          -> ./szzpod tts <name>                       (generovanie + zloženie audia, cache)
3. upload       -> ./szzpod upload <name> --r2-key <kľúč>     (R2; vypíše URL)
4. embed        -> TY vložíš <audio> s vrátenou URL do poznámky
```

### Detailný postup (pre jednu časť)

0. **Archivácia (ty, pred tvorbou scenára).** Skôr než pre daný `name` spustíš
   `transcript-writer`, skontroluj, či už preň existujú artefakty:
   `transcripts/{name}.txt`, `audio/{name}.mp3`, `.cache/{name}/`. Ak áno, presuň
   ich do `archive/{name}-{YYYYMMDD-HHMMSS}/` (zachovaj štruktúru), aby si začal
   načisto a starú verziu nestratil. Ak nič neexistuje, krok preskoč.
1. **Scenár.** Deleguj na `transcript-writer` subagent. V prompte mu odovzdaj
   `name`, ktorú časť píše, cieľový súbor `transcripts/{name}.txt` a podklady (žiadne excesívne
   inštrukcie ani opakovanie pravidiel):
   - **výklad**: celý text zdrojovej poznámky,
   - **komisia**: relevantné riadky z CSV s otázkami komisie (cesta v `config.yaml`
     → `paths.questions_csv`); vyber riadky, kde stĺpce `Predmet` a `Okruh` sedia na
     okruh, prípadne pridaj aj výklad ako zdroj faktov pre odpovede.

   Subagent zapíše `transcripts/{name}.txt` a vráti jednoriadkové potvrdenie.
   (Voliteľne over formát: `./szzpod validate <name>`.)
2. **Audio.** `./szzpod tts <name>`. Chunky sa cachujú; pri vyčerpaní kvóty
   ElevenLabs príkaz zopakuj - dogeneruje len chýbajúce.
3. **Upload.** `./szzpod upload <name> --r2-key <PREDMET/name.mp3>` nahrá audio na
   R2 a **vypíše verejnú URL** (posledný riadok výstupu). Vyžaduje `npx wrangler login`.
4. **Embed (ty).** Vlož do zdrojovej poznámky prehrávač s vrátenou URL:
   `<audio controls src="<URL>"></audio>`. Vkladaj idempotentne (ak tam pre tú
   istú URL/súbor už je, neduplikuj). Pre dve časti budú v poznámke dva prehrávače.

## Dôležité

- **Cache chunkov** (v priečinku backendu, napr. `elevenlabs_speech/.cache/{name}/`)
  zabezpečí, že opakované `tts` dogeneruje len chýbajúce chunky. Seed je odvodený z
  `seed` v config.yaml daného backendu + `name`, takže je stabilný aj bez ukladania.
- Pred krokmi 2-3 musí existovať `transcripts/{name}.txt`.
- Tajomstvá: koreňový `.env` má `CLOUDFLARE_ACCOUNT_ID` (R2 upload); TTS kľúč je v
  `.env` daného backendu (napr. `elevenlabs_speech/.env` → `ELEVENLABS_API_KEY`).
- Setup a závislosti: [README.md](README.md).
