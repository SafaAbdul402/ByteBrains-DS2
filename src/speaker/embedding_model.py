from pathlib import Path
import numpy as np
import pandas as pd
import librosa
import torch
from speechbrain.inference.speaker import EncoderClassifier

from src.utils.io import ensure_dir
from src.utils.paths import SEGMENTS, EMBEDDINGS


def extract_latest_embeddings() -> Path:
    """
    Extract ECAPA embeddings for the latest segmented recording only.
    """
    ensure_dir(EMBEDDINGS)

    rec_dirs = [d for d in SEGMENTS.iterdir() if d.is_dir()]
    if not rec_dirs:
        raise RuntimeError("No segmented recordings found")

    latest = max(rec_dirs, key=lambda p: p.stat().st_mtime)
    segments_csv = latest / "segments.csv"

    df = pd.read_csv(segments_csv)
    df = df[~df["overlap"]].reset_index(drop=True)

    if df.empty:
        raise RuntimeError("No non-overlapping segments found")

    # ✅ IMPORTANT: use wav_path from CSV (no guessing)
    wav_path = Path(df.loc[0, "wav_path"])
    if not wav_path.exists():
        raise FileNotFoundError(f"WAV file not found: {wav_path}")

    classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        run_opts={"device": "cpu"},
    )

    embs = []
    for row in df.itertuples():
        y, sr = librosa.load(
            wav_path,
            sr=16000,
            offset=row.start_s,
            duration=row.end_s - row.start_s,
        )

        if len(y) == 0:
            continue

        emb = classifier.encode_batch(
            torch.tensor(y).unsqueeze(0)
        ).squeeze().numpy()

        emb /= np.linalg.norm(emb)
        embs.append(emb)

    if not embs:
        raise RuntimeError("No embeddings extracted")

    out_dir = EMBEDDINGS / latest.name
    ensure_dir(out_dir)

    np.save(out_dir / "embeddings.npy", np.vstack(embs))
    df.to_csv(out_dir / "meta.csv", index=False)

    print(f"Embeddings written to {out_dir}")
    return out_dir
