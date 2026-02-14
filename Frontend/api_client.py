import os, time, random
import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "").rstrip("/")
SESSION = requests.Session()
DEFAULT_TTL = 60
DEMO_MODE = os.getenv("DEMO_MODE", "0") == "1"

if DEMO_MODE:
    st.set_page_config(page_title="ByteBrains – Demo", layout="centered")
    st.title("Demo deployment")
    st.info("This deployment is for n8n testing only. Please use the **n8n Demo** page.")
    if st.button("Go to n8n Demo", type="primary", use_container_width=True):
        st.switch_page("pages/99_n8n_Demo.py")
    st.stop()

def _cd(name): return f"_cooldown_until__{name}"
def _ck(name): return f"_cache__{name}"
def _ct(name): return f"_cache_ts__{name}"
def _cw(name): return f"_cooldown_warned__{name}"

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
        if not st.session_state.get(_cw(name), False):
            st.session_state[_cw(name)] = True
            st.warning(f"[api_get_json] 429 on {url}  Retry-After={r.headers.get('Retry-After')}  body={r.text[:200]}")
            ra = r.headers.get("Retry-After")
            wait_s = int(ra) if (ra and ra.isdigit()) else 10
            wait_s += random.randint(0, 3)
            st.session_state[_cd(name)] = now + wait_s
            st.session_state.setdefault("_recent_429", [])
            st.session_state["_recent_429"].append({"path": path, "t": now})
            st.session_state["_recent_429"] = st.session_state["_recent_429"][-20:]
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
        if not st.session_state.get(_cw(name), False):
            st.session_state[_cw(name)] = True
            st.warning(f"[api_post_json] 429 on {url}  Retry-After={r.headers.get('Retry-After')}  body={r.text[:200]}")
            ra = r.headers.get("Retry-After")
            wait_s = int(ra) if (ra and ra.isdigit()) else 10
            wait_s += random.randint(0, 3)
            st.session_state[_cd(name)] = now + wait_s
            st.session_state.setdefault("_recent_429", [])
            st.session_state["_recent_429"].append({"path": path, "t": now})
            st.session_state["_recent_429"] = st.session_state["_recent_429"][-20:]
            return {"_rate_limited": True, "_wait_s": wait_s, "_status": 429, "_text": r.text}

    if not r.ok:
        return {"_error": True, "_status": r.status_code, "_text": r.text}

    st.session_state[_cd(name)] = 0.0
    st.session_state[_cw(name)] = False
    return r.json()

def invalidate(name: str) -> None:
    st.session_state.pop(_ck(name), None)
    st.session_state.pop(_ct(name), None)
    st.session_state[_cd(name)] = 0.0