from __future__ import annotations

from pathlib import Path
from typing import Iterable, List


AUDIO_EXTS = {".wav", ".flac", ".mp3", ".m4a", ".ogg"}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def list_audio_files(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    files: List[Path] = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS:
            files.append(p)
    return sorted(files)


def safe_stem(path: Path) -> str:
    # For "meeting 01.wav" -> "meeting_01"
    return "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in path.stem)
