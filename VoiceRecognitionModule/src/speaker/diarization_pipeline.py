from collections import defaultdict
from pathlib import Path
import json


def build_speaker_timeline(segments):
    """
    Build speaker -> [(start, end), ...] mapping
    """
    timeline = defaultdict(list)

    for seg in segments:
        timeline[seg["speaker"]].append(
            (seg["start"], seg["end"])
        )

    return timeline


def timeline_to_segments(timeline):
    """
    Convert:
      { speaker: [(start, end), ...] }

    Into:
      [
        { "start": x, "end": y, "speaker": speaker },
        ...
      ]
    """
    flat_segments = []

    for speaker, intervals in timeline.items():
        for start, end in intervals:
            flat_segments.append({
                "start": round(float(start), 2),
                "end": round(float(end), 2),
                "speaker": speaker
            })

    # IMPORTANT: sort by time
    flat_segments.sort(key=lambda x: x["start"])

    return flat_segments


def save_diarization(timeline, output_dir: Path):
    """
    Save diarization output in flat JSON format
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    flat_segments = timeline_to_segments(timeline)

    # JSON (UI + Whisper friendly)
    json_path = output_dir / "diarization.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(flat_segments, f, indent=2)

    # Optional human-readable TXT
    txt_path = output_dir / "diarization.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        for seg in flat_segments:
            f.write(
                f"{seg['speaker']}: "
                f"{seg['start']:.2f} → {seg['end']:.2f}\n"
            )

    print(f"Diarization saved to: {output_dir}")
    print("DEBUG — segments being saved:", len(flat_segments))
    print(flat_segments[:5])
    print(f"- {json_path}")
    print(f"- {txt_path}")
