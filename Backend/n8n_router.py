# Backend/n8n_router.py
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, Header, HTTPException
from Backend.config import DATA_DIR, RUNS_DIR
from datetime import datetime

router = APIRouter(prefix="/n8n", tags=["n8n"])

#N8N_WEBHOOK = os.getenv("N8N_TEST", "")    
N8N_WEBHOOK = os.getenv("N8N_WEBHOOK", "")         
#TEST_SHARED_SECRET = os.getenv("TEST_SHARED_SECRET", "")
API_BASE = os.getenv("API_BASE", "")

def _state_path(meeting_id: str) -> Path:
    return Path(DATA_DIR) / "n8n_status" / f"{meeting_id}.json"

def _load_state(meeting_id: str) -> Dict[str, Any]:
    p = _state_path(meeting_id)
    if not p.exists():
        return {
            "ok": False,
            "meeting_id": meeting_id,
            "latest": {"type": "Status", "text": "Initializing..."},
            "timeline": [],
            "updated_at": None,
            "result": None,
        }
    return json.loads(p.read_text(encoding="utf-8"))

def _save_state(meeting_id: str, state: Dict[str, Any]) -> None:
    p = _state_path(meeting_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

def _append_timeline(meeting_id: str, msg: Dict[str, Any]) -> None:
    state = _load_state(meeting_id)
    state["ok"] = True
    state["meeting_id"] = meeting_id
    state["latest"] = msg
    state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tl = state.get("timeline") or []
    tl.append({"at": state["updated_at"], **msg})
    state["timeline"] = tl

    # If this looks like a final result, store it
    if isinstance(msg, dict) and (
        "notes" in msg or "email_draft" in msg or "tasks" in msg
    ):
        state["result"] = msg

    _save_state(meeting_id, state)
    

@router.post("/start/{meeting_id}")
def start_n8n(meeting_id: str, payload: Dict[str, Any]): 
    if not N8N_WEBHOOK:
        raise HTTPException(status_code=500, detail="N8N_WEBHOOK is not set.")
    if not API_BASE:
        raise HTTPException(status_code=500, detail="API_BASE is not set.")
    
    # persist initial state
    _append_timeline(meeting_id, {
        "type": "Status",
        "text": "n8n: Workflow triggered"
    })

    start_payload = {
        **payload,
        "meeting_id": meeting_id,
        "status_callback_url": f"{API_BASE}/n8n/update/{meeting_id}",
        "result_callback_url": f"{API_BASE}/n8n/update/{meeting_id}",
    }

    try:
        # 🔑 fire-and-forget
        requests.post(
            N8N_WEBHOOK,
            json=start_payload,
            timeout=3,   # SHORT
        )
    except Exception as e:
        # DO NOT FAIL
        _append_timeline(meeting_id, {
            "type": "Warning",
            "text": f"n8n not reachable: {str(e)}"
        })

    return {"ok": True, "meeting_id": meeting_id}


@router.post("/update/{meeting_id}")
def update_status(meeting_id: str, payload: Dict[str, Any]):
    from Backend.store import read_current_meeting, save_meetings, load_meetings

    # Normalize legacy/alternative field names
    if "Summary" in payload and "notes" not in payload:
        payload["notes"] = payload["Summary"]
    # Save the summary to file
    run_dir = RUNS_DIR / meeting_id
    run_dir.mkdir(parents=True, exist_ok=True)

    summary_path = run_dir / "summary.json"
    summary_data = {
        "meeting_id": meeting_id,
        "received_at": datetime.now().isoformat(timespec="seconds"),
        "notes": payload.get("notes"),
        "raw": payload  # optional: store full raw payload
    }

    summary_path.write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")
    if "EmailDraft" in payload and "email_draft" not in payload:
        payload["email_draft"] = payload["EmailDraft"]
    if "Tasks" in payload and "tasks" not in payload:
        payload["tasks"] = payload["Tasks"]
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object.")

    msg = {
        "type": payload.get("type", "Status"),
        "text": payload.get("text") or payload.get("status") or "",
        **payload,
    }
    _append_timeline(meeting_id, msg)
    return {"ok": True}


@router.get("/status/{meeting_id}")
def get_status(meeting_id: str):
    state = _load_state(meeting_id)
    return {
        "latest": state.get("latest"),
        "result": state.get("result"),
    }







