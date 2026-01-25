import json
from pathlib import Path
import torch
import torchaudio
import whisper

# ------------------------------
# 1. Paths
# ------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIAR_FILE = PROJECT_ROOT / "data" / "diarization" / "WhatsApp Video 2026-01-17 at 6.01.58 PM_diarization.json"
AUDIO_FILE = PROJECT_ROOT / "data" / "outputs" / "processed_audio" / "WhatsApp Video 2026-01-17 at 6.01.58 PM.wav"
OUTPUT_FILE = PROJECT_ROOT / "data" / "outputs" / "finaltranscript" / "whisper_segment_transcript.json"

# ------------------------------
# 2. Load diarization
# ------------------------------
with open(DIAR_FILE, "r") as f:
    diarization = json.load(f)

# ------------------------------
# 3. Load audio
# ------------------------------
waveform, sr = torchaudio.load(AUDIO_FILE)
if waveform.shape[0] > 1:
    waveform = waveform.mean(dim=0, keepdim=True)
waveform = waveform[0]

TARGET_SR = 16000
if sr != TARGET_SR:
    waveform = torchaudio.transforms.Resample(sr, TARGET_SR)(waveform)
    sr = TARGET_SR

# ------------------------------
# 4. Load Whisper
# ------------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
model = whisper.load_model("base", device=device)

# ------------------------------
# 5. Transcribe per diarization segment
# ------------------------------
results = []

for seg in diarization:
    start_sample = int(seg["start"] * sr)
    end_sample = int(seg["end"] * sr)
    speaker = seg["speaker"]

    audio_chunk = waveform[start_sample:end_sample].numpy()

    if audio_chunk.shape[0] == 0:
        continue

    # Whisper expects [samples], not [1, samples]
    transcription = model.transcribe(audio_chunk, language="en", word_timestamps=True)

    words = transcription.get("segments", [])
    word_list = []
    for w in words:
        # each word has start, end, text
        word_list.append({
            "start": round(w["start"], 3),
            "end": round(w["end"], 3),
            "word": w["text"]
        })

    results.append({
        "speaker": speaker,
        "start": round(seg["start"], 3),
        "end": round(seg["end"], 3),
        "words": word_list,
        "text": " ".join([w["word"] for w in word_list])
    })

# ------------------------------
# 6. Save JSON
# ------------------------------
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(f"✅ Segment-level word-level transcript saved to {OUTPUT_FILE}")
print(f"Total diarized segments: {len(results)}")
