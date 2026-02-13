# Backend/trello_router.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from datetime import datetime
import time
from threading import Lock
_sync_lock = Lock()
_last_sync_ts = 0.0
SYNC_COOLDOWN_S = int(os.getenv("TRELLO_SYNC_COOLDOWN_S", "30"))

from Backend.store import load_profiles, save_profiles
from Backend.trello_api import fetch_board_members, members_to_profiles
from Backend.api import invalidate_profiles_cache

router = APIRouter(prefix="/trello", tags=["trello"])

class ImportRequest(BaseModel):
    board: str  # URL OR shortlink OR id

@router.post("/sync-members")   # rename endpoint (recommended)
def sync_members(req: ImportRequest):

    global _last_sync_ts
    now = time.time()

    with _sync_lock:
        if (now - _last_sync_ts) < SYNC_COOLDOWN_S:
            wait = int(SYNC_COOLDOWN_S - (now - _last_sync_ts))
            raise HTTPException(status_code=429, detail=f"sync cooldown: wait {wait}s")
        _last_sync_ts = now

    api_key = os.getenv("TRELLO_API_KEY", "")
    token = os.getenv("TRELLO_TOKEN", "")

    if not api_key or not token:
        raise HTTPException(status_code=500, detail="Missing TRELLO_API_KEY or TRELLO_TOKEN in environment.")

    try:
        members = fetch_board_members(api_key=api_key, token=token, board_input=req.board)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Trello fetch failed: {e}")

    incoming = members_to_profiles(members)
    incoming_ids = {p["trello_id"] for p in incoming if p.get("trello_id")}

    profiles = load_profiles()
    team = profiles.get("team", [])

    # index existing by trello_id
    by_tid = {p.get("trello_id"): p for p in team if p.get("trello_id")}

    # 1) Upsert incoming
    for p in incoming:
        tid = p.get("trello_id")
        if not tid:
            continue

        if tid in by_tid:
            existing = by_tid[tid]
            existing["name"] = p.get("name", existing.get("name", ""))
            existing["trello_username"] = p.get("trello_username", existing.get("trello_username", ""))
            # if was deleted but is back on board:
            if existing.get("status") == "deleted":
                existing["status"] = "imported"
                existing["deleted_at"] = None
        else:
            team.append({
                "id": f"trello-{tid}",
                "trello_id": tid,
                "trello_username": p.get("trello_username", ""),
                "name": p.get("name", "Unknown"),
                "email": "",
                "role": "",
                "skills": [],
                "notes": "",
                "photo": None,
                "status": "imported",
                "deleted_at": None,
            })

    # 2) Soft-delete missing
    now = datetime.now().isoformat(timespec="seconds")
    for prof in team:
        tid = prof.get("trello_id")
        if not tid:
            continue
        if tid not in incoming_ids:
            # only mark as deleted, don't remove
            if prof.get("status") != "deleted":
                prof["status"] = "deleted"
                prof["deleted_at"] = now

    # 3) Store board metadata (optional but professional)
    # 3) Store board metadata (persist!)
    # Backend/trello_router.py
    out = save_profiles({
        "team": team,
        "trello_board": req.board,
        "trello_last_sync": now,
    })
    invalidate_profiles_cache()
    return out