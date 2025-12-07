import sounddevice as sd
import numpy as np

# Recording settings
duration = 3  # seconds
fs = 16000    # sample rate

print("Recording for 3 seconds...")
recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
sd.wait()  # wait until recording is finished

print("Recording complete. Playing back...")
sd.play(recording, fs)
sd.wait()  # wait until playback is finished

print("Done!")
