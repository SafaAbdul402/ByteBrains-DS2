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

def meta_paths(meeting_id: str):
    base = RUNS_DIR / "_meta" / meeting_id
    return {
        "status": base / "vr_status.json",
        "result": base / "vr_result.json",
    }

def main():
    meeting_id = sys.argv[1]
    paths = meta_paths(meeting_id)

    write_json(paths["status"], {
        "stage": "running",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    })

    try:
        res = vr_process(meeting_id)
        write_json(paths["result"], res)

        write_json(paths["status"], {
            "stage": "done",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })

    except Exception as e:
        write_json(paths["status"], {
            "stage": "error",
            "error": str(e),
            "trace": traceback.format_exc(),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })
        raise

if __name__ == "__main__":
    main()