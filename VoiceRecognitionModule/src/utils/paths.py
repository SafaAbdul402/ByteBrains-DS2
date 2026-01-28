from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

RECORDINGS = DATA / "recordings"
PROCESSED_AUDIO = DATA / "outputs" / "processed_audio"
EMBEDDINGS = DATA / "embeddings"
