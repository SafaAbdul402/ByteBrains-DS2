from pathlib import Path
import time
from VoiceRecognitionModule.src.audio.preprocess import preprocess_audio
#from VoiceRecognitionModule.src.audio.segmentation import segment_audio

from VoiceRecognitionModule.src.speaker.segmentation import load_diarization_pipeline
from VoiceRecognitionModule.src.speaker.embedding_model import ECAPAEmbedder
from VoiceRecognitionModule.src.speaker.extract_embeddings import extract_embeddings_from_latest
from VoiceRecognitionModule.src.speaker.clustering import cluster_embeddings
from VoiceRecognitionModule.src.speaker.diarization_pipeline import (
    build_speaker_timeline,
    save_diarization,
)
from VoiceRecognitionModule.src.transcription.transcriber import (
    transcribe_with_diarization,
    save_transcript_with_speakers
)
from VoiceRecognitionModule.src.speaker.audio_snippets import save_speaker_audio_snippets



def annotation_to_segments(annotation):
    
    #Convert pyannote Annotation → list of segments
    
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

def filter_short_segments(segments, min_duration=1.0):
    return [
        s for s in segments
        if (s["end"] - s["start"]) >= min_duration
    ]

def timed_step(step_no, total, message):
    print(f"\n[{step_no}/{total}] {message}")
    return time.time()


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
    t = timed_step(1, 9, " Preprocessing audio...")
    preprocess_audio(recording, processed_wav)
    print("Preprocessed audio:", processed_wav)
    print(f"Done in {time.time() - t:.2f} sec")

    # 2️ Pyannote diarization
    t = timed_step(2, 9, "🧠 Pyannote diarization...")
    diarization_pipeline = load_diarization_pipeline()
    annotation = diarization_pipeline(str(processed_wav))
    print("[✓] Pyannote diarization done")
    print(f"Done in {time.time() - t:.2f} sec")

    t = timed_step(3, 9, "✂️ Converting annotation to segments...")
    segments = annotation_to_segments(annotation)
    
    print(f"✅ Pyannote segments (raw): {len(segments)}")


    segments = filter_short_segments(segments, min_duration=1.0)
    print(f"✅ Segments after filtering: {len(segments)}")



    # downstream code expects "speaker" key, but we don't use it for identity
    for s in segments:
        s["speaker"] = "UNKNOWN"

    print(f"✅ Speech segments: {len(segments)}")

    # 3️ ECAPA embeddings
    embedder = ECAPAEmbedder()
    t = timed_step(4, 9, "🧠 Extracting ECAPA embeddings...")
    embeddings = extract_embeddings_from_latest(
        processed_dir=internal_dir,
        segments=segments,
        embedder=embedder,
        output_dir=internal_dir,
    )
    print(f"✅ Embeddings extracted: {len(embeddings)}")
    print(f"✅ Done in {time.time() - t:.2f} sec")

    # 4️ Clustering
    t = timed_step(5, 9, "🔗 Clustering embeddings...")
    clustered_segments = cluster_embeddings(embeddings)
    print(f"✅ Done in {time.time() - t:.2f} sec")
    print("[✓] Clustering done")

    # 5️ Build timeline
    t = timed_step(6, 9, "🧭 Building speaker timeline...")
    timeline = build_speaker_timeline(clustered_segments)
    print(f"✅ Done in {time.time() - t:.2f} sec")

    # 6 Save diarization
    diarization_json = internal_dir / "diarization.json"
    save_diarization(timeline, internal_dir)

    # 9 Save speaker audio snippets (for UI)
    speaker_audio_dir = meeting_dir / "speaker_audio"

    t = timed_step(9, 9, "🔊 Exporting speaker audio snippets...")
    speaker_audio_files = save_speaker_audio_snippets(
        processed_wav=processed_wav,
        diarization_json=diarization_json,
        output_dir=speaker_audio_dir
    )
    print(f"✅ Done in {time.time() - t:.2f} sec")

    # 7 Transcription (Whisper + diarization)

    t = timed_step(8, 9, "📝 Whisper transcription...")
    transcript_segments = transcribe_with_diarization(
        processed_wav,
        diarization_json,
        model_size="medium",
        device="cuda" if False else "cpu",  # change if GPU
        language="en"
    )
    print(f"Transcription Done in {time.time() - t:.2f} sec")

    # 8 Save FINAL output for UI
    ui_output = meeting_dir / "transcript_with_speakers.json"
    save_transcript_with_speakers(transcript_segments, ui_output)


    print("✅ Voice pipeline completed successfully")


#  LOCAL TEST MODE (no backend / frontend)
if __name__ == "__main__":
    # Change this to any meeting folder you want to test
    test_meeting = Path("data/runs/meeting-1769461158")
    process_meeting(test_meeting)
