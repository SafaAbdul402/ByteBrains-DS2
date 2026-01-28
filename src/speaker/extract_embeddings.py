import json
import torchaudio
from pathlib import Path


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

    for seg in segments:
        start = int(seg["start"] * sr)
        end = int(seg["end"] * sr)

        if end - start < sr * 0.5:
            continue

        chunk = waveform[:, start:end]
        emb = embedder.embed_waveform(chunk)

        embeddings.append({
            "start": seg["start"],
            "end": seg["end"],
            "speaker": seg["speaker"],
            "embedding": emb.tolist()
        })

    with open(output_dir / "embeddings.json", "w") as f:
        json.dump(embeddings, f, indent=2)

    print(f"Embedding {seg['start']:.2f} → {seg['end']:.2f}")

    return embeddings
