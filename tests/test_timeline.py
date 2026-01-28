import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from speaker.diarization_pipeline import (
    build_speaker_timeline,
    save_diarization
)


segments = [
    {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_0"},
    {"start": 2.5, "end": 5.0, "speaker": "SPEAKER_1"},
    {"start": 5.5, "end": 8.0, "speaker": "SPEAKER_0"},
]

timeline = build_speaker_timeline(segments)

output_dir = Path("data/runs/meeting2-test/.voice_internal")
save_diarization(timeline, output_dir)

print("✅ Diarization saved successfully")
