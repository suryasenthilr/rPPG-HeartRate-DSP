"""
Generates a high-resolution, professional architectural block diagram image
for the rPPG DSP Signal Processing Pipeline.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches


def create_pipeline_diagram(output_path="pipeline_architecture.png"):
    fig = plt.figure(figsize=(16, 20), dpi=300)
    fig.patch.set_facecolor("#0f1117")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0f1117")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # Title Header
    ax.text(
        50,
        97.5,
        "REAL-TIME rPPG DIGITAL SIGNAL PROCESSING PIPELINE",
        ha="center",
        va="center",
        fontsize=20,
        fontweight="bold",
        color="#f0f6fc",
        family="sans-serif",
    )
    ax.text(
        50,
        95.5,
        "End-to-End System Architecture: Video Acquisition → Computer Vision → DSP Filtering → Spectral Analysis → HUD",
        ha="center",
        va="center",
        fontsize=11,
        color="#8b949e",
        family="sans-serif",
    )

    # Box styles and stages definition
    stages = [
        {
            "y": 86.5,
            "height": 6.0,
            "title": "1. VIDEO ACQUISITION & FRAME CAPTURE",
            "bg": "#161b22",
            "border": "#388bfd",
            "tag_bg": "#1f6feb",
            "tag": "VIDEO INPUT",
            "bullets": [
                "• 30 FPS Standard Webcam / USB Video Stream / Prerecorded File / Synthetic Pulse Generator",
                "• High-resolution timestamping via time.perf_counter() for dynamic frame-rate tracking",
            ],
        },
        {
            "y": 74.0,
            "height": 8.0,
            "title": "2. COMPUTER VISION & MULTI-ROI SPATIAL EXTRACTION",
            "bg": "#161b22",
            "border": "#238636",
            "tag_bg": "#2ea043",
            "tag": "CV TRACKING",
            "bullets": [
                "• OpenCV Frontal Face Detection with 5-Pixel Deadband Lock (eliminates pixel jitter)",
                "• Hairline-Safe Forehead ROI (15% - 32% face height) avoiding bangs and eyebrows",
                "• Bilateral Cheeks (Left & Right ~50% - 68%) + Central Maxillary ROI (Angular Artery)",
                "• Robust Percentile Trimming: Discards top/bottom 10% luminance to reject specular glare & hair",
            ],
        },
        {
            "y": 61.5,
            "height": 7.0,
            "title": "3. SPATIAL CHANNEL EXTRACTION & COLOR CONSTANCY",
            "bg": "#161b22",
            "border": "#a371f7",
            "tag_bg": "#8957e5",
            "tag": "COLOR NORMALIZATION",
            "bullets": [
                "• Spatial Mean Pixel Averaging across valid microvascular dermal tissue: r(t), g(t), b(t)",
                "• Instantaneous Spatial Luminance Normalization: g_norm(t) = G(t) / [(R + G + B) / 3] (neutralizes AEC/AWB)",
                "• Selectable rPPG Algorithm: Classic Green (-g_norm) vs. Enhanced CHROM Subspace Projection",
            ],
        },
        {
            "y": 49.5,
            "height": 7.0,
            "title": "4. TEMPORAL BUFFERING & EMPIRICAL SAMPLING RATE",
            "bg": "#161b22",
            "border": "#f0883e",
            "tag_bg": "#bd561d",
            "tag": "BUFFER MANAGEMENT",
            "bullets": [
                "• 7.5-Second Continuous Sliding Temporal Window (FIFO Deque Pruning)",
                "• Time-based duration bounds prevent low-framerate webcams from trapping old movement",
                "• Robust Window-Wide Fs Estimation: Fs = (N - 1) / (t_last - t_first) (stabilizes FFT bins)",
            ],
        },
        {
            "y": 37.5,
            "height": 7.0,
            "title": "5. DIGITAL DETRENDING & BASELINE DRIFT SUPPRESSION",
            "bg": "#161b22",
            "border": "#d29922",
            "tag_bg": "#9e6a03",
            "tag": "DSP DETRENDING",
            "bullets": [
                "• 1st-Order Polynomial Linear Least-Squares Detrending to eliminate linear posture shifts",
                "• Uniform Moving-Average High-Pass Filter (2.0s window, cutoff ~0.5 Hz)",
                "• Boundary Mode: 'nearest' (eliminates zero-padding edge spikes that cause periodic ringing)",
                "• Zero-Mean Unit-Variance Standardization: x_norm = (x - μ) / σ",
            ],
        },
        {
            "y": 25.5,
            "height": 7.0,
            "title": "6. 4TH-ORDER ZERO-PHASE BUTTERWORTH BANDPASS FILTER",
            "bg": "#161b22",
            "border": "#f85149",
            "tag_bg": "#da3633",
            "tag": "IIR BANDPASS FILTER",
            "bullets": [
                "• Passband: 0.75 Hz to 2.50 Hz (corresponding strictly to 45 – 150 Beats Per Minute)",
                "• Second-Order Sections (SOS) Biquad Cascade to ensure numerical stability",
                "• Zero-Phase Forward-Backward Filtering (sosfiltfilt): 0 ms phase distortion across pulse wave",
                "• Attenuation: > 20 dB suppression of low-frequency breathing drift and 50/60 Hz lighting flicker",
            ],
        },
        {
            "y": 13.5,
            "height": 7.0,
            "title": "7. WINDOWED FFT, SPECTRAL DENSITY & PEAK TRACKING",
            "bg": "#161b22",
            "border": "#39c5cf",
            "tag_bg": "#1b7c83",
            "tag": "SPECTRAL ESTIMATION",
            "bullets": [
                "• Symmetric Hanning Windowing (suppresses spectral leakage side-lobes to -31.5 dB)",
                "• Zero-Padding to N = 2048 Points for sub-BPM frequency bin resolution (Δf = 0.0146 Hz ≈ 0.88 BPM)",
                "• Recursive Temporal Spectral Averaging: P_smooth = 0.85 * P_prev + 0.15 * P_raw (reduces periodogram variance)",
                "• Phase-Locked Peak Tracking with Gaussian Continuity Prior: HR (BPM) = f_peak × 60",
            ],
        },
        {
            "y": 2.0,
            "height": 6.5,
            "title": "8. REAL-TIME OSCILLOSCOPE HUD & CLINICAL TELEMETRY",
            "bg": "#161b22",
            "border": "#56d364",
            "tag_bg": "#238636",
            "tag": "OUTPUT & HUD",
            "bullets": [
                "• Live Video Stream with locked Face & Anatomical Vascular ROIs Overlay",
                "• Scrolling Time-Domain Blood Volume Pulse (BVP) Oscilloscope Waveform",
                "• FFT Power Spectrum with detected dominant cardiac frequency marker",
                "• Large Digital BPM Readout + Multi-Tiered Clinical Signal Quality (OPTIMAL / GOOD / STABILIZING)",
            ],
        },
    ]

    box_w = 84
    box_x = 8

    for i, s in enumerate(stages):
        bx = box_x
        by = s["y"]
        bw = box_w
        bh = s["height"]

        # Card shadow
        shadow = patches.FancyBboxPatch(
            (bx + 0.5, by - 0.4),
            bw,
            bh,
            boxstyle="round,pad=0.8,rounding_size=1.2",
            facecolor="#05070a",
            edgecolor="none",
            alpha=0.6,
            zorder=1,
        )
        ax.add_patch(shadow)

        # Main Card Box
        box = patches.FancyBboxPatch(
            (bx, by),
            bw,
            bh,
            boxstyle="round,pad=0.8,rounding_size=1.2",
            facecolor=s["bg"],
            edgecolor=s["border"],
            linewidth=2.0,
            zorder=2,
        )
        ax.add_patch(box)

        # Tag pill
        tag_w = len(s["tag"]) * 0.95 + 3.0
        tag_box = patches.FancyBboxPatch(
            (bx + 2.0, by + bh - 1.8),
            tag_w,
            1.6,
            boxstyle="round,pad=0.3,rounding_size=0.6",
            facecolor=s["tag_bg"],
            edgecolor="none",
            zorder=3,
        )
        ax.add_patch(tag_box)
        ax.text(
            bx + 2.0 + tag_w / 2.0,
            by + bh - 1.0,
            s["tag"],
            ha="center",
            va="center",
            fontsize=8.5,
            fontweight="bold",
            color="#ffffff",
            zorder=4,
        )

        # Header title
        ax.text(
            bx + 6.0 + tag_w,
            by + bh - 1.0,
            s["title"],
            ha="left",
            va="center",
            fontsize=12,
            fontweight="bold",
            color="#f0f6fc",
            zorder=4,
        )

        # Bullets
        n_bullets = len(s["bullets"])
        bullet_spacing = (bh - 2.8) / max(1, n_bullets)
        for b_idx, bullet in enumerate(s["bullets"]):
            by_pos = (by + bh - 2.8) - b_idx * bullet_spacing
            ax.text(
                bx + 3.0,
                by_pos,
                bullet,
                ha="left",
                va="center",
                fontsize=9.2,
                color="#c9d1d9",
                family="monospace",
                zorder=4,
            )

        # Arrow down to next stage
        if i < len(stages) - 1:
            arrow_start_y = by - 0.5
            next_stage = stages[i + 1]
            arrow_end_y = next_stage["y"] + next_stage["height"] + 0.6
            ax.annotate(
                "",
                xy=(50, arrow_end_y),
                xytext=(50, arrow_start_y),
                arrowprops=dict(
                    arrowstyle="-|>",
                    color="#58a6ff",
                    lw=2.5,
                    mutation_scale=18,
                ),
                zorder=5,
            )

    plt.tight_layout()
    plt.savefig(output_path, facecolor=fig.get_facecolor(), edgecolor="none", dpi=300)
    plt.close()
    print(f"High-resolution pipeline diagram saved to: {output_path}")


if __name__ == "__main__":
    create_pipeline_diagram()
