import subprocess
from pathlib import Path
from tqdm import tqdm

# ===============================
# PATH CONFIG
# ===============================

INPUT_DIR = Path("data/recordings")
OUTPUT_DIR = Path("data/outputs/processed_audio")

TARGET_SR = 16000
TARGET_CHANNELS = 1  # mono

SUPPORTED_EXTENSIONS = {
    ".wav", ".mp3", ".mp4", ".m4a",
    ".aac", ".flac", ".ogg", ".webm"
}


def preprocess_all_audio():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = [
        f for f in INPUT_DIR.iterdir()
        if f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        print("❌ No audio/video files found in data/recordings")
        return

    print(f"🎧 Processing {len(files)} files...\n")

    for file in tqdm(files):
        output_file = OUTPUT_DIR / f"{file.stem}.wav"

        command = [
            "ffmpeg",
            "-y",
            "-i", str(file),
            "-ac", str(TARGET_CHANNELS),
            "-ar", str(TARGET_SR),
            "-vn",
            str(output_file)
        ]

        subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    print("\n✅ All files processed successfully!")
    print(f"📂 Output folder: {OUTPUT_DIR}")


if __name__ == "__main__":
    preprocess_all_audio()
