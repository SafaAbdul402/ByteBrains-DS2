# Backend/n8n_router.py
from __future__ import annotations

import json
import os
import time
import uuid
import re
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
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object.")

    # ---- Normalize type
    ptype = (payload.get("type") or "").strip().lower()
    text = payload.get("text")

    # tolerate common typos
    if ptype in ("transcipt",):
        ptype = "transcript"

    # ---- Load state so we can accumulate result
    state = _load_state(meeting_id)
    result = state.get("result") or {}   # this will become the merged final object

    # ---- Extract + normalize per message type
    if ptype == "summary":
        # they send: {"type":"Summary","text":"..."}
        summary_text = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False)
        result["summary"] = summary_text

    elif ptype == "tasks":
        # they send: {"type":"Tasks","text": {"0": {"json": {...}}, ...}}
        tasks_list = []
        if isinstance(text, dict):
            # keys "0","1",... each has {"json": {...}}
            for _, item in sorted(text.items(), key=lambda kv: str(kv[0])):
                if isinstance(item, dict):
                    j = item.get("json") if isinstance(item.get("json"), dict) else None
                    if j:
                        tasks_list.append(j)
        elif isinstance(text, list):
            # tolerate list already
            tasks_list = [t for t in text if isinstance(t, dict)]
        result["tasks"] = tasks_list

    elif ptype == "transcript":
        # they send: {"type":"Transcript","text":{"transcript[0]":{...}, ...}}
        transcript_list = []
        if isinstance(text, dict):
            # sort by the index inside "transcript[3]"
            def idx(k: str) -> int:
                m = re.search(r"\[(\d+)\]", str(k))
                return int(m.group(1)) if m else 10**9

            for k, v in sorted(text.items(), key=lambda kv: idx(kv[0])):
                if isinstance(v, dict):
                    transcript_list.append(v)
        elif isinstance(text, list):
            transcript_list = [t for t in text if isinstance(t, dict)]
        result["transcript"] = transcript_list

    # ---- Store merged result back
    state["result"] = result
    _save_state(meeting_id, state)

    # ---- Also keep timeline/latest for debugging
    msg = {
        "type": payload.get("type", "Status"),
        "text": payload.get("text") if isinstance(payload.get("text"), str) else "",
        **payload,
    }
    _append_timeline(meeting_id, msg)

    # Optional: write a single merged file
    run_dir = RUNS_DIR / meeting_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "n8n_result_merged.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    return {"ok": True}

@router.get("/status/{meeting_id}")
def get_status(meeting_id: str):
    state = _load_state(meeting_id)
    return {
        "latest": state.get("latest"),
        "result": state.get("result"),
    }







