from pathlib import Path
import os
import numpy as np
import torch
import pandas as pd

from pyannote.audio import Model, Inference
from pyannote.audio.utils.signal import Binarize
from pyannote.core import SlidingWindowFeature, SlidingWindow


def _collapse_sliding_windows(scores: SlidingWindowFeature) -> SlidingWindowFeature:
    data = scores.data
    sw = scores.sliding_window

    W, F, C = data.shape
    frame_duration = sw.duration / F
    total_frames = int((W - 1) * (sw.step / frame_duration) + F)

    agg = np.zeros((total_frames, C), dtype=np.float32)
    count = np.zeros((total_frames, 1), dtype=np.float32)

    for w in range(W):
        frame_start = int(round(w * sw.step / frame_duration))
        agg[frame_start:frame_start + F] += data[w]
        count[frame_start:frame_start + F] += 1

    agg /= np.maximum(count, 1.0)

    new_sw = SlidingWindow(
        start=sw.start,
        duration=frame_duration,
        step=frame_duration,
    )

    return SlidingWindowFeature(agg, new_sw)


def segment_audio(processed_wav: Path) -> list[dict]:
    """
    Run neural speech segmentation on ONE WAV file.
    Returns a list of segments.
    """

    if not processed_wav.exists():
        raise FileNotFoundError(processed_wav)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        raise RuntimeError("HF_TOKEN environment variable is not set")

    model = Model.from_pretrained(
        "pyannote/segmentation-3.0",
        use_auth_token=hf_token,
    ).to(device)

    inference = Inference(
        model,
        window="sliding",
        step=0.25,
        batch_size=4,
        device=device,
    )

    binarize = Binarize(
        onset=0.5,
        offset=0.5,
        min_duration_on=0.3,
        min_duration_off=0.1,
    )

    scores = inference(str(processed_wav))
    scores = _collapse_sliding_windows(scores)

    speech_scores = SlidingWindowFeature(
        scores.data[:, [1]],
        scores.sliding_window,
    )

    speech = binarize(speech_scores)

    segments = []
    for seg_id, segment in enumerate(speech.itersegments()):
        segments.append({
            "segment_id": seg_id,
            "start": float(segment.start),
            "end": float(segment.end),
            "duration": float(segment.end - segment.start),
        })

    return segments
