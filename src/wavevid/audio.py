"""Audio loading and analysis."""
import numpy as np
import librosa


def load_audio(path: str, sr: int = 22050) -> tuple[np.ndarray, int, float]:
    """Load audio file and return waveform, sample rate, duration."""
    y, sr = librosa.load(path, sr=sr, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)
    return y, sr, duration


def get_amplitude_envelope(y: np.ndarray, sr: int, fps: int) -> np.ndarray:
    """Extract amplitude envelope at video frame rate."""
    hop_length = sr // fps
    envelope = np.abs(y)

    # Downsample to fps
    n_frames = int(len(y) / hop_length)
    frames = np.array_split(envelope, n_frames)
    return np.array([np.max(f) if len(f) > 0 else 0 for f in frames])


def get_frequency_bands(y: np.ndarray, sr: int, fps: int, n_bands: int = 64) -> np.ndarray:
    """Extract frequency band energies for each frame."""
    hop_length = sr // fps

    # STFT
    S = np.abs(librosa.stft(y, hop_length=hop_length, n_fft=2048))

    # Mel spectrogram for perceptually-spaced bands
    mel = librosa.feature.melspectrogram(S=S**2, sr=sr, n_mels=n_bands)
    mel_db = librosa.power_to_db(mel, ref=np.max)

    # Normalize to 0-1
    mel_norm = (mel_db - mel_db.min()) / (mel_db.max() - mel_db.min() + 1e-6)
    return mel_norm.T  # Shape: (n_frames, n_bands)


def get_waveform_chunks(y: np.ndarray, sr: int, fps: int, samples_per_frame: int = 200) -> np.ndarray:
    """Get waveform chunks for each frame."""
    hop_length = sr // fps
    n_frames = int(len(y) / hop_length)

    chunks = []
    for i in range(n_frames):
        start = i * hop_length
        end = start + hop_length
        chunk = y[start:end]

        # Resample chunk to fixed size
        if len(chunk) > 0:
            indices = np.linspace(0, len(chunk) - 1, samples_per_frame).astype(int)
            resampled = chunk[indices]
        else:
            resampled = np.zeros(samples_per_frame)
        chunks.append(resampled)

    return np.array(chunks)
