from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import time
from threading import Lock

router = APIRouter(prefix="/lease", tags=["lease"])

MAX_USERS = int(os.getenv("MAX_ACTIVE_USERS", "2"))
LEASE_TTL_S = int(os.getenv("LEASE_TTL_S", "120"))  # 2 minutes

_lock = Lock()
_leases: dict[str, float] = {}  # session_id -> expires_at


def _cleanup(now: float):
    expired = [sid for sid, exp in _leases.items() if exp <= now]
    for sid in expired:
        _leases.pop(sid, None)


class LeaseReq(BaseModel):
    session_id: str


@router.post("/acquire")
def acquire(req: LeaseReq):
    now = time.time()
    with _lock:
        _cleanup(now)

        # already has a lease -> refresh
        if req.session_id in _leases:
            _leases[req.session_id] = now + LEASE_TTL_S
            return {"ok": True, "active": len(_leases), "ttl_s": LEASE_TTL_S}

        if len(_leases) >= MAX_USERS:
            # Friendly capacity error
            raise HTTPException(
                status_code=503,
                detail=f"capacity_reached: max={MAX_USERS}"
            )

        _leases[req.session_id] = now + LEASE_TTL_S
        return {"ok": True, "active": len(_leases), "ttl_s": LEASE_TTL_S}


@router.post("/heartbeat")
def heartbeat(req: LeaseReq):
    now = time.time()
    with _lock:
        _cleanup(now)
        if req.session_id in _leases:
            _leases[req.session_id] = now + LEASE_TTL_S
            return {"ok": True, "active": len(_leases), "ttl_s": LEASE_TTL_S}
        # If lease missing, client can re-acquire
        return {"ok": False, "missing": True, "active": len(_leases)}


@router.post("/release")
def release(req: LeaseReq):
    with _lock:
        _leases.pop(req.session_id, None)
        return {"ok": True, "active": len(_leases)}