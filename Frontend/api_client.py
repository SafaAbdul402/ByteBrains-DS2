# Frontend/api_client.py
import os, time, random
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "").rstrip("/")
SESSION = requests.Session()

DEFAULT_TTL = 60

def _cooldown_key(name: str) -> str:
    return f"_cooldown_until__{name}"

def _cache_key(name: str) -> str:
    return f"_cache__{name}"

def _cache_ts_key(name: str) -> str:
    return f"_cache_ts__{name}"

def api_get_json(path: str, *, name: str, ttl_s: int = DEFAULT_TTL, timeout: int = 10) -> dict:
    """
    - caches per Streamlit session for ttl_s
    - honors 429 Retry-After with a cooldown (no auto rerun)
    """
    now = time.time()

    # cooldown gate (prevents hammering)
    cd_until = st.session_state.get(_cooldown_key(name), 0.0)
    if now < cd_until:
        wait_s = int(cd_until - now)
        return {"_rate_limited": True, "_wait_s": max(wait_s, 1), "_status": 429}

    # cache
    cached = st.session_state.get(_cache_key(name))
    ts = st.session_state.get(_cache_ts_key(name), 0.0)
    if cached and (now - ts) < ttl_s:
        return cached

    # call
    url = f"{API_BASE}{path}"
    r = SESSION.get(url, timeout=timeout)

    if r.status_code == 429:
        ra = r.headers.get("Retry-After")
        wait_s = int(ra) if (ra and ra.isdigit()) else 10
        # add jitter so multiple users don't retry at the same moment
        wait_s = wait_s + random.randint(0, 3)
        st.session_state[_cooldown_key(name)] = now + wait_s
        return {"_rate_limited": True, "_wait_s": wait_s, "_status": 429, "_text": r.text}

    if not r.ok:
        return {"_error": True, "_status": r.status_code, "_text": r.text}

    data = r.json()
    st.session_state[_cache_key(name)] = data
    st.session_state[_cache_ts_key(name)] = now
    st.session_state[_cooldown_key(name)] = 0.0
    return data

def invalidate(name: str) -> None:
    st.session_state.pop(_cache_key(name), None)
    st.session_state.pop(_cache_ts_key(name), None)
    st.session_state[_cooldown_key(name)] = 0.0