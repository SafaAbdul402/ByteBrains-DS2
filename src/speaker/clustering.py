import numpy as np
from sklearn.cluster import AgglomerativeClustering


def cluster_embeddings(embeddings, threshold=0.75):
    X = np.array([e["embedding"] for e in embeddings])

    clustering = AgglomerativeClustering(
        n_clusters=None,
        metric="cosine",
        linkage="average",
        distance_threshold=threshold
    )

    labels = clustering.fit_predict(X)

    for e, label in zip(embeddings, labels):
        e["speaker"] = f"SPEAKER_{label}"

    return embeddings
