import torch
import torchaudio
from transformers import AutoModel

MODEL_ID = "ai4bharat/indic-conformer-600m-multilingual"

print("Loading model...")

device = "cuda" if torch.cuda.is_available() else "cpu"
print("Device:", device)

model = AutoModel.from_pretrained(
    MODEL_ID,
    trust_remote_code=True
)

model = model.to(device)
model.eval()

print("Model loaded.")

# Create 5 seconds of silent 16 kHz audio
sample_rate = 16000
duration = 5

audio = torch.zeros(1, sample_rate * duration)

print("Audio shape:", audio.shape)
print("Sample rate:", sample_rate)

audio = audio.to(device)

print("Running CTC transcription...")

with torch.no_grad():
    output = model(audio, "ne", "ctc")

print("\nResult:")
print(output)