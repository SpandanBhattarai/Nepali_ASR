
import os
import tempfile
import subprocess

import torch
import torchaudio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from transformers import AutoModel
import soundfile as sf
from numerical_parser import parse_nepali_words, parse_phonetic_english

_DEVANAGARI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


def words_to_number(text: str) -> str:
    """Nepali or English number words -> digits in Devanagari, using numerical_parser only.
    If neither parser understands the text, the raw text is returned unchanged."""
    text = str(text).strip()
    if not text:
        return text

    for parser in (parse_nepali_words, parse_phonetic_english):
        try:
            return str(parser(text)).translate(_DEVANAGARI_DIGITS)
        except ValueError:
            continue

    print("numerical_parser could not parse:", repr(text))
    return text
# ============================================================
# Configuration
# ============================================================

MODEL_ID = "ai4bharat/indic-conformer-600m-multilingual"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

app = FastAPI()


# ============================================================
# Load IndicConformer ONCE
# ============================================================

print("=" * 60)
print("Loading IndicConformer...")
print("Device:", DEVICE)
print("=" * 60)

model = AutoModel.from_pretrained(
    MODEL_ID,
    trust_remote_code=True,
)

model = model.to(DEVICE)
model.eval()

print("=" * 60)
print("IndicConformer loaded successfully!")
print("Device:", DEVICE)
print("=" * 60)


# ============================================================
# Health check
# ============================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Nepali ASR backend is running",
        "device": DEVICE,
    }


# ============================================================
# Convert WebM -> 16 kHz mono WAV
# ============================================================

def convert_to_wav(webm_bytes: bytes):

    with tempfile.NamedTemporaryFile(
        suffix=".webm",
        delete=False
    ) as webm_file:

        webm_path = webm_file.name
        webm_file.write(webm_bytes)

    wav_path = webm_path.replace(".webm", ".wav")

    try:

        command = [
            "ffmpeg",
            "-y",
            "-i",
            webm_path,
            "-ar",
            "16000",
            "-ac",
            "1",
            wav_path,
        ]

        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode != 0:

            print("FFmpeg error:")
            print(result.stderr)

            raise RuntimeError(
                "FFmpeg could not decode the audio"
            )

        return wav_path

    finally:

        if os.path.exists(webm_path):
            os.remove(webm_path)


# ============================================================
# Transcribe audio with IndicConformer
# ============================================================

def transcribe_audio(wav_path: str):

    data, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
    waveform = torch.from_numpy(data.T).contiguous()

    print("=" * 60)
    print("Loaded WAV")
    print("Original sample rate:", sample_rate)
    print("Original shape:", waveform.shape)
    print("=" * 60)

    # --------------------------------------------------------
    # Make sure audio is mono
    # --------------------------------------------------------

    if waveform.ndim == 1:

        waveform = waveform.unsqueeze(0)

    elif waveform.shape[0] > 1:

        waveform = waveform.mean(
            dim=0,
            keepdim=True
        )

    # --------------------------------------------------------
    # Resample to 16 kHz
    # --------------------------------------------------------

    if sample_rate != 16000:

        print(
            f"Resampling {sample_rate} Hz -> 16000 Hz"
        )

        resampler = torchaudio.transforms.Resample(
            orig_freq=sample_rate,
            new_freq=16000,
        )

        waveform = resampler(waveform)

    # --------------------------------------------------------
    # Explicitly guarantee [1, samples]
    # --------------------------------------------------------

    if waveform.ndim != 2 or waveform.shape[0] !=1:

        raise RuntimeError(
            f"Unexpected audio shape: {tuple(waveform.shape)}. "
            "Expected [1, samples]."
        )

    if waveform.shape[0] != 1:

        raise RuntimeError(
            f"Unexpected channel count: {waveform.shape}. "
            "Expected mono audio with shape [1, samples]."
        )

    # --------------------------------------------------------
    # Check that audio actually contains samples
    # --------------------------------------------------------

    if waveform.shape[1] == 0:

        raise RuntimeError(
            "Audio contains zero samples."
        )

    # These measurements make remote microphone problems observable in the
    # backend log without storing a user's recording.
    peak_level = waveform.abs().max().item()
    rms_level = waveform.square().mean().sqrt().item()

    print("Final audio shape:", waveform.shape)
    print("Final sample rate: 16000")
    print("Audio duration:",
          waveform.shape[1] / 16000,
          "seconds")
    print(f"Audio peak level: {peak_level:.6f}")
    print(f"Audio RMS level: {rms_level:.6f}")

    # --------------------------------------------------------
    # Move audio to GPU
    # --------------------------------------------------------

    audio = waveform.to(DEVICE)

    print("Audio device:", audio.device)
    print("Audio dtype:", audio.dtype)

    # --------------------------------------------------------
    # Run IndicConformer
    # --------------------------------------------------------

    print("Running IndicConformer...")

    with torch.no_grad():
        # CTC is the decoder used by this project's model smoke test. RNNT
        # remains a fallback for clips CTC cannot decode.
        transcription = model(
            audio,
            "ne",
            "ctc",
        )

        if isinstance(transcription, (list, tuple)):
            transcription = transcription[0] if transcription else ""

        transcription = str(transcription).strip()

        if not transcription:
            print("CTC returned no text; trying RNNT fallback...")
            transcription = model(
                audio,
                "ne",
                "rnnt",
            )

    if isinstance(transcription, (list, tuple)):
        transcription = transcription[0] if transcription else ""

    transcription = str(transcription).strip()

    if not transcription:
        raise RuntimeError(
            "No speech was recognized. Check the browser microphone permission "
            "and speak clearly for at least one second."
        )

    print("Raw transcription:", transcription)

    transcription = words_to_number(transcription)

    print("Normalized transcription:", transcription)

    return transcription


# ============================================================
# WebSocket
# ============================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    await websocket.accept()

    print("WebSocket client connected")

    try:

        while True:

            # ------------------------------------------------
            # Receive complete recording
            # ------------------------------------------------

            data = await websocket.receive_bytes()

            print("=" * 60)
            print(
                f"Received audio: {len(data)} bytes"
            )
            print("=" * 60)

            if len(data) == 0:

                await websocket.send_json({
                    "status": "error",
                    "message": "Empty audio received",
                })

                continue

            wav_path = None

            try:

                # ------------------------------------------------
                # WebM -> WAV
                # ------------------------------------------------

                wav_path = convert_to_wav(data)

                print(
                    "Audio successfully converted "
                    "to 16 kHz mono WAV"
                )

                # ------------------------------------------------
                # ASR
                # ------------------------------------------------

                transcription = transcribe_audio(
                    wav_path
                )

                print("=" * 60)
                print("TRANSCRIPTION:")
                print(transcription)
                print("=" * 60)

                await websocket.send_json({
                    "status": "success",
                    "text": transcription,
                })

            except Exception as e:

                print("=" * 60)
                print("TRANSCRIPTION FAILED")
                print(repr(e))
                print("=" * 60)

                await websocket.send_json({
                    "status": "error",
                    "message": str(e),
                })

            finally:

                if (
                    wav_path is not None
                    and os.path.exists(wav_path)
                ):

                    os.remove(wav_path)

    except WebSocketDisconnect:

        print("WebSocket client disconnected")

    except Exception as e:

        print("=" * 60)
        print("WebSocket error:")
        print(repr(e))
        print("=" * 60)

        try:
            await websocket.close()
        except Exception:
            pass
