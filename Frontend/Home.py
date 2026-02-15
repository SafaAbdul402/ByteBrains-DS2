import streamlit as st
import pandas as pd
import time
import json
import os
import sys
import re
import warnings
from datetime import datetime
import requests
from pathlib import Path
import subprocess, signal
#from Frontend.auth import require_password

# Suppress specific warnings
warnings.filterwarnings("ignore", message="Torchaudio's I/O functions")
warnings.filterwarnings("ignore", message="Module 'speechbrain.pretrained'")

#require_password()

# Path configuration
REPO_ROOT = Path(__file__).resolve().parents[1]  # ByteBrains/
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Backend.store import insert_meeting, write_meeting_meta
from Backend.config import RUNS_DIR, DATA_DIR

from Frontend.env import load_env
API_BASE = load_env()
if not API_BASE.startswith("http"):
    st.error("API_BASE is missing. Set API_BASE=https://<your-render-backend>.onrender.com in .env")
    st.stop()
PROFILES_COMPLETED_PATH = Path("data/profiles_complete.json")

def api_get_profiles():
    r = requests.get(f"{API_BASE}/profiles", timeout=10)
    r.raise_for_status()
    return r.json()

def api_get_n8n_status(meeting_id: str) -> dict:
    r = requests.get(f"{API_BASE}/n8n/status/{meeting_id}", timeout=10)
    r.raise_for_status()
    return r.json()

def load_completed_profiles() -> list[dict]:
    if not PROFILES_COMPLETED_PATH.exists():
        return []
    
    try:
        data = json.loads(PROFILES_COMPLETED_PATH.read_text(encoding="utf-8"))
        return data.get("team", []) if isinstance(data, dict) else []
    except Exception:
        return []

def profile_state(p: dict) -> str:
    # returns: "deleted" | "incomplete" | "eligible"
    if p.get("status") == "deleted":
        return "deleted"

    role_ok = bool((p.get("role") or "").strip())
    skills = p.get("skills") or []
    skills_ok = isinstance(skills, list) and any(str(s).strip() for s in skills)

    if role_ok and skills_ok:
        return "eligible"
    return "incomplete"

def pretty_speaker_label(raw: str, scheme: str = "letters") -> str:
    if not raw:
        return "Speaker"

    # try to extract the number at the end
    m = re.search(r"(\d+)$", raw)
    if not m:
        # fallback: just normalize SPEAKER_ -> Speaker _
        return raw.replace("SPEAKER_", "Speaker ").replace("_", " ")

    idx = int(m.group(1))  # SPEAKER_0 -> 0

    if scheme == "numbers":
        return f"Speaker {idx + 1}"

    # letters: 0->A, 1->B ... (supports beyond Z -> AA, AB ...)
    def idx_to_letters(i: int) -> str:
        letters = ""
        i += 1
        while i > 0:
            i, rem = divmod(i - 1, 26)
            letters = chr(65 + rem) + letters
        return letters

    return f"Speaker {idx_to_letters(idx)}"

def vr_paths(meeting_id: str):
    run_dir = RUNS_DIR / meeting_id
    meta_dir = RUNS_DIR / "_meta"
    return {
        "run_dir": run_dir,
        "status": meta_dir / meeting_id / "vr_status.json",
        "result": meta_dir / meeting_id / "vr_result.json",
        "log": RUNS_DIR / "_logs" / f"{meeting_id}.vr.log",
        "pid": RUNS_DIR / "_logs" / f"{meeting_id}.vr.pid",
    }

def start_vr_subprocess(meeting_id: str) -> int:
    p = vr_paths(meeting_id)
    p["run_dir"].mkdir(parents=True, exist_ok=True)
    p["log"].parent.mkdir(parents=True, exist_ok=True)
    p["pid"].parent.mkdir(parents=True, exist_ok=True)

    logf = p["log"].open("a", encoding="utf-8", buffering=1)

    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "Backend.vr_worker", meeting_id],  # <- add -u
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
        cwd=str(REPO_ROOT),
    )

    p["pid"].write_text(str(proc.pid), encoding="utf-8")

    def _tee():
        try:
            for line in proc.stdout:
                print(line, end="", flush=True)   # ✅ terminal live
                logf.write(line)                  # ✅ file for UI parsing
        finally:
            try:
                logf.close()
            except Exception:
                pass

    import threading
    threading.Thread(target=_tee, daemon=True).start()

    return proc.pid

def kill_vr_process(meeting_id: str):
    p = vr_paths(meeting_id)
    if not p["pid"].exists():
        return
    pid = int(p["pid"].read_text().strip())

    try:
        # Kill the whole process group
        os.killpg(pid, signal.SIGTERM)
    except Exception:
        pass

    # If it refuses to die quickly, hard kill
    try:
        os.killpg(pid, signal.SIGKILL)
    except Exception:
        pass

VR_STAGE_PROGRESS = {
    "[1/9]": 0.15,
    "[2/9]": 0.22,
    "[3/9]": 0.26,
    "[4/9]": 0.30,
    "[5/9]": 0.33,
    "[6/9]": 0.36,
    "[7/9]": 0.38,
    "[8/9]": 0.39,
    "[9/9]": 0.40,
}

VR_STAGE_LABELS = {
    "[1/9]": "Preprocessing audio...",
    "[2/9]": "Recognizing speakers...",
    "[3/9]": "Building speech segments...",
    "[4/9]": "Extracting speaker embeddings...",
    "[5/9]": "Clustering speakers...",
    "[6/9]": "Building speaker timeline...",
    "[7/9]": "Exporting speaker audio...",
    "[8/9]": "Transcribing...",
    "[9/9]": "Transcribing...",
}

def update_progress_from_vr_log(meeting_id: str):
    p = vr_paths(meeting_id)
    log_path = p["log"]
    if not log_path.exists():
        return

    txt = log_path.read_text(encoding="utf-8", errors="ignore")
    txt = txt[-200_000:]

    # pick the highest stage reached
    best_key = None
    best_prog = None
    for k, prog in VR_STAGE_PROGRESS.items():
        if k in txt:
            if best_prog is None or prog > best_prog:
                best_prog = prog
                best_key = k

    if best_prog is not None:
        st.session_state.progress = max(st.session_state.progress, best_prog)
        st.session_state.status_text = VR_STAGE_LABELS.get(best_key, "Voice pipeline running...")

#n8n status updates:
STATUS_PROGRESS = {
    "n8n": 0.45,
    "input": 0.50,
    "summary": 0.65,
    "tasks": 0.80,
    "trello": 0.90,
    "done": 1.0,
}

STATUS_LABELS = {
    "n8n": "n8n: Workflow started...",
    "input": "n8n: Input received...",
    "summary": "n8n: Creating summary...",
    "tasks": "n8n: Extracting tasks...",
    "trello": "n8n: Creating Trello cards...",
    "done": "n8n: Finished.",
}

def apply_n8n_status(status: dict | None):
    """
    Update session state with n8n status information
    Logs detailed debugging information for n8n communication
    """
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    if not status:
        st.session_state.status_text = "n8n: waiting for updates..."
        log(f"[{timestamp}] [n8n] No status received - waiting for updates")
        return

    stage = (status.get("stage") or status.get("type") or "").strip().lower()
    text = (status.get("text") or status.get("status") or "").strip()
    
    # Log the raw status received from n8n
    log(f"[{timestamp}] [n8n→Streamlit] Received status: stage='{stage}', text='{text}'")
    #log(f"[{timestamp}] [n8n→Streamlit] Full payload: {json.dumps(status, indent=2)}")

    if stage in STATUS_PROGRESS:
        st.session_state.status_text = STATUS_LABELS.get(stage, f"n8n: {text or stage}")
        st.session_state.progress = max(st.session_state.progress, STATUS_PROGRESS[stage])
        log(f"[{timestamp}] [n8n] Stage '{stage}' recognized - Progress: {STATUS_PROGRESS[stage]:.0%}")
        return

    # Fallback: keyword matching
    low = re.sub(r"[^a-z0-9]", "", text.lower())
    for key in STATUS_PROGRESS.keys():
        if key in low:
            st.session_state.status_text = STATUS_LABELS.get(key, f"n8n: {text}")
            st.session_state.progress = max(st.session_state.progress, STATUS_PROGRESS[key])
            log(f"[{timestamp}] [n8n] Keyword '{key}' matched in text - Progress: {STATUS_PROGRESS[key]:.0%}")
            return

    st.session_state.status_text = f"n8n: {text}" if text else "n8n: working..."
    log(f"[{timestamp}] [n8n] No stage match - using text: '{text}'")

def log(msg):
    """Add timestamped message to session logs"""
    print(msg, flush=True)
    st.session_state.logs.append(msg)

def reset_session():
    st.session_state.workflow_step = "READY"
    st.session_state.status_text = "Ready"
    st.session_state.progress = 0.0
    st.session_state.speaker_mapping = {}
    st.session_state.logs = []
    st.session_state.last_uploaded_id = None
    st.session_state.upload_key += 1
    st.session_state.file_buffer = None
    st.session_state.team_demo_override = None
    st.session_state.n8n_started = False
    st.session_state.n8n_poll_count = 0
    st.session_state.vr_pid = None
    log("Session reset completed")

def request_cancel():
    # NEW: actually stop the VR subprocess
    if st.session_state.get("meeting_id"):
        kill_vr_process(st.session_state.meeting_id)

    log("Cancellation requested by user (VR terminated)")

def save_uploaded_file(uploaded_file, meeting_id: str) -> str:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS_DIR / meeting_id
    run_dir.mkdir(parents=True, exist_ok=True)

    audio_path = run_dir / uploaded_file.name
    audio_path.write_bytes(uploaded_file.getvalue())
    log(f"File saved: {audio_path}")
    return str(audio_path)

def save_local_debug(run_dir: Path, name: str, obj):
    run_dir.mkdir(parents=True, exist_ok=True)
    p = run_dir / name
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def build_speaker_mapping(raw_mapping: dict) -> dict:
    return {
        speaker: (name if name != "Noise / Ignore" else None)
        for speaker, name in raw_mapping.items()
    }

def apply_speaker_mapping_to_transcript(transcript: list[dict], mapping: dict) -> list[dict]:
    """
    Replace the 'speaker' field in each transcript line with the assigned person name.
    Drop lines mapped to Noise/Ignore (mapping value None).
    """
    out = []
    for line in transcript:
        raw = line.get("speaker")
        mapped = mapping.get(raw, raw)

        # Noise/Ignore -> drop line
        if mapped is None:
            continue

        out.append({**line, "speaker": mapped})
    return out

st.set_page_config(page_title="ByteBrains – AI Meeting Assistant", layout="wide")

### Session States, to avoid reloading and resetting of the page after each interaction
if "workflow_step" not in st.session_state:
    st.session_state.workflow_step = "READY"
if "speaker_mapping" not in st.session_state:
    st.session_state.speaker_mapping = {}
if "assignment_confirmed" not in st.session_state:
    st.session_state.assignment_confirmed = False
if "logs" not in st.session_state:
    st.session_state.logs = []
if "progress" not in st.session_state:
    st.session_state.progress = 0.0
if "status_text" not in st.session_state:
    st.session_state.status_text = "Ready"
if "upload_key" not in st.session_state:
    st.session_state.upload_key = 0
if "meeting_id" not in st.session_state:
    st.session_state.meeting_id = None
if "audio_path" not in st.session_state:
    st.session_state.audio_path = None
if "vr_result" not in st.session_state:
    st.session_state.vr_result = None
if "last_uploaded_id" not in st.session_state:
    st.session_state.last_uploaded_id = None
if "file_buffer" not in st.session_state:
    st.session_state.file_buffer = None
if "team_demo_override" not in st.session_state:
    st.session_state.team_demo_override = None
if "n8n_started" not in st.session_state:
    st.session_state.n8n_started = False
if "n8n_poll_count" not in st.session_state:
    st.session_state.n8n_poll_count = 0
if "vr_bg_started" not in st.session_state:
    st.session_state.vr_bg_started = False
if "vr_last_stage" not in st.session_state:
    st.session_state.vr_last_stage = None

if "team" not in st.session_state:
    try:
        data = api_get_profiles()
        st.session_state.team = data.get("team", [])
        log(f"Loaded {len(st.session_state.team)} team profiles from API")
    except Exception as e:
        st.session_state.team = []
        log(f"[ERROR] Failed to load team profiles: {e}")


st.title("ByteBrains – AI Meeting Assistant")
st.markdown("Upload your meeting recording and let AI handle the rest.")

left, right = st.columns([1, 1], gap = "large")
with left:
    st.header("Upload a Meeting Recording")

    # --- Always refresh team (or keep your existing logic)
    base_team = st.session_state.get("team", [])
    demo_team = st.session_state.get("team_demo_override")
    active_team = demo_team if demo_team is not None else base_team

    eligible_profiles = [p for p in active_team if profile_state(p) == "eligible"]
    team_empty = len(active_team) == 0
    no_eligible = len(eligible_profiles) == 0

    # Block upload if there are no eligible profiles
    if team_empty:
        st.warning("No team profiles found. Please add/import profiles in 'My Team' first.")
        st.info("Upload is disabled until profiles exist.")
        file = None
    elif no_eligible:
        st.warning("No eligible profiles found for speaker mapping.")
        st.info("Please complete profiles in 'My Team' first.")

        if st.button("Use completed profiles (demo)", width="stretch"):
            demo_profiles = load_completed_profiles()
            if not demo_profiles:
                st.error("profiles_complete.json not found or empty.")
            else:
                st.session_state.team_demo_override = demo_profiles
                st.success("Switched to completed demo profiles.")
                st.rerun()

        file = None
    else:
        file = st.file_uploader(
            "Meeting Recording:",
            type=["wav", "mp3", "m4a", "mp4"],
            key=f"uploader_{st.session_state.upload_key}",
        )

    # Auto-start trigger: detect a NEW upload
    if file is not None:
        st.session_state.file_buffer = file  # store it across reruns


    start_disabled = (st.session_state.file_buffer is None)

    if st.button("Start processing", type="primary", disabled=start_disabled, width="stretch"):
        log("Start clicked → saving audio + meeting_meta.json")

        st.session_state.meeting_id = f"meeting-{int(datetime.now().timestamp())}"
        file_obj = st.session_state.file_buffer

        # save audio
        st.session_state.audio_path = save_uploaded_file(file_obj, st.session_state.meeting_id)

        # write meta + current pointer
        write_meeting_meta(
            meeting_id=st.session_state.meeting_id,
            recording_path=st.session_state.audio_path
        )

        log(f"Meeting ID: {st.session_state.meeting_id}")
        log(f"Saved audio: {st.session_state.audio_path}")

        st.session_state.status_text = "Processing your meeting..."
        st.session_state.progress = 0.1
        st.session_state.vr_pid = None
        st.session_state.workflow_step = "VR_TRANSCRIPTION"
        st.rerun()

    if st.button("Skip VR (demo)", width="stretch"):
        st.session_state.meeting_id = f"meeting-{int(datetime.now().timestamp())}"
        run_dir = RUNS_DIR / st.session_state.meeting_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # fake vr_result so UI can continue
        st.session_state.vr_result = {
            "speakers": ["Speaker 0", "Speaker 1"],
            "transcript": [
                {"speaker": "Speaker 0", "start": 0.0, "end": 2.0, "text": "Hello, this is a demo."},
                {"speaker": "Speaker 1", "start": 2.0, "end": 4.0, "text": "Great, testing n8n integration."},
            ],
        }

        st.session_state.detected_speakers = st.session_state.vr_result["speakers"]
        st.session_state.workflow_step = "UI_ASSIGNMENT"
        st.rerun()

    ###Track Status
    status_container = st.container()
    status_placeholder = st.empty()

    with status_container:
        status_placeholder.status(
            st.session_state.status_text,
            state="complete" if st.session_state.workflow_step in ["DONE", "NEXT", "READY", "UI_ASSIGNMENT"] else "running",
            expanded=True
        )
        st.progress(st.session_state.progress)

    run_active = st.session_state.workflow_step not in ["READY", "NEXT"]

    if run_active:
        if st.button("Cancel", type="secondary", width="stretch"):
            request_cancel()
            reset_session()
            st.rerun()

    if st.session_state.workflow_step == "NEXT":
        col_a, col_b = st.columns([3, 1])
        with col_a:
            if st.button("New Meeting"):
                reset_session()
                st.rerun()

        with col_b:
            if st.button("*View Results*", type="primary", width="stretch"):
                st.rerun()

    st.divider()

    with st.expander("Logs / Debug Output", expanded=False):
        st.code("\n".join(st.session_state.logs))


### Workflow  
if st.session_state.workflow_step == "VR_TRANSCRIPTION":
    st.session_state.status_text = "Starting Voice Recognition..."
    st.session_state.progress = max(st.session_state.progress, 0.12)

    if not st.session_state.get("vr_pid"):
        st.session_state.vr_pid = start_vr_subprocess(st.session_state.meeting_id)
        log(f"VR started in subprocess PID={st.session_state.vr_pid}")

    st.session_state.workflow_step = "VR_RUNNING"
    st.rerun()

if st.session_state.workflow_step == "VR_RUNNING":
    meeting_id = st.session_state.meeting_id
    p = vr_paths(meeting_id)

    update_progress_from_vr_log(meeting_id)

    # Poll status file
    if p["status"].exists():
        status = json.loads(p["status"].read_text(encoding="utf-8"))
        stage = status.get("stage")

        if stage == "done" and p["result"].exists():
            kill_vr_process(meeting_id)
            st.session_state.vr_result = json.loads(p["result"].read_text(encoding="utf-8"))
            st.session_state.detected_speakers = st.session_state.vr_result.get("speakers", [])
            st.session_state.status_text = "Voice pipeline complete."
            st.session_state.progress = max(st.session_state.progress, 0.40)
            st.session_state.workflow_step = "UI_ASSIGNMENT"
            st.rerun()

        if stage == "error":
            st.error("Voice pipeline failed.")
            st.code(status.get("trace", ""))
            st.stop()

    #st.info("VR still running. Click Refresh status or wait.")
    time.sleep(2)
    st.rerun()  

# if st.session_state.workflow_step == "VR_RECOGNITION":
#     st.session_state.status_text = "Recognizing speakers..."
#     st.session_state.progress = 0.3
#     log("Speaker Recognition")

#     speakers = st.session_state.vr_result.get("speakers", [])
#     st.session_state.detected_speakers = speakers

#     st.session_state.workflow_step = "UI_ASSIGNMENT"
#     st.rerun()

with right:
    if st.session_state.workflow_step == "UI_ASSIGNMENT":
        st.subheader("Assign speakers to team members")

        meeting_id = st.session_state.meeting_id

        # Use speakers detected by VR
        speakers = st.session_state.get("detected_speakers") or st.session_state.vr_result.get("speakers", [])
        if not speakers:
            st.error("No speakers found from Voice Recognition module.")
            st.stop()

        # Active team
        base_team = st.session_state.get("team", [])
        demo_team = st.session_state.get("team_demo_override")
        active_team = demo_team if demo_team is not None else base_team

        eligible_profiles = [p for p in active_team if profile_state(p) == "eligible"]
        team_members = [p.get("name", "") for p in eligible_profiles if p.get("name")]

        if not team_members:
            st.warning("No eligible profiles for speaker mapping.")
            st.info("To be eligible, a profile must NOT be deleted and must have: Role + at least 1 Skill.")
            st.stop()

        # Add Noise/Ignore option
        options = ["— Select person —", "Noise / Ignore"] + team_members

        # --- Locate speaker audio folder (Option B)
        speakers_audio_dir = RUNS_DIR / meeting_id / "speaker_audio"

        

        # --- Initialize mapping
        for speaker in speakers:
            if speaker not in st.session_state.speaker_mapping:
                st.session_state.speaker_mapping[speaker] = None

        # --- UI
        if not speakers_audio_dir.exists():
            st.warning(f"Speaker audio folder not found: {speakers_audio_dir}")
            st.info("UI will still work, but no speaker audio snippets can be played.")

        st.markdown("""
            <style>
            /* Style ONLY bordered containers (our "cards") */
            div[data-testid="stContainer"][data-border="true"] {
            border-radius: 14px;
            padding: 14px 14px 10px 14px;
            border: 1px solid rgba(49, 51, 63, 0.14);
            background: rgba(255,255,255,0.55);
            margin-bottom: 12px;
            }

            /* Reduce extra vertical whitespace inside the card */
            div[data-testid="stContainer"][data-border="true"] > div {
            gap: 0.35rem;
            }

            /* Make selectbox align nicely */
            div[data-testid="stContainer"][data-border="true"] .stSelectbox {
            margin-top: -2px;
            }
            </style>
            """, unsafe_allow_html=True)

        for speaker in speakers:
            pretty = pretty_speaker_label(speaker, scheme="letters")

            if speaker not in st.session_state.speaker_mapping:
                st.session_state.speaker_mapping[speaker] = None

            with st.container(border=True):
                top_l, top_r = st.columns([1.4, 3.6], vertical_alignment="center")

                with top_l:
                    st.markdown(f"**{pretty}**")

                with top_r:
                    selection = st.selectbox(
                        "Assign speaker",
                        options,
                        key=f"assign_{meeting_id}_{speaker}",
                        label_visibility="collapsed",
                    )
                    st.session_state.speaker_mapping[speaker] = (
                        None if selection == "— Select person —" else selection
                    )

                speaker_audio_map = st.session_state.vr_result.get("speaker_audio", {})
                audio_path = speaker_audio_map.get(speaker)

                if audio_path:
                    st.audio(audio_path, format="audio/wav")
                else:
                    st.caption("No speaker audio found.")

        # --- Validation (must choose something: person OR Noise/Ignore)
        all_assigned = all(
            st.session_state.speaker_mapping.get(s) is not None
            for s in speakers
        )

        if not all_assigned:
            st.warning("Please assign all speakers before continuing (choose a person or Noise / Ignore).")

        c1, c2 = st.columns([2, 3])

        with c1:
            confirm = st.button("Confirm speaker assignment", disabled=not all_assigned)

            if confirm and all_assigned and not st.session_state.n8n_started:
                log("Speaker assignment confirmed")

                transcript = st.session_state.vr_result.get("transcript")
                if transcript is None:
                    st.error("No transcript returned from Voice Recognition module.")
                    st.stop()

                # Pass-through to n8n (no final transcript building)
                profiles = eligible_profiles
                speaker_mapping = build_speaker_mapping(st.session_state.speaker_mapping)
                final_transcript = apply_speaker_mapping_to_transcript(transcript, speaker_mapping)
                st.session_state.n8n_started = True

                payload = {
                    "meeting_id": meeting_id,
                    "transcript": final_transcript,     # ✅ names are here now
                    "profiles": profiles,
                }

                run_dir = RUNS_DIR / meeting_id
                run_dir.mkdir(parents=True, exist_ok=True)

                payload_path = run_dir / "n8n_payload.json"
                with payload_path.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)

                log(f"Saved payload to {payload_path}")

                # 3. Send to n8n
                r = requests.post(
                    f"{API_BASE}/n8n/start/{meeting_id}",
                    json=payload,
                    timeout=20,
                )
                #r.raise_for_status()

                st.session_state.workflow_step = "n8n_RUNNING"
                st.session_state.progress = max(st.session_state.progress, 0.45)
                st.rerun()
            
            skip_n8n = st.button("Skip n8n (demo)", width="stretch")
            if skip_n8n and all_assigned:
                transcript = st.session_state.vr_result.get("transcript") or []
                speaker_mapping = build_speaker_mapping(st.session_state.speaker_mapping)
                final_transcript = apply_speaker_mapping_to_transcript(transcript, speaker_mapping)

                fake_result = {
                    "summary": "Demo summary (n8n skipped).",
                    "tasks": [
                        {"taskName": "Review meeting summary", "descr": "Validate the demo pipeline output.", "due_date": "", "trello_id": ""},
                    ],
                    "transcript": final_transcript,
                }

                run_dir = RUNS_DIR / meeting_id
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "n8n_result_skipped.json").write_text(
                    json.dumps(fake_result, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )

                st.session_state.n8n_result = fake_result
                st.session_state.workflow_step = "DONE"
                st.session_state.progress = 1.0
                st.rerun()

        with c2:
            if st.button("Use completed profiles"):
                demo_profiles = load_completed_profiles()
                if not demo_profiles:
                    st.error("profiles_complete.json not found or empty.")
                else:
                    st.session_state.team_demo_override = demo_profiles
                    st.success("Switched to completed demo profiles.")
                    st.rerun()

if st.session_state.workflow_step == "n8n_RUNNING":
    meeting_id = st.session_state.meeting_id

    POLL_EVERY = 8.0
    now = time.time()
    last = st.session_state.get("last_n8n_poll_ts", 0.0)
    can_poll = (now - last) >= POLL_EVERY

    c1, c2 = st.columns([1, 2])
    with c1:
        refresh = st.button("↻ Refresh status", width="stretch", disabled=not can_poll)
        remaining = max(0, int(POLL_EVERY - (now - last)))
        st.caption(f"Next refresh in {remaining}s")
    with c2:
        st.caption("Manual refresh prevents rate limits and Render restarts.")

    if not refresh:
        st.info("Click refresh to check n8n status.")
        st.stop()

    st.session_state.last_n8n_poll_ts = now
    data = api_get_n8n_status(meeting_id)

    latest = data.get("latest")
    result = data.get("result")

    run_dir = RUNS_DIR / meeting_id
    save_local_debug(run_dir, "n8n_status_latest.json", latest)
    save_local_debug(run_dir, "n8n_status_full.json", data)
    if result:
        save_local_debug(run_dir, "n8n_result_from_api.json", result)

    apply_n8n_status(latest)

    if result and (result.get("summary") or result.get("tasks") or result.get("transcript")):
        # normalize fields we care about
        result.setdefault("summary", "")
        result.setdefault("tasks", [])
        result.setdefault("transcript", [])

        st.session_state.n8n_result = result
        st.session_state.status_text = "n8n: Finished."
        st.session_state.progress = 1.0
        st.session_state.workflow_step = "DONE"
        st.rerun()

    st.info("Not finished yet. Refresh again in a few seconds.")
    st.stop()
        
if st.session_state.workflow_step == "DONE":
    st.session_state.status_text = "Done"
    st.session_state.progress = 1.0
    log("Done")

    # 1) Persist meeting results FIRST
    result = st.session_state.get("n8n_result", None)
    if result:
        summary = (result or {}).get("summary") or ""
        tasks = (result or {}).get("tasks") or []
        transcript = (result or {}).get("transcript") or []

        run_dir = RUNS_DIR / st.session_state.meeting_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "n8n_transcript.json").write_text(
            json.dumps(transcript, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        insert_meeting(
            title="Processed Meeting",
            notes=summary,
            email_draft="",
            tasks=tasks,
            meeting_id=st.session_state.meeting_id,
        )
    else:
        insert_meeting(
            title="Processed Meeting",
            notes="(placeholder notes)",
            email_draft="(placeholder email)",
            tasks=[],
            meeting_id=st.session_state.meeting_id,
        )

    # 2) Update workflow
    st.session_state.workflow_step = "NEXT"

    # 3) Tell Meetings page which meeting to open
    st.session_state["selected_meeting_id"] = st.session_state.meeting_id

    # 4) Navigate
    st.switch_page("pages/2_Meetings.py")
    

    
    


