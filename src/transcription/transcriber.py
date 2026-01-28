from pathlib import Path
import json
import torchaudio
from faster_whisper import WhisperModel
from typing import List, Dict

# ===============================
# MODEL LOADING (cached singleton)
# ===============================

_MODEL = None

def get_whisper_model(
    model_size: str = "medium",
    device: str = "cpu"
) -> WhisperModel:
    global _MODEL
    if _MODEL is None:
        _MODEL = WhisperModel(model_size, device=device)
    return _MODEL


# ===============================
# MAIN TRANSCRIPTION FUNCTION
# ===============================

def transcribe_with_diarization(
    audio_path: Path,
    diarization_json_path: Path,
    *,
    model_size: str = "medium",
    device: str = "cpu",
    language: str = "en"
) -> List[Dict]:
    """
    Transcribe audio per diarization segment and return
    time-aligned speaker segments.

    Returns:
        List of segments sorted by start time.
    """

    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    if not diarization_json_path.exists():
        raise FileNotFoundError(diarization_json_path)

    # Load audio
    waveform, sr = torchaudio.load(audio_path)

    # Load diarization
    with open(diarization_json_path, "r", encoding="utf-8") as f:
        diarization_segments = json.load(f)

    model = get_whisper_model(model_size=model_size, device=device)

    all_segments: List[Dict] = []

    for seg in diarization_segments:
        start_sec = float(seg["start"])
        end_sec = float(seg["end"])
        speaker = seg["speaker"]

        if end_sec <= start_sec:
            continue

        start_frame = int(start_sec * sr)
        end_frame = int(end_sec * sr)

        segment_waveform = waveform[:, start_frame:end_frame]
        if segment_waveform.numel() == 0:
            continue

        segment_audio = segment_waveform.squeeze().numpy()

        segments, _ = model.transcribe(
            segment_audio,
            beam_size=5,
            language=language,
            word_timestamps=False
        )

        for s in segments:
            all_segments.append({
                "start": s.start + start_sec,
                "end": s.end + start_sec,
                "speaker": speaker,
                "text": s.text.strip()
            #'''""""words": [{"word": w.word,"start": w.start + start_sec,"end": w.end + start_sec}(s.words or [])] '''
            })



    # Critical: global ordering
    all_segments.sort(key=lambda x: x["start"])
    return all_segments

def save_transcript_with_speakers(
    segments: List[Dict],
    output_path: Path
):
    """
    Save final transcript_with_speakers.json for UI.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)

    print("Transcript with speakers saved at:")
    print(output_path.resolve())
