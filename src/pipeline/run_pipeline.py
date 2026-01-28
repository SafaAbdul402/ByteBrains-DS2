from pathlib import Path

from src.audio.preprocess import preprocess_audio
from src.speaker.segmentation import load_diarization_pipeline
from src.speaker.embedding_model import ECAPAEmbedder
from src.speaker.extract_embeddings import extract_embeddings_from_latest
from src.speaker.clustering import cluster_embeddings
from src.speaker.diarization_pipeline import (
    build_speaker_timeline,
    save_diarization,
)
from src.transcription.transcriber import (
    transcribe_with_diarization,
    save_transcript_with_speakers
)
from src.speaker.audio_snippets import save_speaker_audio_snippets



def annotation_to_segments(annotation):
    """
    Convert pyannote Annotation → list of segments
    """
    segments = []
    for segment, _, speaker in annotation.itertracks(yield_label=True):
        segments.append(
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "speaker": speaker,
            }
        )
    return segments


def process_meeting(meeting_dir: Path):
    """
    FULL VOICE RECOGNITION PIPELINE
    --------------------------------
    Input:
        data/runs/meeting-<id>/
            └── recording.<ext>

    Output:
        data/runs/meeting-<id>/
            └── .voice_internal/
                ├── processed.wav
                ├── embeddings.json
                ├── diarization.json
                └── diarization.txt
    """

    meeting_dir = Path(meeting_dir)
    if not meeting_dir.exists():
        raise FileNotFoundError(meeting_dir)

    # 🔒 Internal working directory
    internal_dir = meeting_dir / ".voice_internal"
    internal_dir.mkdir(parents=True, exist_ok=True)

    #  Locate uploaded recording
    recordings = [
        f for f in meeting_dir.iterdir()
        if f.is_file() and f.suffix.lower() not in [".json", ".txt"]
    ]

    if not recordings:
        raise RuntimeError("No recording file found in meeting directory")

    recording = recordings[0]
    print("🎙 Using recording:", recording)

    # 1 Preprocess (ANY format → 16kHz mono wav)
    processed_wav = internal_dir / "processed.wav"
    preprocess_audio(recording, processed_wav)
    print("✅ Preprocessed audio:", processed_wav)

    # 2️ Pyannote diarization
    diarization_pipeline = load_diarization_pipeline()
    annotation = diarization_pipeline(str(processed_wav))

    segments = annotation_to_segments(annotation)
    print(f"✅ Pyannote segments: {len(segments)}")

    # 3️ ECAPA embeddings
    embedder = ECAPAEmbedder()
    embeddings = extract_embeddings_from_latest(
        processed_dir=internal_dir,
        segments=segments,
        embedder=embedder,
        output_dir=internal_dir,
    )
    print(f"✅ Embeddings extracted: {len(embeddings)}")

    # 4️ Clustering
    clustered_segments = cluster_embeddings(embeddings)

    # 5️ Build timeline
    timeline = build_speaker_timeline(clustered_segments)

    # 6 Save diarization
    diarization_json = internal_dir / "diarization.json"
    save_diarization(timeline, internal_dir)

    # 7 Transcription (Whisper + diarization)

    transcript_segments = transcribe_with_diarization(
        processed_wav,
        diarization_json,
        model_size="medium",
        device="cuda" if False else "cpu",  # change if GPU
        language="en"
    )

    # 8 Save FINAL output for UI
    ui_output = meeting_dir / "transcript_with_speakers.json"
    save_transcript_with_speakers(transcript_segments, ui_output)


    print("✅ Voice pipeline completed successfully")

    # 9 Save speaker audio snippets (for UI)
    speaker_audio_dir = meeting_dir / "speaker_audio"

    speaker_audio_files = save_speaker_audio_snippets(
        processed_wav=processed_wav,
        diarization_json=diarization_json,
        output_dir=speaker_audio_dir
    )

#  LOCAL TEST MODE (no backend / frontend)
if __name__ == "__main__":
    # Change this to any meeting folder you want to test
    test_meeting = Path("data/runs/meeting-test")
    process_meeting(test_meeting)
