from pyannote.audio import Pipeline
import torch

from pathlib import Path
import os
import torch
import numpy as np

from pyannote.audio import Model, Inference
from pyannote.audio.utils.signal import Binarize
from pyannote.core import SlidingWindowFeature, SlidingWindow


def _collapse_sliding_windows(scores):
    data = scores.data
    sw = scores.sliding_window

    W, F, C = data.shape
    frame_duration = sw.duration / F
    total_frames = int((W - 1) * (sw.step / frame_duration) + F)

    agg = np.zeros((total_frames, C), dtype=np.float32)
    count = np.zeros((total_frames, 1), dtype=np.float32)

    for w in range(W):
        frame_start = int(round(w * sw.step / frame_duration))
        frame_end = min(frame_start + F, total_frames)  # ✅ clamp
        length = frame_end - frame_start  # ✅ actual slice length

        if length <= 0:
            continue

        agg[frame_start:frame_end] += data[w][:length]
        count[frame_start:frame_end] += 1

    agg /= np.maximum(count, 1.0)

    new_sw = SlidingWindow(
        start=sw.start,
        duration=frame_duration,
        step=frame_duration,
    )

    return SlidingWindowFeature(agg, new_sw)


def load_diarization_pipeline():
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=True
    )

    if pipeline is None:
        raise RuntimeError(
            "Failed to load pyannote pipeline. "
            "Check HuggingFace token, model access, and pyannote version."
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # pyannote pipelines support .to() ONLY if successfully loaded
    pipeline.to(device)

    return pipeline
