from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering

from src.utils.io import ensure_dir
from src.utils.paths import EMBEDDINGS, CLUSTERING


def cluster_latest_embeddings() -> Path:
    ensure_dir(CLUSTERING)

    rec_dirs = [d for d in EMBEDDINGS.iterdir() if d.is_dir()]
    if not rec_dirs:
        raise RuntimeError("No embeddings found")

    latest = max(rec_dirs, key=lambda p: p.stat().st_mtime)

    E = np.load(latest / "embeddings.npy")
    meta = pd.read_csv(latest / "meta.csv")

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=0.25,
        metric="cosine",
        linkage="average",
    )

    labels = clustering.fit_predict(E)
    meta["speaker"] = [f"SPEAKER_{i:02d}" for i in labels]

    out_dir = CLUSTERING / latest.name
    ensure_dir(out_dir)

    out_csv = out_dir / "clusters.csv"
    meta.to_csv(out_csv, index=False)

    print(f"Clustering written to {out_csv}")
    return out_csv
