from pathlib import Path
import torch
import torchaudio
import json
from tqdm import tqdm

# ===============================
# PATHS
# ===============================

AUDIO_DIR = Path("data/outputs/processed_audio")
SEGMENTS_DIR = Path("data/segments")
SEGMENTS_DIR.mkdir(parents=True, exist_ok=True)

# ===============================
# LOAD SILERO VAD
# ===============================

model, utils = torch.hub.load(
    repo_or_dir="snakers4/silero-vad",
    model="silero_vad",
    trust_repo=True
)

(get_speech_timestamps,
 save_audio,
 read_audio,
 VADIterator,
 collect_chunks) = utils


# ===============================
# MAIN VAD FUNCTION
# ===============================

def run_vad():
    audio_files = list(AUDIO_DIR.glob("*.wav"))

    if not audio_files:
        print("❌ No WAV files found for VAD.")
        return

    print(f"🎙️ Running VAD on {len(audio_files)} files...\n")

    for audio_path in tqdm(audio_files):
        wav = read_audio(str(audio_path), sampling_rate=16000)

        speech_timestamps = get_speech_timestamps(
            wav,
            model,
            sampling_rate=16000
        )

        # Save timestamps
        json_path = SEGMENTS_DIR / f"{audio_path.stem}_segments.json"
        with open(json_path, "w") as f:
            json.dump(speech_timestamps, f, indent=2)

        # Save audio chunks
        chunks = collect_chunks(speech_timestamps, wav)
        save_audio(
            str(SEGMENTS_DIR / f"{audio_path.stem}_speech.wav"),
            chunks,
            sampling_rate=16000
        )

    print("\n✅ VAD completed successfully!")
    print(f"📂 Segments saved in: {SEGMENTS_DIR}")


if __name__ == "__main__":
    run_vad()
