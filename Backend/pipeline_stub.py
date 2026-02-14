from typing import Dict, List, Any
from pathlib import Path
import json
from Backend.config import RUNS_DIR
from VoiceRecognitionModule.src.pipeline.run_pipeline import process_meeting
 #change?

def vr_process(meeting_id: str) -> dict:
    run_dir = RUNS_DIR / meeting_id
    process_meeting(str(run_dir))  # VR writes outputs
    return load_vr_outputs(meeting_id)


def load_vr_outputs(meeting_id: str):
    run_dir = RUNS_DIR / meeting_id
    out = {}

    status_path = run_dir / "vr_status.json"
    if status_path.exists():
        out["status"] = json.loads(status_path.read_text(encoding="utf-8"))

    speakers_path = run_dir / "vr_speakers.json"
    if speakers_path.exists():
        out["speakers"] = json.loads(speakers_path.read_text(encoding="utf-8"))

    transcript_path = run_dir / "vr_transcript.json"
    if transcript_path.exists():
        out["transcript"] = json.loads(transcript_path.read_text(encoding="utf-8"))

    return out

def n8n_run(final_transcript: str, profiles: List[dict]) -> Dict[str, Any]:
    """
    Placeholder for n8n agent pipeline.
    Later replace with HTTP POST to n8n webhook and parse result.
    """
    return {
        "summary": "Short summary...",
        "notes": "• Decision 1...\n• Decision 2...",
        "email_draft": "Hi all,\n\nThanks for today...\n\nBest,",
        "tasks": [
            {
                "task": "Example task",
                "assigned_to": profiles[0]["name"] if profiles else "Unassigned",
                "deadline": "2026-01-20",
                "reason": "Matched skills",
                "status": "Open",
            }
        ],
    }