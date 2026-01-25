from pathlib import Path
import json
import pandas as pd

from src.utils.io import ensure_dir
from src.utils.paths import CLUSTERING, DIARIZATION


def diarize_latest() -> Path:
    ensure_dir(DIARIZATION)

    rec_dirs = [d for d in CLUSTERING.iterdir() if d.is_dir()]
    if not rec_dirs:
        raise RuntimeError("No clustering results found")

    latest = max(rec_dirs, key=lambda p: p.stat().st_mtime)
    clusters_csv = latest / "clusters.csv"

    df = pd.read_csv(clusters_csv)

    timeline = [
        {
            "start": float(r.start_s),
            "end": float(r.end_s),
            "speaker": r.speaker,
        }
        for r in df.itertuples()
    ]

    out = DIARIZATION / f"{latest.name}_diarization.json"
    with open(out, "w") as f:
        json.dump(timeline, f, indent=2)

    print(f"Diarization written to {out}")
    return out
