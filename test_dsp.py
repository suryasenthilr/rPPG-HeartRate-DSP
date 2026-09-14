"""
Unit Tests for Digital Signal Processing (DSP) Pipeline
-------------------------------------------------------
Verifies:
1. Butterworth bandpass filter frequency response & cutoff attenuation.
2. Baseline detrending and standardization.
3. Fast Fourier Transform (FFT) peak detection accuracy across known BPM rates.
4. Signal-to-Noise Ratio (SNR) and confidence metric robustness.
5. CHROM vs Green channel extraction modes.
"""

import numpy as np
import pytest
from dsp_pipeline import RPPGSignalProcessor


def test_detrend_signal():
    processor = RPPGSignalProcessor()
    fs = 30.0
    t = np.linspace(0, 10, int(10 * fs))

    # Signal with linear ramp drift: y = 2*t + sin(2*pi*1.2*t)
    drift = 2.5 * t
    pure_signal = np.sin(2 * np.pi * 1.2 * t)
    raw = drift + pure_signal

    detrended = processor.detrend_signal(raw, fs)

    # Detrended signal must have zero mean and unit variance
    assert np.isclose(np.mean(detrended), 0.0, atol=1e-2)
    assert np.isclose(np.std(detrended), 1.0, atol=1e-2)

    # Correlation between detrended and true pure sinusoidal pulse should be high (> 0.8)
    corr = np.corrcoef(detrended, pure_signal)[0, 1]
    assert corr > 0.85, f"Correlation after detrending was {corr}, expected > 0.85"


def test_butterworth_bandpass_attenuation():
    processor = RPPGSignalProcessor(low_bpm=45.0, high_bpm=150.0)
    fs = 30.0
    t = np.linspace(0, 10, int(10 * fs))

    # Components:
    # 0.2 Hz (12 BPM - sub-cardiac baseline drift) -> Should be attenuated
    # 1.25 Hz (75 BPM - normal cardiac rhythm) -> Should PASS
    # 8.0 Hz (480 BPM - electronic noise / fluorescent flicker) -> Should be attenuated
    f_low = 0.2
    f_pass = 1.25
    f_high = 8.0

    sig_low = np.sin(2 * np.pi * f_low * t)
    sig_pass = np.sin(2 * np.pi * f_pass * t)
    sig_high = np.sin(2 * np.pi * f_high * t)

    composite = sig_low + sig_pass + sig_high
    filtered = processor.butterworth_bandpass_filter(composite, fs)

    # Check power at each frequency before and after
    fft_in = np.abs(np.fft.rfft(composite)) ** 2
    fft_out = np.abs(np.fft.rfft(filtered)) ** 2
    freqs = np.fft.rfftfreq(len(composite), 1.0 / fs)

    idx_pass = np.argmin(np.abs(freqs - f_pass))
    idx_low = np.argmin(np.abs(freqs - f_low))
    idx_high = np.argmin(np.abs(freqs - f_high))

    # Attenuation: out / in
    gain_pass = fft_out[idx_pass] / fft_in[idx_pass]
    gain_low = fft_out[idx_low] / fft_in[idx_low]
    gain_high = fft_out[idx_high] / fft_in[idx_high]

    # Passband component should be preserved (gain near 1.0)
    # Stopband components should be heavily suppressed
    assert gain_pass > 0.5, f"Passband gain too low: {gain_pass}"
    assert gain_low < 0.15, f"Low frequency was not attenuated: {gain_low}"
    assert gain_high < 0.05, f"High frequency was not attenuated: {gain_high}"


@pytest.mark.parametrize("target_bpm", [60.0, 72.0, 85.0, 110.0, 135.0])
def test_fft_heart_rate_estimation_accuracy(target_bpm):
    """
    Tests that the zero-padded windowed FFT pipeline identifies the true cardiac rate
    with an error margin within 1.0 BPM.
    """
    processor = RPPGSignalProcessor(buffer_size=300)
    fs = 30.0
    f_cardiac = target_bpm / 60.0
    n_samples = 250

    t = np.arange(n_samples) / fs
    # Modulated green signal: mean 150 + sinusoidal pulse of amplitude 1.5 + small noise
    noise = np.random.normal(0, 0.05, n_samples)
    g_signal = 150.0 + 1.5 * np.sin(2 * np.pi * f_cardiac * t) + noise
    r_signal = 180.0 + 0.5 * np.sin(2 * np.pi * f_cardiac * t)
    b_signal = 120.0 + 0.2 * np.sin(2 * np.pi * f_cardiac * t)

    for i in range(n_samples):
        processor.add_sample(r_signal[i], g_signal[i], b_signal[i], t[i])

    bpm, raw_bpm, conf, filtered, freqs, power = processor.process()

    error = abs(raw_bpm - target_bpm)
    assert error < 1.0, f"Target {target_bpm} BPM, got {raw_bpm} BPM (error {error:.2f} BPM)"
    assert conf > 0.4, f"Expected high confidence for clean signal, got {conf:.2f}"
    assert processor.snr > 3.0, f"Expected positive SNR dB, got {processor.snr:.2f}"


def test_chrom_algorithm():
    processor = RPPGSignalProcessor(buffer_size=250, method="chrom")
    fs = 30.0
    target_bpm = 80.0
    f_pulse = target_bpm / 60.0
    n_samples = 250
    t = np.arange(n_samples) / fs

    # CHROM exploits differential absorption in G and R channels
    # Oxyhemoglobin pulse is stronger in G and opposite/weaker in R
    r_signal = 170.0 * (1.0 + 0.005 * np.sin(2 * np.pi * f_pulse * t))
    g_signal = 140.0 * (1.0 - 0.015 * np.sin(2 * np.pi * f_pulse * t))
    b_signal = 110.0 * (1.0 + 0.002 * np.sin(2 * np.pi * f_pulse * t))

    for i in range(n_samples):
        processor.add_sample(r_signal[i], g_signal[i], b_signal[i], t[i])

    bpm, raw_bpm, conf, filtered, freqs, power = processor.process()
    error = abs(raw_bpm - target_bpm)
    assert error < 1.5, f"CHROM estimated {raw_bpm} BPM, expected {target_bpm} BPM"


def test_noise_rejection():
    """Pure random Gaussian noise should yield low confidence score."""
    processor = RPPGSignalProcessor(buffer_size=250)
    fs = 30.0
    n_samples = 250
    t = np.arange(n_samples) / fs

    np.random.seed(42)
    # Pure noise with no periodic cardiac oscillation
    noise_r = np.random.normal(150, 10, n_samples)
    noise_g = np.random.normal(150, 10, n_samples)
    noise_b = np.random.normal(150, 10, n_samples)

    for i in range(n_samples):
        processor.add_sample(noise_r[i], noise_g[i], noise_b[i], t[i])

    bpm, raw_bpm, conf, filtered, freqs, power = processor.process()
    # Confidence for noise should remain low (< 0.35)
    assert conf < 0.35, f"Confidence on pure noise was unexpectedly high: {conf}"
