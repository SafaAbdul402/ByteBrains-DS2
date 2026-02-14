from pathlib import Path
import os

# If DATA_DIR is set (Render), use it. Otherwise fallback to repo/data (local).
BASE_DATA_DIR = os.getenv("DATA_DIR")

if BASE_DATA_DIR:
    DATA_DIR = Path(BASE_DATA_DIR)
else:
    REPO_ROOT = Path(__file__).resolve().parents[1]
    DATA_DIR = REPO_ROOT / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)

RUNS_DIR = DATA_DIR / "runs"
RUNS_DIR.mkdir(exist_ok=True)

CURRENT_MEETING_PATH = DATA_DIR / "current_meeting.json"
PROFILES_PATH = DATA_DIR / "profiles.json"
PROFILES_COMPLETED_PATH = DATA_DIR / "profiles_complete.json"
MEETINGS_PATH = DATA_DIR / "meetings.json"