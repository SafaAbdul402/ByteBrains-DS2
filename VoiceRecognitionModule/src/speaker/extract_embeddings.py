import json
import torchaudio
from pathlib import Path
import time



def extract_embeddings_from_latest(processed_dir: Path, segments, embedder, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    processed_files = list(processed_dir.glob("*.wav"))
    if not processed_files:
        raise FileNotFoundError("No processed audio found")

    latest_audio = max(processed_files, key=lambda f: f.stat().st_mtime)

    waveform, sr = torchaudio.load(latest_audio)
    if sr != 16000:
        waveform = torchaudio.functional.resample(waveform, sr, 16000)
        sr = 16000

    embeddings = []

    start_time = time.time()
    total = len(segments)

    for i, seg in enumerate(segments):
        start = int(seg["start"] * sr)
        end = int(seg["end"] * sr)

        if end - start < sr * 0.5:
            continue

        print(f"    Embedding segment {i + 1}: {seg['start']:.2f} → {seg['end']:.2f}")

        chunk = waveform[:, start:end]
        emb = embedder.embed_waveform(chunk)

        embeddings.append({
            "start": seg["start"],
            "end": seg["end"],
            "speaker": seg["speaker"],
            "embedding": emb.tolist()
        })

        if i % 10 == 0 or i == total - 1:
            elapsed = time.time() - start_time
            avg = elapsed / (i + 1)
            remaining = avg * (total - i - 1)

            print(
                f"    ECAPA {i + 1}/{total} | "
                f"elapsed {elapsed:.1f}s | ETA {remaining / 60:.1f} min"
            )

    with open(output_dir / "embeddings.json", "w") as f:
        json.dump(embeddings, f, indent=2)

    return embeddings
