from pathlib import Path

# repo_root/Backend/config.py -> repo_root = parents[1]
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
RUNS_DIR = DATA_DIR / "runs"   # per meeting_id folder
CURRENT_MEETING_PATH = DATA_DIR / "current_meeting.json"
PROFILES_PATH = DATA_DIR / "profiles.json"
PROFILES_COMPLETED_PATH = DATA_DIR / "profiles_completed.json"
MEETINGS_PATH = DATA_DIR / "meetings.json"