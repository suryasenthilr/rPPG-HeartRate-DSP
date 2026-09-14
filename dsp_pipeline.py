"""
DSP Pipeline for Remote Photoplethysmography (rPPG) System
-----------------------------------------------------------
Implements:
1. Signal Buffering & Timestamp Management
2. Baseline Detrending & Normalization
3. 4th-Order Zero-Phase Butterworth Bandpass Filtering
4. Zero-Padded Windowed Fast Fourier Transform (FFT)
5. Peak Detection & Real-Time BPM Estimation
6. Signal-to-Noise Ratio (SNR) & Confidence Scoring
7. Multiple rPPG extraction methods:
   - Pure Green Channel (Classic rPPG)
   - CHROM (Chrominance-based method for motion/illumination artifact rejection)
"""

from collections import deque
import numpy as np
import scipy.signal
import scipy.ndimage


class RPPGSignalProcessor:
    """
    Digital Signal Processor for real-time BVP (Blood Volume Pulse) extraction.
    """

    def __init__(
        self,
        buffer_size: int = 250,
        low_bpm: float = 45.0,
        high_bpm: float = 180.0,
        method: str = "green",
    ):
        """
        Parameters:
        -----------
        buffer_size : int
            Number of recent frames to store in the temporal buffer (~8-10 seconds at 30 fps).
        low_bpm : float
            Lower bound of physiological heart rate (default 45 BPM = 0.75 Hz).
        high_bpm : float
            Upper bound of physiological heart rate (default 180 BPM = 3.0 Hz).
        method : str
            rPPG extraction method: 'green' or 'chrom'.
        """
        self.buffer_size = buffer_size
        self.min_freq = low_bpm / 60.0  # Hz (~0.75 Hz)
        self.max_freq = high_bpm / 60.0  # Hz (~3.00 Hz)
        self.method = method.lower()

        # Buffers for raw spatial mean signals and frame arrival timestamps
        self.raw_r = deque(maxlen=buffer_size)
        self.raw_g = deque(maxlen=buffer_size)
        self.raw_b = deque(maxlen=buffer_size)
        self.timestamps = deque(maxlen=buffer_size)

        # Smoothed state
        self.smooth_bpm = 0.0
        self.bpm_history = deque(maxlen=30)
        self.snr = 0.0
        self.confidence = 0.0  # 0.0 to 1.0
        self.hold_frames = 0  # Persistence hold counter for transient noise/movement
        self.smooth_power: np.ndarray | None = None  # Rolling average power spectrum

    def reset(self):
        """Clears all signal buffers and resets state."""
        self.raw_r.clear()
        self.raw_g.clear()
        self.raw_b.clear()
        self.timestamps.clear()
        self.bpm_history.clear()
        self.smooth_bpm = 0.0
        self.snr = 0.0
        self.confidence = 0.0
        self.hold_frames = 0
        self.smooth_power = None

    def add_sample(self, r: float, g: float, b: float, timestamp: float):
        """
        Appends spatial average RGB values and frame arrival timestamp to buffer.
        Enforces a 7.5-second temporal duration window so that low-framerate webcams
        do not trap 15-20 seconds of old motion in the buffer.
        """
        self.raw_r.append(r)
        self.raw_g.append(g)
        self.raw_b.append(b)
        self.timestamps.append(timestamp)

        # Enforce temporal buffer duration (7.5 seconds)
        while len(self.timestamps) > 40 and (self.timestamps[-1] - self.timestamps[0] > 7.5):
            self.raw_r.popleft()
            self.raw_g.popleft()
            self.raw_b.popleft()
            self.timestamps.popleft()

    def estimate_sampling_rate(self) -> float:
        """
        Calculates empirical frame rate (Fs) across the entire stored buffer.
        Using total duration (t_last - t_first) eliminates frame-to-frame timestamp jitter
        so that FFT frequency bins remain completely stable.
        """
        n = len(self.timestamps)
        if n < 5:
            return 30.0
        total_time = self.timestamps[-1] - self.timestamps[0]
        if total_time <= 0.1:
            return 30.0
        measured_fs = (n - 1) / total_time
        return float(np.clip(measured_fs, 15.0, 60.0))

    def _extract_raw_pulse(self) -> np.ndarray:
        """
        Extracts raw pulse signal from RGB buffers based on selected method:
        - 'green': Spatial average of the Green color channel.
        - 'chrom': Chrominance-based method (Haan & Jeanne, 2013).
        """
        r = np.array(self.raw_r, dtype=np.float64)
        g = np.array(self.raw_g, dtype=np.float64)
        b = np.array(self.raw_b, dtype=np.float64)

        # Per-frame total spatial luminance L(t) = (r + g + b) / 3
        # Normalizing by L(t) cancels out webcam auto-exposure steps, room light changes, and AC flicker
        luminance = (r + g + b) / 3.0 + 1e-6
        rn = r / luminance
        gn = g / luminance
        bn = b / luminance

        if self.method == "chrom":
            # Chrominance method (de Haan & Jeanne, 2013)
            # Use chromaticity normalized signals
            xs = 3.0 * rn - 2.0 * gn
            ys = 1.5 * rn + gn - 1.5 * bn

            std_xs = np.std(xs)
            std_ys = np.std(ys)

            if std_ys > 1e-6:
                alpha = std_xs / std_ys
                pulse = xs - alpha * ys
            else:
                pulse = xs
            return pulse
        else:
            # Normalized Green channel:
            # Hemoglobin absorbs green light relative to total illumination
            # Invert (-gn) so systolic blood volume expansion appears as an upward peak
            return -gn

    def detrend_signal(self, signal: np.ndarray, fs: float) -> np.ndarray:
        """
        Removes baseline drift and low-frequency motion artifacts.
        Combines linear detrending with a 2.0-second moving average subtraction
        so that cardiac frequencies (1.0-2.5 Hz) are preserved without being notched out.
        """
        # Step 1: Linear detrending
        detrended = scipy.signal.detrend(signal, type="linear")

        # Step 2: Moving average high-pass (~2.0 seconds cutoff ~0.5 Hz)
        # Using mode='nearest' eliminates zero-padding edge spikes that ring through the IIR filter
        win_size = int(max(7, round(fs * 2.0)))
        if win_size % 2 == 0:
            win_size += 1

        if len(detrended) > win_size:
            baseline = scipy.ndimage.uniform_filter1d(detrended, size=win_size, mode="nearest")
            detrended = detrended - baseline

        # Step 3: Zero-mean unit-variance standardization
        std = np.std(detrended)
        if std > 1e-6:
            detrended = (detrended - np.mean(detrended)) / std

        return detrended

    def butterworth_bandpass_filter(
        self, signal: np.ndarray, fs: float, order: int = 2
    ) -> np.ndarray:
        """
        Applies a zero-phase digital Butterworth bandpass filter.
        Uses Second-Order Sections (SOS) for numerical stability.

        Passband: [min_freq, max_freq] (e.g. 0.75 Hz to 2.5 Hz = 45 to 150 BPM).
        sosfiltfilt provides zero phase distortion (forward-backward filtering).
        """
        nyquist = 0.5 * fs
        low = self.min_freq / nyquist
        high = self.max_freq / nyquist

        # Guard against invalid normalized frequencies if Fs drops temporarily
        low = max(0.01, min(low, 0.95))
        high = max(low + 0.05, min(high, 0.99))

        sos = scipy.signal.butter(
            order, [low, high], btype="bandpass", output="sos"
        )
        # Apply zero-phase bidirectional filter
        # Minimum signal length required for sosfiltfilt is typically 3 * order
        if len(signal) > 3 * (2 * order + 1):
            filtered = scipy.signal.sosfiltfilt(sos, signal)
        else:
            filtered = scipy.signal.sosfilt(sos, signal)

        return filtered

    def compute_fft(
        self, signal: np.ndarray, fs: float, n_fft: int = 2048
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Computes windowed Fast Fourier Transform (FFT) with zero-padding.

        Returns:
        --------
        freqs : np.ndarray
            Frequency bins in Hz.
        power_spectrum : np.ndarray
            Normalized power spectral density for each frequency bin.
        """
        n_samples = len(signal)
        # Apply Hanning window to reduce spectral leakage
        window = np.hanning(n_samples)
        windowed_signal = signal * window

        # Zero-pad to n_fft for fine frequency resolution (< 1 BPM per bin)
        n_points = max(n_fft, 2 ** int(np.ceil(np.log2(n_samples)) + 1))
        fft_result = np.fft.rfft(windowed_signal, n=n_points)
        freqs = np.fft.rfftfreq(n_points, d=1.0 / fs)

        # Power spectrum
        power = np.abs(fft_result) ** 2
        max_power = np.max(power) if np.max(power) > 0 else 1.0
        normalized_power = power / max_power

        return freqs, normalized_power

    def extract_bpm_and_snr(
        self, freqs: np.ndarray, power: np.ndarray
    ) -> tuple[float, float, float]:
        """
        Identifies the dominant cardiac frequency in the physiological band,
        computes Heart Rate (BPM), SNR, and confidence score.
        Uses peak-to-noise floor contrast and statistical prominence.
        """
        # Mask for physiological cardiac frequency range
        valid_mask = (freqs >= self.min_freq) & (freqs <= self.max_freq)
        valid_freqs = freqs[valid_mask]
        valid_power = power[valid_mask]

        if len(valid_power) == 0:
            return 0.0, 0.0, 0.0

        # Find local peaks in the spectrum separated by at least ~6 BPM (0.10 Hz)
        freq_step = freqs[1] - freqs[0] if len(freqs) > 1 else 0.015
        min_dist = max(1, int(round(0.10 / freq_step)))
        peak_indices, _ = scipy.signal.find_peaks(valid_power, distance=min_dist)

        # Restrict peak search away from the absolute frequency boundary edges (respiratory leakage band)
        # Physiological resting-to-exercise cardiac band: 50 BPM (0.83 Hz) to 170 BPM (2.83 Hz)
        interior_mask = (valid_freqs >= 0.82) & (valid_freqs <= 2.80)
        interior_indices = np.where(interior_mask)[0]

        if len(interior_indices) > 0:
            search_indices = [p for p in peak_indices if p in interior_indices]
            if len(search_indices) == 0:
                # If no sharp local peak in interior, select highest interior bin
                peak_idx = int(interior_indices[int(np.argmax(valid_power[interior_indices]))])
            else:
                if self.smooth_bpm > 0 and len(self.bpm_history) >= 3:
                    prev_freq = self.smooth_bpm / 60.0
                    scores = []
                    for p_i in search_indices:
                        f = valid_freqs[p_i]
                        p = valid_power[p_i]
                        continuity_weight = np.exp(-((f - prev_freq) ** 2) / (2.0 * (0.35 ** 2)))
                        scores.append(p * (0.35 + 0.65 * continuity_weight))
                    peak_idx = int(search_indices[int(np.argmax(scores))])
                else:
                    peak_idx = int(search_indices[int(np.argmax(valid_power[search_indices]))])
        else:
            peak_idx = int(np.argmax(valid_power))

        peak_freq = float(valid_freqs[peak_idx])
        raw_bpm = peak_freq * 60.0

        # Peak band: peak_freq +/- 0.12 Hz (~7.2 BPM window around peak)
        peak_band = 0.12
        signal_mask = np.abs(valid_freqs - peak_freq) <= peak_band
        signal_power = float(np.sum(valid_power[signal_mask]))
        total_power = float(np.sum(valid_power)) + 1e-8
        noise_power = max(total_power - signal_power, 1e-8)

        # Spectral energy concentration ratio in peak
        concentration = signal_power / total_power
        snr_linear = signal_power / noise_power
        snr_db = float(10.0 * np.log10(max(snr_linear, 1e-3)))

        # Continuous confidence mapping
        # Diffuse noise: concentration ~ 0.18-0.22
        # Clean cardiac peak: concentration >= 0.40
        conf = float(np.clip((concentration - 0.18) / 0.35, 0.05, 1.0))

        return raw_bpm, snr_db, conf

    def process(
        self,
    ) -> tuple[float, float, float, np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        """
        Full DSP processing execution on current buffered samples.

        Returns:
        --------
        bpm : float
            Smoothed heart rate in BPM.
        raw_bpm : float
            Instantaneous heart rate in BPM.
        confidence : float
            Confidence metric [0.0, 1.0].
        filtered_pulse : np.ndarray | None
            Filtered time-domain BVP waveform.
        freqs : np.ndarray | None
            FFT frequency bins in Hz.
        power : np.ndarray | None
            FFT normalized power spectrum.
        """
        n_samples = len(self.raw_g)
        # Minimum frames needed for meaningful DSP estimation (~2.5 seconds)
        if n_samples < 50:
            return 0.0, 0.0, 0.0, None, None, None

        fs = self.estimate_sampling_rate()
        if fs < 10.0:
            return 0.0, 0.0, 0.0, None, None, None

        # 1. Multi-channel signal extraction
        raw_signal = self._extract_raw_pulse()

        # 2. Linear & moving average detrending
        detrended = self.detrend_signal(raw_signal, fs)

        # 3. 4th-order Butterworth bandpass filtering (0.75 - 3.0 Hz)
        filtered_pulse = self.butterworth_bandpass_filter(detrended, fs)

        # 4. Zero-padded windowed FFT
        freqs, power = self.compute_fft(filtered_pulse, fs, n_fft=2048)

        # Temporal spectral averaging (textbook DSP):
        # Random noise phases cancel out across frames while true periodic cardiac peak reinforces
        if self.smooth_power is None or len(self.smooth_power) != len(power):
            self.smooth_power = power.copy()
        else:
            self.smooth_power = 0.85 * self.smooth_power + 0.15 * power

        # Keep smoothed spectrum peak normalized
        max_sp = np.max(self.smooth_power)
        if max_sp > 0:
            self.smooth_power = self.smooth_power / max_sp

        # 5. Peak detection & SNR calculation on smoothed power spectrum
        raw_bpm, snr_db, conf = self.extract_bpm_and_snr(freqs, self.smooth_power)
        if self.snr == 0.0:
            self.snr = snr_db
        else:
            self.snr = 0.94 * self.snr + 0.06 * snr_db

        # Rate stability metric: measures physiological continuity of the pulse
        if self.smooth_bpm > 0 and len(self.bpm_history) >= 3:
            bpm_diff = abs(raw_bpm - self.smooth_bpm)
            stability = float(np.exp(-(bpm_diff ** 2) / (2.0 * (12.0 ** 2))))
            conf_combined = float(np.clip(0.60 * conf + 0.40 * stability, 0.05, 0.95))
        else:
            conf_combined = float(np.clip(conf, 0.05, 0.90))

        # Calm temporal smoothing: holds stable reading without jumping or oscillating
        if self.confidence <= 0.05:
            self.confidence = conf_combined
        else:
            self.confidence = 0.96 * self.confidence + 0.04 * conf_combined

        # 6. Post-processing: Exponential Moving Average (EMA) with Persistence Hold
        if raw_bpm > 0:
            if conf_combined >= 0.25:
                if self.smooth_bpm == 0.0:
                    self.smooth_bpm = raw_bpm
                else:
                    # Dynamic alpha: adapt smoothly to natural heart rate variability
                    alpha = 0.10 * conf_combined + 0.03
                    if abs(raw_bpm - self.smooth_bpm) < 20.0 or len(self.bpm_history) < 5:
                        self.smooth_bpm = alpha * raw_bpm + (1.0 - alpha) * self.smooth_bpm
                    else:
                        self.smooth_bpm = 0.03 * raw_bpm + 0.97 * self.smooth_bpm
                self.bpm_history.append(raw_bpm)
                self.hold_frames = 90  # Hold for ~3 seconds of transient noise
            else:
                # Confidence dipped: hold the last valid smoothed BPM
                if self.hold_frames > 0:
                    self.hold_frames -= 1
                else:
                    # After 90 frames of low confidence, use historical median
                    if len(self.bpm_history) >= 5:
                        self.smooth_bpm = float(np.median(self.bpm_history))

        return self.smooth_bpm, raw_bpm, self.confidence, filtered_pulse, freqs, self.smooth_power
