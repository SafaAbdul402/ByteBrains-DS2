from __future__ import annotations

import json, os, time, uuid
from pathlib import Path
import requests
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from Backend.config import DATA_DIR  # uses your existing config.py

router = APIRouter(prefix="/test", tags=["test-http"])

TEST_STATE_PATH = Path(DATA_DIR) / "test_http_last.json"
N8N_TEST_WEBHOOK = os.getenv("N8N_TEST_WEBHOOK", "https://spryfox.app.n8n.cloud/webhook-test/8ed146ad-2041-4df2-911d-c0d54338a86f")
TEST_SHARED_SECRET = os.getenv("TEST_SHARED_SECRET", "byte-test-tk")  # simple auth


class TestRequest(BaseModel):
    source: str = "streamlit"
    type: str = "test"
    message: str = "Hello n8n 👋"


def save_last(payload: Dict[str, Any]) -> None:
    TEST_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    TEST_STATE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_last() -> Optional[Dict[str, Any]]:
    if not TEST_STATE_PATH.exists():
        return None
    try:
        return json.loads(TEST_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


@router.post("/n8n-roundtrip")
def n8n_roundtrip(body: TestRequest, x_bb_secret: str = Header(default="")):
    """
    Streamlit calls THIS.
    Backend calls n8n webhook.
    Backend returns result + also stores it.
    """
    if x_bb_secret != TEST_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized (missing/invalid X-BB-SECRET).")

    if not N8N_TEST_WEBHOOK:
        raise HTTPException(status_code=500, detail="N8N_TEST_WEBHOOK is not set in environment.")

    correlation_id = str(uuid.uuid4())

    payload = {
        "correlation_id": correlation_id,
        "user": "Tabia",
        "source": body.source,
        "type": body.type,
        "message": body.message,
        "server_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # basic retry (2 attempts total)
    last_err = None
    for attempt in range(2):
        try:
            r = requests.post(N8N_TEST_WEBHOOK, json=payload, timeout=12)
            r.raise_for_status()

            # n8n should return JSON
            try:
                n8n_data = r.json()
            except Exception:
                n8n_data = {"raw_text": r.text}

            out = {
                "ok": True,
                "correlation_id": correlation_id,
                "sent_to_n8n": payload,
                "received_from_n8n": n8n_data,
                "n8n_status_code": r.status_code,
            }
            save_last(out)
            return out

        except Exception as e:
            last_err = str(e)
            time.sleep(0.5)

    out = {
        "ok": False,
        "correlation_id": correlation_id,
        "sent_to_n8n": payload,
        "error": last_err,
    }
    save_last(out)
    raise HTTPException(status_code=502, detail=out)


@router.get("/last")
def get_last(x_bb_secret: str = Header(default="")):
    if x_bb_secret != TEST_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized (missing/invalid X-BB-SECRET).")
    return load_last() or {"ok": False, "message": "No test result stored yet."}