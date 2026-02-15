# Backend/vr_worker.py
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

from Backend.pipeline_stub import vr_process
from Backend.config import RUNS_DIR

def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def main():
    meeting_id = sys.argv[1]
    run_dir = RUNS_DIR / meeting_id
    run_dir.mkdir(parents=True, exist_ok=True)

    status_path = run_dir / "vr_status.json"
    result_path = run_dir / "vr_result.json"

    write_json(status_path, {
        "stage": "running",
        "updated_at": datetime.now().isoformat(timespec="seconds")
    })

    try:
        res = vr_process(meeting_id)  # <-- your existing VR integration
        write_json(result_path, res)

        write_json(status_path, {
            "stage": "done",
            "updated_at": datetime.now().isoformat(timespec="seconds")
        })

    except Exception as e:
        write_json(status_path, {
            "stage": "error",
            "error": str(e),
            "trace": traceback.format_exc(),
            "updated_at": datetime.now().isoformat(timespec="seconds")
        })
        raise

if __name__ == "__main__":
    main()