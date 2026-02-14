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
from threading import Lock

router = APIRouter(prefix="/n8n", tags=["n8n"])

_start_lock = Lock()
_started: dict[str, float] = {}
_update_lock = Lock()
_last_update_ts: dict[str, float] = {}   # meeting_id -> last accepted update timestamp
N8N_UPDATE_DEBOUNCE_S = float(os.getenv("N8N_UPDATE_DEBOUNCE_S", "1.0"))  # 1 update / sec per meeting
N8N_START_DEDUP_S = float(os.getenv("N8N_START_DEDUP_S", "60"))

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

def _cleanup_updates(now: float, ttl: float = 3600.0):
    # Remove meetings that haven't updated in 1h
    dead = [mid for mid, ts in _last_update_ts.items() if (now - ts) > ttl]
    for mid in dead:
        _last_update_ts.pop(mid, None)
    

@router.post("/start/{meeting_id}")
def start_n8n(meeting_id: str, payload: Dict[str, Any]): 
    now = time.time()
    with _start_lock:
        last = _started.get(meeting_id)
        if last and (now - last) < N8N_START_DEDUP_S:
            _append_timeline(meeting_id, {
                "type": "Status",
                "text": "n8n: start deduped (already triggered)"
            })
            return {"ok": True, "meeting_id": meeting_id, "deduped": True}
        _started[meeting_id] = now
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

    # Save txt in run dir (optional)
    #run_dir = RUNS_DIR / meeting_id
    #run_dir.mkdir(parents=True, exist_ok=True)
    #payload_txt = json.dumps(start_payload, ensure_ascii=False, indent=2)
    #(run_dir / "n8n_payload.txt").write_text(payload_txt, encoding="utf-8")

    #try:
     #   # SEND TXT to n8n webhook
      #  requests.post(
       #     N8N_WEBHOOK,
        #    data=payload_txt,
         #   headers={"Content-Type": "text/plain; charset=utf-8"},
          #  timeout=3,
        #)
    #except Exception as e:
     #   _append_timeline(meeting_id, {"type": "Warning", "text": f"n8n not reachable: {str(e)}"})

    #return {"ok": True, "meeting_id": meeting_id}


@router.post("/update/{meeting_id}")
def update_status(meeting_id: str, payload: Dict[str, Any]):
    # Normalize legacy/alternative field names early
    if isinstance(payload, dict) and "Summary" in payload and "notes" not in payload:
        payload["notes"] = payload["Summary"]
    if isinstance(payload, dict) and "EmailDraft" in payload and "email_draft" not in payload:
        payload["email_draft"] = payload["EmailDraft"]
    if isinstance(payload, dict) and "Tasks" in payload and "tasks" not in payload:
        payload["tasks"] = payload["Tasks"]

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object.")

    # ✅ Decide if this is a "final-ish" update we MUST not debounce
    is_final = any(k in payload for k in ("notes", "email_draft", "tasks")) and (
        payload.get("notes") or payload.get("email_draft") or payload.get("tasks")
    )

    # ✅ Debounce only non-final status updates
    now = time.time()
    if not is_final:
        with _update_lock:
            # optional cleanup
            # _cleanup_updates(now)

            last = _last_update_ts.get(meeting_id, 0.0)
            if (now - last) < N8N_UPDATE_DEBOUNCE_S:
                # Drop this update quietly (prevents spam & IO)
                return {"ok": True, "debounced": True}

            _last_update_ts[meeting_id] = now
    else:
        # Always accept final updates (and record timestamp too)
        with _update_lock:
            _last_update_ts[meeting_id] = now

    # ✅ Build the message for your timeline/state file
    msg = {
        "type": payload.get("type", "Status"),
        "text": payload.get("text") or payload.get("status") or "",
        **payload,
    }

    # ✅ Only write summary.json when it's a final/summary payload (reduces disk IO)
    if is_final:
        run_dir = RUNS_DIR / meeting_id
        run_dir.mkdir(parents=True, exist_ok=True)

        summary_path = run_dir / "summary.json"
        summary_data = {
            "meeting_id": meeting_id,
            "received_at": datetime.now().isoformat(timespec="seconds"),
            "notes": payload.get("notes"),
            "raw": payload,
        }
        summary_path.write_text(
            json.dumps(summary_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    _append_timeline(meeting_id, msg)
    return {"ok": True}


@router.get("/status/{meeting_id}")
def get_status(meeting_id: str):
    state = _load_state(meeting_id)
    return {
        "latest": state.get("latest"),
        "result": state.get("result"),
    }







