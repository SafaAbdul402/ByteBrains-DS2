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
from Backend.config import DATA_DIR

router = APIRouter(prefix="/n8n", tags=["n8n"])

N8N_WEBHOOK = os.getenv("N8N_WEBHOOK", "")         
TEST_SHARED_SECRET = os.getenv("TEST_SHARED_SECRET", "")

def _state_path(meeting_id: str) -> Path:
    return Path(DATA_DIR) / "n8n_status" / f"{meeting_id}.json"

def _load_state(meeting_id: str) -> Dict[str, Any]:
    p = _state_path(meeting_id)
    if not p.exists():
        return {
            "ok": False,
            "meeting_id": meeting_id,
            "latest": {"type": "Status", "text": "n8n"},
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

def _auth_or_401(x_bb_secret: str) -> None:
    if not TEST_SHARED_SECRET or x_bb_secret != TEST_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized (missing/invalid X-BB-SECRET).")
    

@router.post("/start/{meeting_id}")
def start_n8n(meeting_id: str, payload: Dict[str, Any], x_bb_secret: str = Header(default="")):
    """
    Streamlit calls this to kick off n8n processing.
    n8n webhook returns immediately (often only once).
    For live status updates, n8n should also POST /n8n/update/{meeting_id} during the run.
    """
    _auth_or_401(x_bb_secret)

    if not N8N_WEBHOOK:
        raise HTTPException(status_code=500, detail="N8N_WEBHOOK is not set.")

    correlation_id = str(uuid.uuid4())

    start_payload = {
        **payload,
        "meeting_id": meeting_id,
        "correlation_id": correlation_id,
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        # Tell n8n where to POST status updates:
        "status_callback_url": f"http://localhost:8000/n8n/update/{meeting_id}",
    }

    # store initial status
    _append_timeline(meeting_id, {"type": "Status", "text": "n8n"})

    last_err: Optional[str] = None
    for attempt in range(2):
        try:
            r = requests.post(N8N_WEBHOOK, json=start_payload, timeout=30)
            r.raise_for_status()

            # This is usually ONE response from n8n
            try:
                n8n_data = r.json()
            except Exception:
                n8n_data = {"type": "Status", "text": r.text}

            if isinstance(n8n_data, dict):
                _append_timeline(meeting_id, n8n_data)
            else:
                _append_timeline(meeting_id, {"type": "Status", "text": str(n8n_data)})

            return {"ok": True, "meeting_id": meeting_id, "correlation_id": correlation_id}

        except Exception as e:
            last_err = str(e)
            time.sleep(0.5)

    _append_timeline(meeting_id, {"type": "Error", "text": f"n8n call failed: {last_err}"})
    raise HTTPException(status_code=502, detail={"ok": False, "meeting_id": meeting_id, "error": last_err})


@router.post("/update/{meeting_id}")
def update_status(meeting_id: str, payload: Dict[str, Any], x_bb_secret: str = Header(default="")):
    """
    n8n should call this during workflow:
      { "type": "Status", "text": "input" }
      { "type": "Status", "text": "summary" }
      { "type": "Status", "text": "tasks" }
      { "type": "Status", "text": "trello" }
      { "type": "Status", "text": "done" }
    or send final result JSON (notes/email/tasks) at the end.
    """
    _auth_or_401(x_bb_secret)

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object.")

    # Normalize to always have keys
    msg = {
        "type": payload.get("type", "Status"),
        "text": payload.get("text", "") or payload.get("status", "") or "",
        **payload,
    }
    _append_timeline(meeting_id, msg)
    return {"ok": True}


@router.get("/status/{meeting_id}")
def get_status(meeting_id: str, x_bb_secret: str = Header(default="")):
    _auth_or_401(x_bb_secret)
    state = _load_state(meeting_id)
    return state.get("latest") or {"type": "Status", "text": "n8n"}


@router.get("/result/{meeting_id}")
def get_result(meeting_id: str, x_bb_secret: str = Header(default="")):
    _auth_or_401(x_bb_secret)
    state = _load_state(meeting_id)
    return state.get("result") or {}

@router.get("/timeline/{meeting_id}")
def get_timeline(meeting_id: str, x_bb_secret: str = Header(default="")):
    _auth_or_401(x_bb_secret)
    return _load_state(meeting_id)





