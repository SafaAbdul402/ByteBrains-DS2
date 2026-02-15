from dotenv import load_dotenv
from pathlib import Path
import os

def load_env():
    repo_root = Path(__file__).resolve().parents[1]  # ByteBrains/
    load_dotenv(repo_root / ".env")
    return (os.getenv("API_BASE") or "").strip().rstrip("/")