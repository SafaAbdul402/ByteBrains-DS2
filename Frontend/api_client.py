import os, time, random
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "").rstrip("/")
SESSION = requests.Session()
DEFAULT_TTL = 60

def _cd(name): return f"_cooldown_until__{name}"
def _ck(name): return f"_cache__{name}"
def _ct(name): return f"_cache_ts__{name}"

def api_get_json(path: str, *, name: str, ttl_s: int = DEFAULT_TTL, timeout: int = 10) -> dict:
    now = time.time()

    cd_until = st.session_state.get(_cd(name), 0.0)
    if now < cd_until:
        wait_s = int(cd_until - now)
        return {"_rate_limited": True, "_wait_s": max(wait_s, 1), "_status": 429}

    cached = st.session_state.get(_ck(name))
    ts = st.session_state.get(_ct(name), 0.0)
    if cached is not None and (now - ts) < ttl_s:
        return cached

    url = f"{API_BASE}{path}"
    try:
        r = SESSION.get(url, timeout=timeout)
    except Exception as e:
        return {"_error": True, "_status": "network", "_text": str(e)}

    if r.status_code == 429:
        ra = r.headers.get("Retry-After")
        wait_s = int(ra) if (ra and ra.isdigit()) else 10
        wait_s += random.randint(0, 3)
        st.session_state[_cd(name)] = now + wait_s
        return {"_rate_limited": True, "_wait_s": wait_s, "_status": 429, "_text": r.text}

    if not r.ok:
        return {"_error": True, "_status": r.status_code, "_text": r.text}

    data = r.json()
    st.session_state[_ck(name)] = data
    st.session_state[_ct(name)] = now
    st.session_state[_cd(name)] = 0.0
    return data

def api_post_json(path: str, payload: dict, *, name: str = "post", timeout: int = 20) -> dict:
    now = time.time()

    cd_until = st.session_state.get(_cd(name), 0.0)
    if now < cd_until:
        wait_s = int(cd_until - now)
        return {"_rate_limited": True, "_wait_s": max(wait_s, 1), "_status": 429}

    url = f"{API_BASE}{path}"
    try:
        r = SESSION.post(url, json=payload, timeout=timeout)
    except Exception as e:
        return {"_error": True, "_status": "network", "_text": str(e)}

    if r.status_code == 429:
        ra = r.headers.get("Retry-After")
        wait_s = int(ra) if (ra and ra.isdigit()) else 10
        wait_s += random.randint(0, 3)
        st.session_state[_cd(name)] = now + wait_s
        return {"_rate_limited": True, "_wait_s": wait_s, "_status": 429, "_text": r.text}

    if not r.ok:
        return {"_error": True, "_status": r.status_code, "_text": r.text}

    st.session_state[_cd(name)] = 0.0
    return r.json()

def invalidate(name: str) -> None:
    st.session_state.pop(_ck(name), None)
    st.session_state.pop(_ct(name), None)
    st.session_state[_cd(name)] = 0.0