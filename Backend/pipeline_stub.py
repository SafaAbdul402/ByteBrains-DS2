from pathlib import Path
import json
from typing import Dict, List, Any
from Backend.config import RUNS_DIR
from VoiceRecognitionModule.src.pipeline.run_pipeline import process_meeting


def vr_process(meeting_id: str) -> dict:
    run_dir = RUNS_DIR / meeting_id

    # VR team handles EVERYTHING internally
    process_meeting(run_dir)

    return {
        "transcript": json.loads((run_dir / "transcript.json").read_text()),
        "speakers": json.loads((run_dir / "speakers.json").read_text()),
        "status": json.loads((run_dir / "status.json").read_text()),
    }


def n8n_run(transcript: Any, speaker_mapping: Dict[str, Any], profiles: List[dict], meeting_id: str,) -> Dict[str, Any]:
    payload = {
        "meeting_id": meeting_id,
        "transcript": transcript,
        "speaker_mapping": speaker_mapping,
        "profiles": profiles,
    }

    # TODO: requests.post(n8n_webhook_url, json=payload).json()
    return {
        "summary": "Short summary...",
        "notes": "• Decision 1...\n• Decision 2...",
        "email_draft": "Hi all,\n\nThanks for today...\n\nBest,",
        "tasks": [],
    }