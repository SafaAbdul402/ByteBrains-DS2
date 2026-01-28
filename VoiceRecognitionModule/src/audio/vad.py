from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
import soundfile as sf
import webrtcvad
from tqdm import tqdm

from ..utils.io import ensure_dir, safe_stem


@dataclass
class Segment:
    start_s: float
    end_s: float


def _frame_generator(audio: np.ndarray, sr: int, frame_ms: int = 30) -> List[np.ndarray]:
    frame_len = int(sr * frame_ms / 1000)
    n = len(audio)
    frames = []
    for i in range(0, n - frame_len + 1, frame_len):
        frames.append(audio[i:i + frame_len])
    return frames


def _to_pcm16_bytes(frame: np.ndarray) -> bytes:
    frame_i16 = np.clip(frame * 32768.0, -32768, 32767).astype(np.int16)
    return frame_i16.tobytes()


def vad_segments(wav_path: Path, aggressiveness: int = 2, frame_ms: int = 30,
                 min_speech_ms: int = 300, min_silence_ms: int = 150) -> List[Segment]:
    """
    Returns speech segments using WebRTC VAD.
    Assumes wav is 16kHz mono float audio.
    """
    audio, sr = sf.read(str(wav_path))
    if sr != 16000:
        raise ValueError(f"Expected 16kHz input for VAD, got {sr}Hz: {wav_path}")
    if audio.ndim != 1:
        audio = audio.mean(axis=1)

    vad = webrtcvad.Vad(aggressiveness)

    frames = _frame_generator(audio, sr, frame_ms=frame_ms)
    is_speech = [vad.is_speech(_to_pcm16_bytes(f), sr) for f in frames]

    frame_dur = frame_ms / 1000.0

    # Convert speech flags to segments with hysteresis
    segs: List[Segment] = []
    in_speech = False
    start = 0.0

    silence_run = 0.0
    speech_run = 0.0

    for idx, flag in enumerate(is_speech):
        t = idx * frame_dur
        if flag:
            speech_run += frame_dur
            silence_run = 0.0
            if not in_speech and speech_run * 1000 >= min_speech_ms:
                in_speech = True
                start = t - speech_run + frame_dur
        else:
            silence_run += frame_dur
            speech_run = 0.0
            if in_speech and silence_run * 1000 >= min_silence_ms:
                end = t - silence_run + frame_dur
                if end > start:
                    segs.append(Segment(start_s=start, end_s=end))
                in_speech = False

    # close last
    if in_speech:
        end = len(audio) / sr
        if end > start:
            segs.append(Segment(start_s=start, end_s=end))

    # Merge tiny gaps
    merged: List[Segment] = []
    for s in segs:
        if not merged:
            merged.append(s)
        else:
            prev = merged[-1]
            if s.start_s - prev.end_s <= 0.2:  # merge short gaps
                merged[-1] = Segment(prev.start_s, max(prev.end_s, s.end_s))
            else:
                merged.append(s)

    return merged


def write_segments(wav_path: Path, segments: List[Segment], out_root: Path) -> Path:
    """
    Writes each segment as a wav file and a CSV manifest.
    Returns folder path containing segment wavs + segments.csv
    """
    audio, sr = sf.read(str(wav_path))
    if sr != 16000:
        raise ValueError("VAD expects 16kHz mono wav")

    rec_name = safe_stem(wav_path)
    out_dir = out_root / rec_name
    ensure_dir(out_dir)

    rows = []
    for i, s in enumerate(segments):
        start_i = int(s.start_s * sr)
        end_i = int(s.end_s * sr)
        chunk = audio[start_i:end_i]
        seg_path = out_dir / f"seg_{i:05d}.wav"
        sf.write(str(seg_path), chunk, sr)
        rows.append({
            "recording": rec_name,
            "segment_id": i,
            "wav_path": str(seg_path),
            "start_s": s.start_s,
            "end_s": s.end_s,
            "duration_s": float(s.end_s - s.start_s),
        })

    df = pd.DataFrame(rows)
    csv_path = out_dir / "segments.csv"
    df.to_csv(csv_path, index=False)
    return out_dir


def run_vad_on_folder(processed_audio_dir: Path, segments_dir: Path) -> None:
    """
    For each *_16k.wav in processed_audio_dir:
    - run VAD
    - write segment wav files + manifest to segments_dir/<recording_name>/
    """
    ensure_dir(segments_dir)
    wavs = sorted(processed_audio_dir.glob("*_16k.wav"))
    for wav in tqdm(wavs, desc="VAD segmenting"):
        segs = vad_segments(wav)
        write_segments(wav, segs, segments_dir)
