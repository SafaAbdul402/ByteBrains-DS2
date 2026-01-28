import sys
from pathlib import Path

# Allow imports from src/
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from speaker.audio_snippets import save_speaker_audio_snippets


def test_audio_snippets():
    meeting_dir = Path("data/runs/meeting2-test")

    processed_wav = meeting_dir / ".voice_internal" / "processed.wav"
    diarization_json = meeting_dir / ".voice_internal" / "diarization.json"
    output_dir = meeting_dir / "speaker_audio"

    speaker_files = save_speaker_audio_snippets(
        processed_wav=processed_wav,
        diarization_json=diarization_json,
        output_dir=output_dir
    )

    assert len(speaker_files) > 0, "No speaker audio files generated"

    for speaker, path in speaker_files.items():
        print(f"{speaker}: {path}")

    print("✅ Speaker audio snippets generated successfully")


if __name__ == "__main__":
    test_audio_snippets()
