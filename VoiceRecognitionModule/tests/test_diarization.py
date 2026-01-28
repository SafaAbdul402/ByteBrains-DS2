import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from speaker.segmentation import load_diarization_pipeline


meeting_dir = Path("data/runs/meeting2-test")
processed_wav = meeting_dir / ".voice_internal" / "processed.wav"

assert processed_wav.exists(), "processed.wav not found"

pipeline = load_diarization_pipeline()
annotation = pipeline(str(processed_wav))

segments = []
for segment, _, speaker in annotation.itertracks(yield_label=True):
    segments.append({
        "start": segment.start,
        "end": segment.end,
        "speaker": speaker
    })

print(f"✅ Diarization OK — segments found: {len(segments)}")

# Print first few for sanity
for s in segments[:5]:
    print(s)
