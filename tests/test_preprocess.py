import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from audio.preprocess import preprocess_audio


meeting_dir = Path("data/runs/meeting2-test")
input_audio = meeting_dir / "test_meeting_min.wav"
output_wav = meeting_dir / ".voice_internal" / "processed.wav"

processed = preprocess_audio(input_audio, output_wav)

print("✅ Preprocess successful")
print("Processed audio saved at:")
print(processed.resolve())
