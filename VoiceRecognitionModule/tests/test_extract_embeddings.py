import sys
from pathlib import Path
import json

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from speaker.embedding_model import ECAPAEmbedder
from speaker.extract_embeddings import extract_embeddings_from_latest


meeting_dir = Path("data/runs/meeting2-test")
processed_dir = meeting_dir / ".voice_internal"
output_dir = meeting_dir / ".voice_internal"

# Fake minimal segments for test
segments = [
    {"start": 0.0, "end": 3.0, "speaker": "SPEAKER_0"},
    {"start": 4.0, "end": 7.0, "speaker": "SPEAKER_1"},
]

embedder = ECAPAEmbedder()

embeddings = extract_embeddings_from_latest(
    processed_dir,
    segments,
    embedder,
    output_dir
)

print(f"✅ Embeddings extracted: {len(embeddings)}")
print("Saved at:", output_dir / "embeddings.json")
