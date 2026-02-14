from pathlib import Path
from collections import defaultdict
import json
import torchaudio
import torch


def save_speaker_audio_snippets(
    processed_wav: Path,
    diarization_json: Path,
    output_dir: Path
):
    """
    Create one WAV file per speaker by concatenating
    all diarized segments for that speaker.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    # Load audio
    # Load audio (Windows-safe)
    processed_wav = Path(processed_wav)

    if not processed_wav.exists():
        raise FileNotFoundError(f"processed_wav not found: {processed_wav}")

    size = processed_wav.stat().st_size
    if size < 1000:
        raise RuntimeError(f"processed.wav looks invalid (too small: {size} bytes): {processed_wav}")

    waveform, sr = torchaudio.load(str(processed_wav))

    # Load diarization
    diarization_json = Path(diarization_json)
    with open(str(diarization_json), "r", encoding="utf-8") as f:

        segments = json.load(f)

    speaker_chunks = defaultdict(list)

    for seg in segments:
        start = int(seg["start"] * sr)
        end = int(seg["end"] * sr)

        if end <= start:
            continue

        chunk = waveform[:, start:end]
        speaker_chunks[seg["speaker"]].append(chunk)

    saved_files = {}

    for speaker, chunks in speaker_chunks.items():
        if not chunks:
            continue

        # Total duration check
        total_samples = sum(chunk.shape[1] for chunk in chunks)
        total_duration = total_samples / sr

        if total_duration <= 7.0:
            print(f"Skipping {speaker} (only {total_duration:.2f}s → likely noise)")
            continue

        speaker_waveform = torch.cat(chunks, dim=1)
        out_path = output_dir / f"{speaker}.wav"

        torchaudio.save(out_path, speaker_waveform, sr)

        saved_files[speaker] = str(out_path)

        print(f"Saved speaker audio: {out_path} ({total_duration:.2f}s)")

    return saved_files
