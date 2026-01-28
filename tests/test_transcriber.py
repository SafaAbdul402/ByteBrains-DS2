import sys
from pathlib import Path
import json

# Allow imports from src/
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from transcription.transcriber import transcribe_with_diarization


def test_transcription():
    meeting_dir = Path("data/runs/meeting2-test")

    processed_audio = meeting_dir / ".voice_internal" / "processed.wav"
    diarization_json = meeting_dir / ".voice_internal" / "diarization.json"
    output_json = meeting_dir / "transcript_with_speakers.json"

    segments = transcribe_with_diarization(
        audio_path=processed_audio,
        diarization_json_path=diarization_json,
        model_size="medium",
        device="cpu",
        language="en"
    )

    assert len(segments) > 0, "No transcription segments produced"

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2)

    print("✅ Transcription OK")
    print(f"Segments: {len(segments)}")
    print(f"Saved at: {output_json.resolve()}")


if __name__ == "__main__":
    test_transcription()
