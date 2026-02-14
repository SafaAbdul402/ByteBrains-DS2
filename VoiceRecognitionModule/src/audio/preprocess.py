import subprocess
from pathlib import Path
import torchaudio


SUPPORTED_INPUT_EXTENSIONS = [
    ".wav", ".mp3", ".mp4", ".m4a", ".aac",
    ".ogg", ".flac", ".webm", ".mkv", ".mov"
]


def convert_any_to_wav(input_audio: Path, output_wav: Path) -> None:
    """
    Convert ANY audio/video file to 16kHz mono WAV using ffmpeg.
    """

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_audio),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-f", "wav",
        str(output_wav)
    ]

    subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False
    )

    if not output_wav.exists():
        raise RuntimeError(f"FFmpeg failed to convert: {input_audio}")


def preprocess_audio(input_audio: Path, output_wav: Path) -> Path:
    """
    Normalize ANY input audio to 16kHz mono WAV.
    """

    if not input_audio.exists():
        raise FileNotFoundError(input_audio)

    output_wav.parent.mkdir(parents=True, exist_ok=True)

    # Always convert (even wav → normalized wav)
    convert_any_to_wav(input_audio, output_wav)

    # Final safety check
    waveform, sr = torchaudio.load(output_wav)

    if sr != 16000:
        waveform = torchaudio.functional.resample(waveform, sr, 16000)

    torchaudio.save(output_wav, waveform, 16000)

    return output_wav
