from pathlib import Path
import numpy as np
import librosa
import soundfile as sf

from src.utils.io import ensure_dir, safe_stem
from src.utils.paths import RECORDINGS, SUPPORTED_AUDIO_EXTS, PROCESSED_AUDIO


def get_latest_recording() -> Path:
    files = [
        p for p in RECORDINGS.iterdir()
        if p.suffix.lower() in SUPPORTED_AUDIO_EXTS
    ]
    if not files:
        raise RuntimeError("No supported audio files found in data/recordings")
    return max(files, key=lambda p: p.stat().st_mtime)


def preprocess_latest_to_wav16k() -> Path:
    """
    Take the latest recording and convert to mono 16k WAV.
    """
    ensure_dir(PROCESSED_AUDIO)

    latest = get_latest_recording()
    out = PROCESSED_AUDIO / f"{safe_stem(latest)}_16k.wav"

    if out.exists():
        print("Preprocessed audio already exists, skipping preprocessing.")
        return out

    print(f"Preprocessing latest audio: {latest}")

    y, sr = librosa.load(str(latest), sr=None, mono=True)

    if sr != 16000:
        y = librosa.resample(y, orig_sr=sr, target_sr=16000)

    peak = float(np.max(np.abs(y))) if y.size else 0.0
    if peak > 0:
        y = 0.95 * y / peak

    sf.write(out, y, 16000)
    return out
