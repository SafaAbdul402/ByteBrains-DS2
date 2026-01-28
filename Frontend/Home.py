import streamlit as st
import pandas as pd
import numpy as np
import time
import json
import os
import sys
from datetime import datetime
import requests
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]  # ByteBrains/
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from Backend.pipeline_stub import vr_process, build_final_transcript, n8n_run
from Backend.store import insert_meeting, write_meeting_meta
from Backend.config import RUNS_DIR, DATA_DIR

API_BASE = "http://localhost:8000"
PROFILES_COMPLETED_PATH = Path("data/profiles_complete.json")

def api_get_profiles():
    r = requests.get(f"{API_BASE}/profiles", timeout=10)
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

st.set_page_config(page_title="ByteBrains – AI Meeting Assistant", layout="wide")

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
if st.session_state.workflow_step == "READY":
    try:
        st.session_state.team = api_get_profiles().get("team", [])
    except:
        pass

# Block the site, if there are no team members
#if len(st.session_state.team) == 0:
 #   st.warning("No team profiles found. Please add/import profiles in 'My Team' first.")


def log(msg):
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

def request_cancel():
    st.session_state.cancel_requested = True
    st.session_state.paused = False  # cancel overrides pause

def toggle_pause():
    st.session_state.paused = not st.session_state.paused

def save_uploaded_file(uploaded_file, meeting_id: str) -> str:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS_DIR / meeting_id
    run_dir.mkdir(parents=True, exist_ok=True)

    audio_path = run_dir / uploaded_file.name
    audio_path.write_bytes(uploaded_file.getvalue())
    return str(audio_path)


st.title("ByteBrains – AI Meeting Assistant")

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

        if st.button("Use completed profiles (demo)", use_container_width=True):
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
            type=["wav", "mp3"],
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

    start_disabled = (st.session_state.file_buffer is None) or (participants is None) or (participants < 1)

    if st.button("Start processing", type="primary", disabled=start_disabled, use_container_width=True):
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

    ###Track Status
    status_container = st.container()
    status_placeholder = st.empty()

    with status_container:
        status_placeholder.status(
            st.session_state.status_text,
            state="running" if st.session_state.workflow_step not in ["READY","DONE","NEXT"] else "complete",
            expanded=True
        )
        st.progress(st.session_state.progress)

    run_active = st.session_state.workflow_step not in ["READY", "NEXT"]

    if run_active:
        c1, c2 = st.columns([1, 1])
        with c1:
            label = "Pause" if not st.session_state.paused else "Resume"
            if st.button(label, use_container_width=True):
                toggle_pause()
                st.rerun()

        with c2:
            if st.button("Cancel", type="secondary", use_container_width=True):
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
            if st.button("*View Results*", type="primary", use_container_width=True):
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
    speaker_clips = st.session_state.vr_result.get("speaker_clips", {})

    st.session_state.workflow_step = "UI_ASSIGNMENT"
    st.rerun()

if st.session_state.workflow_step == "UI_ASSIGNMENT":
    st.session_state.status_text = "Waiting for Speaker Assignment..."
    st.session_state.progress = 0.4
    log("Waiting for Speaker Assignment by user")
    time.sleep(1)
    st.session_state.workflow_step = "UI_ASSIGNMENT_2"
    st.rerun()

with right:
    if st.session_state.workflow_step == "UI_ASSIGNMENT_2":
        
        st.subheader("")
        st.subheader("")
        st.subheader("Assign speakers to team members")

        speakers = st.session_state.get("detected_speakers", ["Speaker A", "Speaker B", "Speaker C"])
        
        base_team = st.session_state.team
        demo_team = st.session_state.team_demo_override
        active_team = demo_team if demo_team is not None else base_team

        eligible_profiles = [p for p in active_team if profile_state(p) == "eligible"]
        team_members = [p.get("name","") for p in eligible_profiles if p.get("name")]
        if not team_members:
            st.warning("No eligible profiles for speaker mapping.")
            st.info("To be eligible, a profile must NOT be deleted and must have: Role + at least 1 Skill.")
            st.stop()
        options = ["— Select person —"] + team_members

        # --- Initialize mapping (important!)
        for speaker in speakers:
            if speaker not in st.session_state.speaker_mapping:
                st.session_state.speaker_mapping[speaker] = None

        # --- UI
        for speaker in speakers:
            col_speaker, col_profile = st.columns([2, 3])

            with col_speaker:
                st.markdown(f"**{speaker}**")
                clip = None
                if st.session_state.vr_result:
                    clip = st.session_state.vr_result.get("speaker_clips", {}).get(speaker)

                st.audio(clip)  # placeholder for voice clip

            with col_profile:
                selection = st.selectbox(
                    "",
                    options,
                    key=f"assign_{st.session_state.meeting_id}_{speaker}",
                    placeholder="Select person",
                )

                st.session_state.speaker_mapping[speaker] = (
                    None if selection == "— Select person —" else selection
                )

        # --- Validation
        all_assigned = all(
            st.session_state.speaker_mapping[s] is not None
            for s in speakers
        )

        if not all_assigned:
            st.warning("Please assign all speakers before continuing.")

        c1, c2 = st.columns([2, 3])
        with c1: 
            confirm = st.button(
                "Confirm speaker assignment",
                disabled=not all_assigned
                )

            if confirm and all_assigned:
                log("Speaker assignment confirmed")

                transcript = st.session_state.vr_result["transcript"]  # or raw_transcript if you use that
                final_transcript = build_final_transcript(transcript, st.session_state.speaker_mapping)
                if "final_transcript" not in st.session_state:
                    st.session_state.final_transcript = None

                profiles = eligible_profiles  # only completed + non-deleted
                st.session_state.n8n_result = n8n_run(final_transcript, profiles)

                st.session_state.workflow_step = "n8n_SUMMARIZING"
                st.rerun()
        with c2: 
            if st.button("Use completed profiles"):
                demo_profiles = load_completed_profiles()
                if not demo_profiles:
                    st.error("profiles_completed.json not found or empty.")
                else:
                    st.session_state.team_demo_override = demo_profiles
                    st.success("Switched to completed demo profiles.")
                    st.rerun()


        

if st.session_state.workflow_step == "n8n_SUMMARIZING":
    st.session_state.status_text = "Summarizing Meeting Transcript..."
    st.session_state.progress = 0.5
    log("Meeting Summary")

    st.session_state.workflow_step = "n8n_NOTES"
    st.rerun()

if st.session_state.workflow_step == "n8n_NOTES":
    st.session_state.status_text = "Creating Meeting Notes..."
    st.session_state.progress = 0.6
    log("Meeting Notes")
    time.sleep(1)
    st.session_state.workflow_step = "n8n_TASK_EXTR"
    st.rerun()

if st.session_state.workflow_step == "n8n_TASK_EXTR":
    st.session_state.status_text = "Extracting Tasks..."
    st.session_state.progress = 0.7
    log("Task Extraction")
    time.sleep(1)
    st.session_state.workflow_step = "n8n_TASK_ASSI"
    st.rerun()

if st.session_state.workflow_step == "n8n_TASK_ASSI":
    st.session_state.status_text = "Assigning Tasks..."
    st.session_state.progress = 0.8
    log("Task Assignment")
    time.sleep(1)
    st.session_state.workflow_step = "n8n_MAIL"
    st.rerun()

if st.session_state.workflow_step == "n8n_MAIL":
    st.session_state.status_text = "Writing E-Mail Draft..."
    st.session_state.progress = 0.9
    log("Mail Draft")
    time.sleep(1)
    st.session_state.workflow_step = "DONE"
    st.rerun()

if st.session_state.workflow_step == "DONE":
    st.session_state.status_text = "Done"
    st.session_state.progress = 1.0
    log("Done")

    # 1) Persist meeting results FIRST
    result = st.session_state.get("n8n_result", None)
    if result:
        insert_meeting(
            title="Processed Meeting",
            notes=result["notes"],
            email_draft=result["email_draft"],
            tasks=result["tasks"],
            meeting_id=st.session_state.meeting_id,   # << MUST
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
    st.switch_page("Frontend/pages/2_Meetings.py")
    

    
    


