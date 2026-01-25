from __future__ import annotations

from pathlib import Path
import os
import numpy as np
import pandas as pd
import torch

from pyannote.audio import Model, Inference
from pyannote.audio.utils.signal import Binarize
from pyannote.core import SlidingWindowFeature, SlidingWindow

from src.utils.io import ensure_dir, safe_stem
from src.utils.paths import PROCESSED_AUDIO, SEGMENTS


def _collapse_sliding_windows(scores: SlidingWindowFeature) -> SlidingWindowFeature:
    """
    Convert (num_windows, frames_per_window, num_classes)
    into (global_frames, num_classes) using overlap-add averaging.
    """
    data = scores.data  # (W, F, C)
    sw = scores.sliding_window

    if data.ndim != 3:
        raise ValueError(f"Expected 3D scores, got {data.shape}")

    W, F, C = data.shape

    start = sw.start
    step = sw.step
    frame_duration = sw.duration / F

    total_frames = int((W - 1) * (step / frame_duration) + F)

    agg = np.zeros((total_frames, C), dtype=np.float32)
    count = np.zeros((total_frames, 1), dtype=np.float32)

    for w in range(W):
        frame_start = int(round(w * step / frame_duration))
        agg[frame_start:frame_start + F] += data[w]
        count[frame_start:frame_start + F] += 1.0

    agg /= np.maximum(count, 1.0)

    new_sw = SlidingWindow(
        start=start,
        duration=frame_duration,
        step=frame_duration,
    )

    return SlidingWindowFeature(agg, new_sw)


def segment_latest_processed() -> Path:
    """
    Neural speech segmentation on the LATEST processed WAV only.
    """
    ensure_dir(SEGMENTS)

    wavs = list(PROCESSED_AUDIO.glob("*_16k.wav"))
    if not wavs:
        raise RuntimeError("No processed audio found")

    latest_wav = max(wavs, key=lambda p: p.stat().st_mtime)
    recording = safe_stem(latest_wav)

    out_dir = SEGMENTS / recording
    ensure_dir(out_dir)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise RuntimeError("HF_TOKEN environment variable is not set")

    # Load segmentation MODEL (not pipeline)
    model = Model.from_pretrained(
        "pyannote/segmentation-3.0",
        use_auth_token=hf_token,
    ).to(device)

    inference = Inference(
        model,
        window="sliding",
        step=0.25,
        batch_size=4,   # CPU safe
        device=device,
    )

    binarize = Binarize(
        onset=0.5,
        offset=0.5,
        min_duration_on=0.3,
        min_duration_off=0.1,
    )

    # Run model
    scores = inference(str(latest_wav))  # (W, F, C)
    scores = _collapse_sliding_windows(scores)

    # Class index 1 = SPEECH for segmentation-3.0
    speech_scores = SlidingWindowFeature(
        scores.data[:, [1]],
        scores.sliding_window,
    )

    speech = binarize(speech_scores)

    rows = []
    seg_id = 0
    for segment in speech.itersegments():
        rows.append({
            "recording": recording,
            "segment_id": seg_id,
            "wav_path": str(latest_wav),
            "start_s": float(segment.start),
            "end_s": float(segment.end),
            "duration_s": float(segment.end - segment.start),
            "overlap": False,  # handled later
        })
        seg_id += 1

    out_csv = out_dir / "segments.csv"
    pd.DataFrame(rows).to_csv(out_csv, index=False)

    print(f"Segmentation written to {out_csv}")
    return out_csv
