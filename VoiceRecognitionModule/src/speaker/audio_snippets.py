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
    waveform, sr = torchaudio.load(processed_wav)

    # Load diarization
    with open(diarization_json, "r", encoding="utf-8") as f:
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

        speaker_waveform = torch.cat(chunks, dim=1)
        out_path = output_dir / f"{speaker}.wav"

        torchaudio.save(out_path, speaker_waveform, sr)

        saved_files[speaker] = str(out_path)

        print(f"Saved speaker audio: {out_path}")

    return saved_files
