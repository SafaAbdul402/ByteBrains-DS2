import sys
import json
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from speaker.clustering import cluster_embeddings


embeddings_path = Path(
    "data/runs/meeting2-test/.voice_internal/embeddings.json"
)

with open(embeddings_path) as f:
    embeddings = json.load(f)

clustered = cluster_embeddings(embeddings)

print("✅ Clustering OK")
for e in clustered[:5]:
    print(e["speaker"])
