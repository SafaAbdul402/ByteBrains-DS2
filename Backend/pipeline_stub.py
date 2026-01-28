from pathlib import Path
import json
import os
from typing import Dict, List, Any
from Backend.config import RUNS_DIR
from VoiceRecognitionModule.src.pipeline.run_pipeline import process_meeting
import requests

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
TEST_SHARED_SECRET = os.getenv("TEST_SHARED_SECRET", "byte-test-tk")

def vr_process(meeting_id: str) -> dict:
    run_dir = RUNS_DIR / meeting_id
    process_meeting(run_dir)

    return {
        "transcript": json.loads((run_dir / "transcript.json").read_text()),
        "speakers": json.loads((run_dir / "speakers.json").read_text()),
        "status": json.loads((run_dir / "status.json").read_text()),
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