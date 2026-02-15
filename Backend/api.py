from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from Backend.store import load_profiles, save_profiles
from Backend.trello_router import router as trello_router
from Backend.n8n_router import router as n8n_router

app = FastAPI(title="ByteBrains Backend")
app.include_router(trello_router)
app.include_router(n8n_router)

# allow Streamlit + n8n to call this easily
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # for demo; restrict later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Profile(BaseModel):
    id: str
    name: str
    trello_id: Optional[str] = None
    trello_username: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    skills: List[str] = []
    notes: Optional[str] = None
    photo: Optional[str] = None  # store base64 string later if you want
    status: Optional[str] = "imported"

class ProfilesPayload(BaseModel):
    team: List[Profile]

@app.get("/profiles")
def get_profiles():
    return load_profiles()

# Backend/api.py
@app.post("/profiles")
def post_profiles(payload: ProfilesPayload):
    existing = load_profiles()
    team_dicts = [p.model_dump() for p in payload.team]

    # preserve trello metadata
    existing["team"] = team_dicts
    return save_profiles(existing)

class SettingsPayload(BaseModel):
    trello_board: Optional[str] = ""

@app.get("/settings")
def get_settings():
    data = load_profiles()
    return {
        "trello_board": data.get("trello_board", "") or "",
        "trello_last_sync": data.get("trello_last_sync", None),
    }

@app.post("/settings")
def save_settings_endpoint(payload: SettingsPayload):
    data = load_profiles()
    data["trello_board"] = (payload.trello_board or "").strip()
    # keep team + last sync as-is
    return save_profiles(data)

@app.get("/health")
def health():
    return {"ok": True}