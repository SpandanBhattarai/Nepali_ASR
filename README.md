# Nepali Number ASR

A browser-based speech-recognition app for Nepali number words. The frontend records audio in the browser, sends it to a FastAPI WebSocket backend, and displays the recognized number in Devanagari digits when it can be parsed.

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

```text
Browser
  | HTTPS / WSS
  v
Caddy (port 443)
  |-- /    -> Next.js frontend (127.0.0.1:3000)
  `-- /ws  -> FastAPI ASR backend (127.0.0.1:8000)
```

The browser sends recorded WebM audio as a binary WebSocket message. The backend converts it to 16 kHz mono WAV with FFmpeg, runs IndicConformer, and normalizes recognized Nepali number words.

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
