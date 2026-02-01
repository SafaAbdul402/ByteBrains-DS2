from pathlib import Path
import json
import os
from typing import Dict, List, Any
from Backend.config import RUNS_DIR
from VoiceRecognitionModule.src.pipeline.run_pipeline import process_meeting
import requests

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
TEST_SHARED_SECRET = os.getenv("TEST_SHARED_SECRET", "")

def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _list_speaker_audio(run_dir: Path) -> Dict[str, str]:
    """
    Returns mapping like:
      { "SPEAKER_0": "/abs/path/.../speaker_audio/SPEAKER_0.wav", ... }
    Speaker IDs are derived from the filename stem.
    """
    speaker_dir = run_dir / "speaker_audio"
    if not speaker_dir.exists():
        return {}

    files = []
    # accept common audio extensions just in case
    for ext in ("*.wav", "*.mp3", "*.m4a", "*.flac", "*.ogg"):
        files.extend(speaker_dir.glob(ext))

    speaker_audio = {}
    for f in sorted(files):
        speaker_id = f.stem  # e.g. "SPEAKER_0"
        speaker_audio[speaker_id] = str(f.resolve())

    return speaker_audio


def vr_process(meeting_id: str) -> dict:
    run_dir = RUNS_DIR / meeting_id

    # Run VR pipeline
    process_meeting(run_dir)

    # --- Transcript (use the file that actually exists)
    transcript_path = run_dir / "transcript_with_speakers.json"
    if not transcript_path.exists():
        raise FileNotFoundError(f"Missing transcript file: {transcript_path}")

    transcript = _read_json(transcript_path)

    # --- Speakers derived from speaker_audio folder
    speaker_audio = _list_speaker_audio(run_dir)
    speakers = sorted(list(speaker_audio.keys()))

    # --- Optional status from meeting_meta.json (or just omit)
    meta_status = None
    meta_path = run_dir / "meeting_meta.json"
    if meta_path.exists():
        try:
            meta = _read_json(meta_path)
            meta_status = meta.get("status")
        except Exception:
            meta_status = None

    return {
        "transcript": transcript,
        "speakers": speakers,
        "speaker_audio": speaker_audio,  # <— use this in Streamlit to play audio
        "status": meta_status,           # optional, can be None
    }

def n8n_run(transcript: Any, speaker_mapping: Dict[str, Any], profiles: List[dict], meeting_id: str) -> Dict[str, Any]:
    payload = {
        "meeting_id": meeting_id,
        "transcript": transcript,
        "speaker_mapping": speaker_mapping,
        "profiles": profiles,
    }

    r = requests.post(
        f"{API_BASE}/n8n/start/{meeting_id}",
        json=payload,
        headers={"X-BB-SECRET": TEST_SHARED_SECRET},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()