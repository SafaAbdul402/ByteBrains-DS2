# Backend/store.py
import json
from datetime import datetime
from Backend.config import DATA_DIR, PROFILES_PATH, RUNS_DIR, CURRENT_MEETING_PATH, MEETINGS_PATH
from json import JSONDecodeError

def load_profiles():
    DATA_DIR.mkdir(exist_ok=True)
    default = {"updated_at": None, "trello_board": "", "trello_last_sync": None, "team": []}

    if not PROFILES_PATH.exists():
        return default

    try:
        text = PROFILES_PATH.read_text(encoding="utf-8").strip()
        if not text:
            return default
        data = json.loads(text)

        data.setdefault("trello_board", "")
        data.setdefault("trello_last_sync", None)
        data.setdefault("team", [])
        data.setdefault("updated_at", None)
        return data
    except JSONDecodeError:
        return default

def save_profiles(payload: dict):
    DATA_DIR.mkdir(exist_ok=True)

    current = load_profiles()

    # normalize trello_board
    incoming_board = payload.get("trello_board", None)
    if incoming_board is None:
        incoming_board = current.get("trello_board", "") or ""
    incoming_board = (incoming_board or "").strip()   # <- ensures never None

    # normalize last sync
    incoming_sync = payload.get("trello_last_sync", None)
    if incoming_sync is None:
        incoming_sync = current.get("trello_last_sync", None)

    out = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "team": payload.get("team", current.get("team", [])),
        "trello_board": incoming_board,          # <- never null
        "trello_last_sync": incoming_sync,
    }

    PROFILES_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out

# This is it:
def write_meeting_meta(meeting_id: str, participants: int, recording_path: str):
    run_dir = RUNS_DIR / meeting_id
    run_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "meeting_id": meeting_id,
        "participants": int(participants),
        "recording_path": recording_path,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "uploaded",
    }

    (run_dir / "meeting_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    pointer = dict(meta)
    pointer["run_dir"] = str(run_dir)
    CURRENT_MEETING_PATH.write_text(json.dumps(pointer, indent=2), encoding="utf-8")

    return meta

def read_current_meeting():
    if not CURRENT_MEETING_PATH.exists():
        return None
    return json.loads(CURRENT_MEETING_PATH.read_text(encoding="utf-8"))

#need to be updated?
def load_meetings():
    DATA_DIR.mkdir(exist_ok=True)
    if not MEETINGS_PATH.exists():
        return []
    return json.loads(MEETINGS_PATH.read_text(encoding="utf-8"))

def save_meetings(meetings):
    DATA_DIR.mkdir(exist_ok=True)
    MEETINGS_PATH.write_text(
        json.dumps(meetings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def insert_meeting(title, notes, email_draft, tasks, meeting_id: str | None = None):
    meetings = load_meetings()

    # IMPORTANT: use provided meeting_id so it matches data/runs/<meeting_id>/
    if meeting_id is None:
        meeting_id = f"meeting-{int(datetime.now().timestamp())}"

    meeting = {
        "meeting_id": meeting_id,
        "title": title,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "notes": notes,
        "email_draft": email_draft,
        "tasks": tasks,
        "trello_sync": {"last_status": "Not sent", "last_timestamp": None},
    }

    meetings.insert(0, meeting)
    save_meetings(meetings)
    return meeting