"""
Generate a royalty-free ambient background pad for podcast use.

Creates a calm, low-frequency drone from filtered noise,
suitable as background bed music for spoken-word content.

Usage:
    python tools/generate_ambient_pad.py [output_path] [duration_sec]

Default output: storage/music/ambient_pad.wav (10 minutes)
"""
import sys
import os
import numpy as np
import soundfile as sf


def generate_ambient_pad(
    output_path: str,
    duration_sec: float = 600.0,
    sample_rate: int = 44100,
    base_freq: float = 55.0,       # A1 — low, warm
    chord_freqs: tuple = (65.4, 82.4, 110.0),  # C2, E2, A2 — calm major
    noise_amount: float = 0.3,
) -> str:
    """
    Generate a gentle ambient pad from filtered noise + sine layers.

    The result is a warm, non-distracting background texture that sits
    well under spoken voice without competing for attention.
    """
    num_samples = int(duration_sec * sample_rate)
    t = np.arange(num_samples, dtype=np.float32) / sample_rate

    # Layer 1: Filtered noise (the "air" / texture)
    rng = np.random.default_rng(42)
    noise = rng.normal(0, 1, num_samples).astype(np.float32)

    # Simple low-pass filter via moving average (approx 400 Hz cutoff)
    window = int(sample_rate / 400)
    kernel = np.ones(window, dtype=np.float32) / window
    noise_filtered = np.convolve(noise, kernel, mode='same')

    # Layer 2: Stack of quiet sine waves (the "warmth")
    tones = np.zeros(num_samples, dtype=np.float32)
    all_freqs = (base_freq,) + chord_freqs
    for freq in all_freqs:
        # Subtle amplitude modulation for movement
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.15 * t + freq * 0.1)
        phase = np.random.default_rng(int(freq * 100)).uniform(0, 2 * np.pi)
        tones += lfo * np.sin(2 * np.pi * freq * t + phase)

    tones *= 0.15 / len(all_freqs)

    # Mix
    pad = noise_amount * noise_filtered + (1 - noise_amount) * tones

    # Normalize to safe level
    peak = np.max(np.abs(pad))
    if peak > 0:
        pad = pad / peak * 0.25  # -12dB peak = quiet background

    # Fade in/out (5 seconds each)
    fade_len = int(sample_rate * 5.0)
    if fade_len < num_samples:
        pad[:fade_len] *= np.linspace(0, 1, fade_len, dtype=np.float32)
        pad[-fade_len:] *= np.linspace(1, 0, fade_len, dtype=np.float32)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    sf.write(output_path, pad.astype(np.float32), sample_rate)
    duration = len(pad) / sample_rate
    print(f"Generated ambient pad: {output_path} ({duration:.0f}s, {sample_rate}Hz mono)")
    return output_path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "storage/music/ambient_pad.wav"
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else 600.0
    generate_ambient_pad(out, dur)
