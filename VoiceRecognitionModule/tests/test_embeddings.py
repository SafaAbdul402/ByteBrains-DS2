import sys
from pathlib import Path
import torchaudio

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from speaker.embedding_model import ECAPAEmbedder


wav = Path("data/runs/meeting2-test/.voice_internal/processed.wav")
assert wav.exists()

waveform, sr = torchaudio.load(wav)
assert sr == 16000

# Take a 2s chunk
chunk = waveform[:, : 2 * sr]

embedder = ECAPAEmbedder()
embedding = embedder.embed_waveform(chunk)

print("✅ ECAPA embedding OK")
print("Embedding shape:", embedding.shape)
