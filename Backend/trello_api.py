# Backend/trello_api.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
import requests


TRELLO_API_BASE = "https://api.trello.com/1"


def extract_board_id(board_input: str) -> str:
    """
    Accepts:
      - full board URL: https://trello.com/b/yXS7VY3T/bytebrains-dsii
      - board shortlink: yXS7VY3T
      - board id: 66f.... (also works)
    Returns something Trello accepts as /boards/{idOrShortLink}
    """
    s = (board_input or "").strip()
    if not s:
        raise ValueError("Board ID/URL is empty.")

    # URL -> extract the part after /b/
    m = re.search(r"trello\.com/b/([A-Za-z0-9]+)/", s)
    if m:
        return m.group(1)

    # otherwise assume it's already shortlink or id
    return s


def fetch_board_members(api_key: str, token: str, board_input: str) -> List[Dict[str, Any]]:
    board_id = extract_board_id(board_input)

    url = f"{TRELLO_API_BASE}/boards/{board_id}/members"
    params = {
        "key": api_key,
        "token": token,
        "fields": "fullName,username,initials",
    }

    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()



def members_to_profiles(members: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    profiles: List[Dict[str, Any]] = []
    for m in members:
        tid = m.get("id")
        username = m.get("username", "")

        profiles.append(
            {
                "trello_id": tid,
                "trello_username": username,
                "name": m.get("fullName") or username or "Unknown",
            }
        )
    return profiles