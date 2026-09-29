# Nepali Number ASR

A browser-based speech-recognition app for Nepali number words. The frontend records audio in the browser, sends it to a FastAPI WebSocket backend, and displays the recognized number in Devanagari digits when it can be parsed. The model turns spoken numbers into digits in two stages: speech recognition (the ASR model) produces text, and number parsing (numerical_parser.py) turns that text into digits. This document covers the second stage, since that's where Nepali and English are actually handled differently.

## Model

The backend uses [AI4Bharat IndicConformer 600M Multilingual](https://huggingface.co/ai4bharat/indic-conformer-600m-multilingual).

| Property | Value |
| --- | --- |
| Model size | 600 million parameters |
| Languages | 22 Indic languages, including Nepali (`ne`) |
| Audio input | 16 kHz mono WAV |
| Primary decoder | CTC |
| Fallback decoder | RNNT |

The 600M figure refers to parameter count. Loading the model also requires substantial disk space and system memory for its ONNX assets and inference runtime. A CUDA-capable GPU is used when PyTorch detects one; CPU inference is also supported but slower.

## Architecture

microphone audio (webm/m4a)
        |  ffmpeg          (backend/main.py: convert_to_wav)
        v
16 kHz mono WAV
        |  soundfile + IndicConformer ("ne", "ctc")
        v
raw text, e.g. "सात हजार दुई सय तीन" or "फोर हन्ड्रेड फोर्टी फोर"
        |  words_to_number()   (backend/main.py)
        v
digits, e.g. "7203" -> displayed as "७२०३"

The browser sends recorded WebM audio as a binary WebSocket message. The backend converts it to 16 kHz mono WAV with FFmpeg, runs IndicConformer, and normalizes recognized Nepali number words.

## Two vocabularies, two parsers

| | Nepali | English (spelled in Devanagari) |
| --- | --- | --- |
| Function | `parse_nepali_words()` | `parse_phonetic_english()` |
| Word lists | `NEPALI_UNITS`, `NEPALI_MULTIPLIERS` | `PHONETIC_UNITS`, `PHONETIC_MULTIPLIERS` |
| Example | `सात हजार दुई सय तीन` → `7203` | `फोर थाउजन्ड फोर हन्ड्रेड फोर्टी फोर` → `4444` |
| Compound order | units, *then* सय/हजार/लाख multiply it | tens word, *then* the unit adds to it ("forty" + "four" = 44) |

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Node.js 20.9 or newer
- FFmpeg available on `PATH`
- Caddy for HTTPS LAN sharing
- Optional: NVIDIA CUDA-capable GPU

## Run Locally

Install frontend dependencies once:

```powershell
cd frontend
npm install
```

Start the backend:

```powershell
cd backend
uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

Start the frontend in a second terminal:

```powershell
cd frontend
npm run dev -- -H 127.0.0.1
```

For local use on the same computer, open `http://localhost:3000`.

## Share On A LAN With HTTPS

Microphone access on other devices requires HTTPS. Keep the frontend and backend bound to `127.0.0.1`, and expose only Caddy over HTTPS.

1. Install Caddy:

   ```powershell
   winget install --id CaddyServer.Caddy --exact
   ```

2. Update `Caddyfile` with this computer's LAN IP. The committed example uses `192.168.10.61`.

3. Start the backend and frontend with the commands above.

4. Start Caddy from the project root:

   ```powershell
   caddy run --config Caddyfile
   ```

5. Share the HTTPS URL, for example:

   ```text
   https://192.168.10.61/

## Testing results

Two scripts in tests/ check the backend from outside: accuracy_test.py checks whether recognized numbers come out correct, concurrency_test.py checks whether the server holds up when several people use it at once. Both talk to the backend's /ws endpoint directly with no browser involved.

### Accuracy Test

Sends a folder of pre-recorded clips (generated with ElevenLabs TTS) through the backend one at a time and compares each result to the number encoded in the file name (e.g. num_1253.mp3 → expects 1253).

| Verdict | Count | Meaning |
| --- | --- | --- |
| `MATCH` | 18 | Correct digits returned. |
| `no-digits` | 4 | Neither parser recognized the words; raw ASR text was returned unchanged. Visible failure — safe. |
| `MISMATCH` | 2 | A number was returned, but the wrong one. Silent failure — the dangerous kind. |

**`no-digits` cases (unrecognized spelling — safe, but need a vocabulary entry):**

| File | Expected | ASR produced | Cause |
| --- | --- | --- | --- |
| `digit_984123.mp3` | 984123 | `न आठ चार एक दुई तिन` | `नौ` (9) was transcribed as `न`, missing the `ौ`. `न` isn't in the vocabulary. |
| `num_4444.mp3` | 4444 | `चार हजार चार सय चवालिस` | `चवालिस` is a vowel-shortened form of `चौवालीस` (44) that isn't close enough for the fuzzy matcher (cutoff 0.75) to catch. |
| `num_7162.mp3` | 7162 | `सात हजार एक सय बैसट्ठी` | `बैसट्ठी` (62) isn't in `NEPALI_UNITS` — only the pulled file's original spelling `बयसठ्ठी` is. The two spellings differ enough (`ट` vs `ठ`, `ै` vs `य`+`ि`) that neither the vowel-folding step nor fuzzy matching bridges them. |
| `eng_123.mp3` | 123 | `वान हन्ड्रेड थोनििस्री` | The ASR mangled "twenty three" beyond recognition (`थोनििस्री`). This looks like an audio/model quality issue, not a parser gap. |

**`MISMATCH` cases (wrong number, no error — needs investigating first):**

| File | Expected | Got | Note |
| --- | --- | --- | --- |
| `num_44.mp3` | 44 | 40 | The parser accepted *something* as a valid number and returned 40. Likely: the ASR's spelling of 44 fuzzy-matched to `चालीस` (40) instead of failing outright. The raw transcription wasn't captured for `MISMATCH` rows (only for `no-digits`) — check the backend log's `Raw transcription:` line for this file to confirm and add the correct spelling as an exact entry. |
| `num_99.mp3` | 99 | 1000 | Same situation — the parser returned a confident wrong answer. `1000` suggests the ASR output was heard as something matching `हजार` alone. Check the raw transcription log for this file before fixing. |

### Concurrency Test

Opens several simulated users at once against the same backend, sends the same recording from each, and checks three things: total throughput, whether the server keeps answering new connections while it's busy, and whether every reply for the same audio came back identical.

### Test run results

one user alone: 0.42s

5 users at once: 50/50 succeeded, everyone done after 20.80s
  wait per request: fastest 0.40s  median 2.07s  slowest 3.40s
  time to open a NEW connection while busy: median 1.728s  worst 2.759s

  distinct transcripts across 50 successful replies: 1

| Check | Result | Reading |
|---|---|---|
| Correctness under load | 50/50 identical transcripts | Pass — no cross-request interference. |
| Throughput | 20.8s for 50 requests (≈ 50 × 0.42s baseline) | **Sequential**, not parallel. Expected with one model instance on one GPU; GPU inference itself is a queue, not a bug by itself. |
| Responsiveness while busy | new connections waited up to 2.76s | **Fail.** |

So, the final results of the concurrency tests are as follows:
One request alone takes 0.4s.
If the server handled all 5 clients truly in parallel, 50 requests should still take roughly 0.4–1s total (or scale up gently with GPU contention).
If it handles them strictly one at a time, 50 requests should take about 50 × 0.4s = 20s.
