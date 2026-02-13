import streamlit as st
import time as pytime
import json
import os
import sys
import re
import warnings
from datetime import datetime
import requests
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]  # /src
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from Frontend.api_client import api_get_json, api_post_json, invalidate
#from Frontend.lease_client import acquire_or_block
#acquire_or_block()

#from auth import require_password

# Suppress specific warnings
warnings.filterwarnings("ignore", message="Torchaudio's I/O functions")
warnings.filterwarnings("ignore", message="Module 'speechbrain.pretrained'")

#require_password()

try:
    from Backend.pipeline_stub import vr_process
except Exception:
    def vr_process(meeting_id: str) -> dict:
        raise RuntimeError("VR module not available in this deployment. Use 'Skip VR (demo)'.")
from Backend.store import insert_meeting, write_meeting_meta
from Backend.config import RUNS_DIR

API_BASE = os.getenv("API_BASE", "")
IS_RENDER = bool(os.getenv("RENDER"))
PROFILES_COMPLETED_PATH = Path("data/profiles_complete.json")
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"

def api_get_n8n_status(meeting_id: str) -> dict:
    # ttl_s small prevents rerun spam, name includes meeting_id to avoid collisions
    return api_get_json(
        f"/n8n/status/{meeting_id}",
        name=f"n8n_status__{meeting_id}",
        ttl_s=3,
        timeout=10,
    )

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

def find_speaker_wavs(speakers_audio_dir: Path, speaker_id: str) -> list[Path]:
    if not speakers_audio_dir.exists():
        return []
    return sorted([p for p in speakers_audio_dir.glob("*.wav") if speaker_id in p.name])

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

    stage = (status.get("stage") or "").strip().lower()
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
    st.session_state.logs.append(msg)

def reset_session():
    st.session_state.workflow_step = "READY"
    st.session_state.status_text = "Ready"
    st.session_state.progress = 0.0
    st.session_state.speaker_mapping = {}
    st.session_state.logs = []
    st.session_state.cancel_requested = False
    st.session_state.paused = False
    st.session_state.last_uploaded_id = None
    st.session_state.upload_key += 1
    st.session_state.file_buffer = None
    st.session_state.participants = None
    st.session_state.team_demo_override = None
    st.session_state.n8n_started = False
    st.session_state.n8n_poll_count = 0
    st.session_state.vr_demo = False
    log("Session reset completed")

def request_cancel():
    st.session_state.cancel_requested = True
    st.session_state.paused = False  # cancel overrides pause
    log("Cancellation requested by user")

def toggle_pause():
    st.session_state.paused = not st.session_state.paused
    state = "paused" if st.session_state.paused else "resumed"
    log(f"Workflow {state}")

def save_uploaded_file(uploaded_file, meeting_id: str) -> str:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS_DIR / meeting_id
    run_dir.mkdir(parents=True, exist_ok=True)

    audio_path = run_dir / uploaded_file.name
    audio_path.write_bytes(uploaded_file.getvalue())
    log(f"File saved: {audio_path}")
    return str(audio_path)

def build_speaker_mapping(raw_mapping: dict) -> dict:
    return {
        speaker: (name if name != "Noise / Ignore" else None)
        for speaker, name in raw_mapping.items()
    }

def apply_speaker_mapping(transcript: list[dict], mapping: dict) -> list[dict]:
    return [
        {**line, "speaker": mapping.get(line["speaker"], line["speaker"])}
        for line in transcript
    ]

def status_state_for_step(step: str) -> str:
    step = (step or "").upper()

    if step in ["READY", "UI_ASSIGNMENT", "UI_ASSIGNMENT_2", "NEXT"]:
        return "complete"   # no spinner

    if step in ["DONE"]:
        return "complete"

    if step in ["ERROR", "FAILED"]:
        return "error"

    # VR_TRANSCRIPTION, VR_RECOGNITION, n8n_RUNNING, etc.
    return "running"

st.set_page_config(page_title="ByteBrains – AI Meeting Assistant", layout="wide")

if DEMO_MODE:
    demo_profiles = load_completed_profiles()
    st.session_state.team_demo_override = demo_profiles

### Session States, to avoid reloading and resetting of the page after each interaction
if "paused" not in st.session_state:
    st.session_state.paused = False
if "cancel_requested" not in st.session_state:
    st.session_state.cancel_requested = False
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
if "participants" not in st.session_state:
    st.session_state.participants = None
if "file_buffer" not in st.session_state:
    st.session_state.file_buffer = None
if "team_demo_override" not in st.session_state:
    st.session_state.team_demo_override = None
if "n8n_started" not in st.session_state:
    st.session_state.n8n_started = False
if "n8n_poll_count" not in st.session_state:
    st.session_state.n8n_poll_count = 0
if "last_n8n_poll_ts" not in st.session_state:
    st.session_state.last_n8n_poll_ts = 0.0
if "n8n_started_at" not in st.session_state:
    st.session_state.n8n_started_at = None
if "vr_demo" not in st.session_state:
    st.session_state.vr_demo = False

if "team" not in st.session_state:
    st.session_state.team = []
    st.session_state.team_loaded = False

if not st.session_state.team_loaded:
    data = api_get_json("/profiles", name="profiles", ttl_s=60)

    if data.get("_rate_limited"):
        st.warning(f"Backend rate limited (429). Wait ~{data.get('_wait_s', 10)}s then click Retry.")
        st.write("Recent 429s:", st.session_state.get("_recent_429", []))
        if st.button("Retry"):
            invalidate("profiles")
            st.rerun()
        st.stop()

    # IMPORTANT: safe_get_json uses r.raise_for_status(), so wrap it
    if data.get("_error"):
        st.error("Could not load profiles from backend.")
        st.code(f"HTTP {data.get('_status')}: {data.get('_text')}")
        st.stop()

    st.session_state.team = data.get("team", [])
    st.session_state.team_loaded = True
    log(f"Loaded {len(st.session_state.team)} team profiles from API")


st.title("ByteBrains – AI Meeting Assistant")
st.markdown("Upload your meeting recording and let AI handle the rest.")

# If paused, don't advance the workflow
if st.session_state.get("paused", False) and st.session_state.workflow_step not in ["READY", "NEXT"]:
    st.info("Paused. Click Resume to continue.")
    st.stop()

# If cancel requested, reset and stop
if st.session_state.get("cancel_requested", False):
    reset_session()
    st.stop()

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

    participants = st.number_input(
        "# Meeting participants",
        min_value=1,
        max_value=50,
        step=1,
        value=st.session_state.participants or 1
    )
    st.session_state.participants = participants

    start_disabled = IS_RENDER or (st.session_state.file_buffer is None) or (participants is None) or (participants < 1)

    if IS_RENDER:
        st.info("Demo deployment: Voice Recognition is disabled. Use **Skip VR (demo)** to test n8n integration.")

    if st.button("Start processing", type="primary", disabled=start_disabled, width="stretch"):
        log("Start clicked → saving audio + meeting_meta.json")

        st.session_state.meeting_id = f"meeting-{int(datetime.now().timestamp())}"
        file_obj = st.session_state.file_buffer

        # save audio
        st.session_state.audio_path = save_uploaded_file(file_obj, st.session_state.meeting_id)

        # write meta + current pointer
        write_meeting_meta(
            meeting_id=st.session_state.meeting_id,
            participants=st.session_state.participants,
            recording_path=st.session_state.audio_path
        )

        log(f"Meeting ID: {st.session_state.meeting_id}")
        log(f"Participants: {participants}")
        log(f"Saved audio: {st.session_state.audio_path}")

        st.session_state.status_text = "Processing meeting..."
        st.session_state.progress = 0.1
        st.session_state.workflow_step = "VR_TRANSCRIPTION"
        st.rerun()

    if st.button("Skip VR (demo)", width="stretch"):
        st.session_state.vr_demo = True
        st.session_state.meeting_id = f"meeting-{int(datetime.now().timestamp())}"

        # fake vr_result so UI can continue
        st.session_state.vr_result = {
            "speakers": ["SPEAKER_0", "SPEAKER_1"],
            "transcript": [
                {"speaker": "SPEAKER_0", "start": 0.0, "end": 2.0, "text": "Hello, this is a demo."},
                {"speaker": "SPEAKER_1", "start": 2.0, "end": 4.0, "text": "Great, testing n8n integration."},
            ],
        }

        st.session_state.detected_speakers = st.session_state.vr_result["speakers"]
        st.session_state.workflow_step = "UI_ASSIGNMENT_2"
        st.rerun()

    ###Track Status
    status_container = st.container()
    status_placeholder = st.empty()

    with status_container:
        status_placeholder.status(
            st.session_state.status_text,
            state=status_state_for_step(st.session_state.workflow_step),
            expanded=True
        )
        st.progress(st.session_state.progress)

    run_active = st.session_state.workflow_step not in ["READY", "NEXT"]

    if run_active:
        c1, c2 = st.columns([1, 1])
        with c1:
            label = "Pause" if not st.session_state.paused else "Resume"
            if st.button(label, width="stretch"):
                toggle_pause()
                st.rerun()

        with c2:
            if st.button("Cancel", type="secondary", width="stretch"):
                request_cancel()
                reset_session()
                st.rerun()

    if st.session_state.workflow_step == "NEXT":
        if IS_RENDER:
            st.success("Done (demo). Here are the results from n8n:")

            res = st.session_state.get("n8n_result", {}) or {}
            st.subheader("Summary / Notes")
            st.write(res.get("notes") or res.get("Summary") or "(empty)")

            st.subheader("Tasks")
            st.json(res.get("tasks", []))

            st.subheader("Email Draft")
            st.write(res.get("email_draft", "(none)"))

            if st.button("New Meeting", use_container_width=True):
                reset_session()
                st.rerun()

        else:
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
    st.session_state.status_text = "Transcribing meeting..."
    st.session_state.progress = 0.2
    log("Transcription")

    # VR call
    st.session_state.vr_result = vr_process(st.session_state.meeting_id)

    st.session_state.workflow_step = "VR_RECOGNITION"
    st.rerun()

if st.session_state.workflow_step == "VR_RECOGNITION":
    st.session_state.status_text = "Recognizing speakers..."
    st.session_state.progress = 0.3
    log("Speaker Recognition")

    speakers = st.session_state.vr_result.get("speakers", [])
    st.session_state.detected_speakers = speakers

    st.session_state.workflow_step = "UI_ASSIGNMENT"
    st.rerun()

if st.session_state.workflow_step == "UI_ASSIGNMENT":
    st.session_state.status_text = "Waiting for Speaker Assignment..."
    st.session_state.progress = 0.4
    log("Waiting for Speaker Assignment by user")
    pytime.sleep(1)
    st.session_state.workflow_step = "UI_ASSIGNMENT_2"
    st.rerun()

with right:
    if st.session_state.workflow_step == "UI_ASSIGNMENT_2":
        st.subheader("")
        st.subheader("")
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
        is_demo = st.session_state.get("vr_demo", False) or IS_RENDER
        speakers_audio_dir = None if is_demo else (RUNS_DIR / meeting_id / "speaker_audio")

        

        # --- Initialize mapping
        for speaker in speakers:
            if speaker not in st.session_state.speaker_mapping:
                st.session_state.speaker_mapping[speaker] = None

        # --- UI
        if (not is_demo) and speakers_audio_dir and (not speakers_audio_dir.exists()):
            st.warning(f"Speaker audio folder not found: {speakers_audio_dir}")
            st.info("UI will still work, but no speaker audio snippets can be played.")

        for speaker in speakers:
            col_speaker, col_profile = st.columns([2, 3])

            with col_speaker:
                st.markdown(f"**{pretty_speaker_label(speaker, scheme='letters')}**")
                #st.caption(f"Internal ID: {speaker}")  # optional, remove if you don’t want it shown            

                if is_demo:
                    st.caption("Demo mode: no audio snippets available.")
                else:
                    if speakers_audio_dir is None:
                        st.caption("No speaker audio directory.")
                    else:
                        wavs = find_speaker_wavs(speakers_audio_dir, speaker)
                        if wavs:
                            max_snippets = 5
                            for w in wavs[:max_snippets]:
                                st.audio(str(w), format="audio/wav")
                            if len(wavs) > max_snippets:
                                st.caption(f"...and {len(wavs) - max_snippets} more snippet(s)")
                        else:
                            st.caption("No .wav snippets found for this speaker.")

            with col_profile:
                selection = st.selectbox(
                    "Assign speaker",
                    options,
                    key=f"assign_{meeting_id}_{speaker}",
                    label_visibility="collapsed",
                )

                st.session_state.speaker_mapping[speaker] = (
                    None if selection == "— Select person —" else selection
                )

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

            skip_n8n = st.button("Skip n8n (demo)", type="secondary", use_container_width=True)

            if skip_n8n:
                log("Skip n8n clicked → using dummy result")

                # make sure meeting_id exists
                if not st.session_state.meeting_id:
                    st.session_state.meeting_id = f"meeting-{int(datetime.now().timestamp())}"

                # ensure run dir exists
                #run_dir = RUNS_DIR / st.session_state.meeting_id
                #run_dir.mkdir(parents=True, exist_ok=True)

                # create dummy result
                dummy = {
                    "Summary": "✅ Demo summary: We discussed project status, next steps, and ownership.",
                    "notes": "✅ Demo summary: We discussed project status, next steps, and ownership.",
                    "tasks": [],
                    "email_draft": "(no email draft in this project)",
                }
                st.session_state.n8n_result = dummy
                st.session_state.status_text = "n8n: (skipped) Finished."
                st.session_state.progress = 1.0

                # jump to DONE
                st.session_state.workflow_step = "DONE"
                st.rerun()

            if confirm and all_assigned and not st.session_state.n8n_started:
                log("Speaker assignment confirmed")

                transcript = st.session_state.vr_result.get("transcript")
                if transcript is None:
                    st.error("No transcript returned from Voice Recognition module.")
                    st.stop()

                speaker_mapping = build_speaker_mapping(st.session_state.speaker_mapping)

                st.session_state.n8n_started = True
                final_transcript = apply_speaker_mapping(transcript, speaker_mapping)

                # Pass-through to n8n (no final transcript building)
                profiles = eligible_profiles
                payload = {
                    "meeting_id": meeting_id,
                    "transcript": final_transcript,
                    "profiles": profiles,
                }

                #run_dir = RUNS_DIR / meeting_id
                #run_dir.mkdir(parents=True, exist_ok=True)

                #payload_path = run_dir / "n8n_payload.json"
                #with payload_path.open("w", encoding="utf-8") as f:
                 #   json.dump(payload, f, ensure_ascii=False, indent=2)
                #meetingID_path = run_dir / "meeting_ID.json"
                #with meetingID_path.open("w", encoding="utf-8") as f:
                 #   json.dump(meeting_id, f, ensure_ascii=False, indent=2)
                #transcript_path = run_dir / "transcript.json"
                #with transcript_path.open("w", encoding="utf-8") as f:
                 #   json.dump(final_transcript, f, ensure_ascii=False, indent=2)

                #log(f"Saved payload to {payload_path}")

                #payload_txt_path = run_dir / "n8n_payload.txt"
                #payload_txt = json.dumps(payload, ensure_ascii=False, indent=2)
                #payload_txt_path.write_text(payload_txt, encoding="utf-8")

                #log(f"Saved payload to {payload_txt_path}")

                res = api_post_json(
                    f"/n8n/start/{meeting_id}",
                    payload,
                    name=f"n8n_start__{meeting_id}",
                    timeout=30,
                )

                if res.get("_rate_limited"):
                    st.warning(f"Backend rate limited (429). Wait ~{res.get('_wait_s', 10)}s and try again.")
                    st.stop()

                if res.get("_error"):
                    st.error("Failed to start n8n workflow.")
                    st.code(f"HTTP {res.get('_status')}: {res.get('_text')[:400]}")
                    st.stop()

                log("POST /n8n/start accepted")

                st.session_state.workflow_step = "n8n_RUNNING"
                st.session_state.n8n_started_at = pytime.time()
                st.session_state.progress = max(st.session_state.progress, 0.45)
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

    # timeout
    if st.session_state.n8n_started_at and (pytime.time() - st.session_state.n8n_started_at > 600):
        st.error("n8n timeout (no result after 10 minutes)")
        st.stop()

    # poll gating: only allow a poll every 8 seconds
    POLL_EVERY = 10.0
    now = pytime.time()
    last = st.session_state.get("last_n8n_poll_ts", 0.0)

    can_poll = (now - last) >= POLL_EVERY

    # UI controls
    c1, c2 = st.columns([1, 2])
    with c1:
        refresh = st.button("↻ Refresh status", use_container_width=True, disabled=not can_poll)
        remaining = max(0, int(POLL_EVERY - (now - last)))
        st.caption(f"Next allowed refresh in {remaining}s")
    with c2:
        st.caption(f"Polling every {int(POLL_EVERY)}s (manual refresh button).")

    # If we can't poll yet, do NOT rerun-spam
    if not can_poll and not refresh:
        st.info("Waiting…")
        st.stop()

    # Perform exactly one poll
    st.session_state.last_n8n_poll_ts = now
    data = api_get_n8n_status(meeting_id)

    if data.get("_rate_limited"):
        st.warning(f"Backend rate limited (429). Wait ~{data.get('_wait_s', 10)}s then click Retry.")
        if st.button("Retry"):
            st.rerun()
        st.stop()

    latest = data.get("latest")
    result = data.get("result")
    apply_n8n_status(latest)

    if result and (result.get("notes") or result.get("Summary")):
        result.setdefault("notes", result.get("Summary", "(summary missing)"))
        result.setdefault("email_draft", "(placeholder email)")
        result.setdefault("tasks", [])
        st.session_state.n8n_result = result
        st.session_state.status_text = "n8n: Finished."
        st.session_state.progress = 1.0
        st.session_state.workflow_step = "DONE"
        st.rerun()

    # Not done: show status and stop. No auto loop.
    st.info("Not finished yet. Click Refresh status again in a few seconds.")
    st.stop()
        
if st.session_state.workflow_step == "DONE":
    st.session_state.status_text = "Done"
    st.session_state.progress = 1.0
    log("Done")

    result = st.session_state.get("n8n_result")

    if not IS_RENDER:
        # keep your existing persistence
        if result:
            insert_meeting(
                title="Processed Meeting",
                notes=result.get("notes", ""),
                email_draft=result.get("email_draft", ""),
                tasks=result.get("tasks", []),
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

        st.session_state.workflow_step = "NEXT"
        st.session_state["selected_meeting_id"] = st.session_state.meeting_id
        st.switch_page("pages/2_Meetings.py")

    else:
        # DEMO: show results inline and stop navigation
        st.session_state.workflow_step = "NEXT"