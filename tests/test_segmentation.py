import sys
from pathlib import Path
import json

# allow imports from src/
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from speaker.segmentation import load_diarization_pipeline

meeting_dir = Path("data/runs/meeting2-test")
processed_wav = meeting_dir / ".voice_internal" / "processed.wav"
output_json = meeting_dir / ".voice_internal" / "diarization.json"

if not processed_wav.exists():
    raise FileNotFoundError(processed_wav)

print("🎙️ Running diarization on:")
print(processed_wav.resolve())

pipeline = load_diarization_pipeline()
annotation = pipeline(str(processed_wav))

segments = []
for segment, _, speaker in annotation.itertracks(yield_label=True):
    segments.append({
        "start": round(segment.start, 2),
        "end": round(segment.end, 2),
        "speaker": speaker
    })

output_json.parent.mkdir(parents=True, exist_ok=True)
with open(output_json, "w") as f:
    json.dump(segments, f, indent=2)

print(f"✅ Diarization complete")
print(f"Segments found: {len(segments)}")
print(f"Saved to: {output_json.resolve()}")
