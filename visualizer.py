"""
Oscilloscope and Real-Time HUD Dashboard Visualizer
---------------------------------------------------
Renders:
1. Video stream with tracked Facial ROIs and skin mask toggles.
2. Real-time time-domain Blood Volume Pulse (BVP) oscilloscope wave.
3. Frequency-domain Fast Fourier Transform (FFT) power spectrum.
4. Large digital Heart Rate (BPM) readout, SNR (dB), Confidence gauge, and system telemetry.
"""

import cv2
import numpy as np


class OscilloscopeVisualizer:
    """
    High-performance real-time UI dashboard rendered directly in OpenCV.
    """

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height

        # Color palette (BGR)
        self.BG_COLOR = (24, 24, 28)
        self.PANEL_BG = (35, 35, 42)
        self.BORDER_COLOR = (60, 60, 72)
        self.TEXT_COLOR = (230, 230, 235)
        self.ACCENT_CYAN = (230, 200, 30)
        self.ACCENT_GREEN = (80, 220, 100)
        self.ACCENT_RED = (60, 60, 240)
        self.ACCENT_YELLOW = (40, 210, 255)
        self.PULSE_COLOR = (255, 120, 40)  # Bright orange/cyan
        self.GRID_COLOR = (48, 48, 56)

        # Pulse animation state for beating heart icon
        self.beat_phase = 0.0

    def draw_roi_boxes(
        self,
        frame: np.ndarray,
        face_bbox: tuple[int, int, int, int] | None,
        rois: dict[str, tuple[int, int, int, int]] | None,
        show_rois: bool = True,
    ):
        """Draws labeled bounding boxes around face and vascular regions."""
        if not show_rois or face_bbox is None:
            return

        fx, fy, fw, fh = face_bbox
        # Draw face boundary with corner brackets
        cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (160, 160, 160), 1)

        if rois is None:
            return

        # Forehead box
        if "forehead" in rois:
            x, y, w, h = rois["forehead"]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (240, 180, 20), 2)
            cv2.putText(
                frame,
                "Forehead ROI",
                (x, max(15, y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (240, 180, 20),
                1,
                cv2.LINE_AA,
            )

        # Cheek & Central boxes
        for key, name, col in [
            ("left_cheek", "Cheek L", (80, 220, 100)),
            ("right_cheek", "Cheek R", (80, 220, 100)),
            ("central", "Nose/Cheek ROI", (200, 120, 240)),
        ]:
            if key in rois:
                x, y, w, h = rois[key]
                cv2.rectangle(frame, (x, y), (x + w, y + h), col, 2)
                cv2.putText(
                    frame,
                    name,
                    (x, max(15, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.38,
                    col,
                    1,
                    cv2.LINE_AA,
                )

    def draw_waveform(
        self,
        canvas: np.ndarray,
        box: tuple[int, int, int, int],
        signal: np.ndarray | None,
        title: str = "BVP Time-Domain Pulse Wave",
    ):
        """Renders time-domain oscilloscope wave in specified rectangle (x, y, w, h)."""
        x, y, w, h = box

        # Background & border
        cv2.rectangle(canvas, (x, y), (x + w, y + h), self.PANEL_BG, -1)
        cv2.rectangle(canvas, (x, y), (x + w, y + h), self.BORDER_COLOR, 1)

        # Title
        cv2.putText(
            canvas,
            title,
            (x + 12, y + 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            self.TEXT_COLOR,
            1,
            cv2.LINE_AA,
        )

        # Grid lines
        for i in range(1, 4):
            gy = y + int(h * i / 4)
            cv2.line(canvas, (x + 8, gy), (x + w - 8, gy), self.GRID_COLOR, 1)
        for j in range(1, 6):
            gx = x + int(w * j / 6)
            cv2.line(canvas, (gx, y + 28), (gx, y + h - 8), self.GRID_COLOR, 1)

        # Midline (zero level)
        mid_y = y + h // 2
        cv2.line(canvas, (x + 8, mid_y), (x + w - 8, mid_y), (65, 65, 80), 1)

        if signal is None or len(signal) < 2:
            cv2.putText(
                canvas,
                "Buffering signal...",
                (x + w // 2 - 70, y + h // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (120, 120, 130),
                1,
                cv2.LINE_AA,
            )
            return

        # Scale waveform to box height
        # Normalize recent window
        recent_samples = signal[-min(len(signal), 180) :]
        s_min = np.min(recent_samples)
        s_max = np.max(recent_samples)
        amp_range = s_max - s_min
        if amp_range < 1e-4:
            amp_range = 1.0

        n_pts = len(recent_samples)
        plot_w = w - 24
        plot_h = h - 50
        pts = []

        for i, val in enumerate(recent_samples):
            px = int(x + 12 + (i / max(1, n_pts - 1)) * plot_w)
            norm_val = (val - s_min) / amp_range
            # Invert y because canvas (0,0) is top-left
            py = int((y + h - 14) - norm_val * plot_h)
            pts.append((px, py))

        pts_array = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(canvas, [pts_array], False, self.PULSE_COLOR, 2, cv2.LINE_AA)

        # Highlight latest sample
        if pts:
            cv2.circle(canvas, pts[-1], 4, (0, 255, 255), -1)

    def draw_spectrum(
        self,
        canvas: np.ndarray,
        box: tuple[int, int, int, int],
        freqs: np.ndarray | None,
        power: np.ndarray | None,
        min_bpm: float = 45.0,
        max_bpm: float = 180.0,
        peak_bpm: float = 0.0,
    ):
        """Renders FFT power spectrum in specified rectangle (x, y, w, h)."""
        x, y, w, h = box

        # Background & border
        cv2.rectangle(canvas, (x, y), (x + w, y + h), self.PANEL_BG, -1)
        cv2.rectangle(canvas, (x, y), (x + w, y + h), self.BORDER_COLOR, 1)

        # Title
        cv2.putText(
            canvas,
            "FFT Power Spectrum (Cardiac Frequency Band)",
            (x + 12, y + 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            self.TEXT_COLOR,
            1,
            cv2.LINE_AA,
        )

        # Grid lines
        for i in range(1, 4):
            gy = y + int(h * i / 4)
            cv2.line(canvas, (x + 8, gy), (x + w - 8, gy), self.GRID_COLOR, 1)

        f_min_hz = min_bpm / 60.0
        f_max_hz = max_bpm / 60.0
        plot_w = w - 24
        plot_h = h - 50

        # Frequency labels on bottom
        for bpm_mark in [60, 90, 120, 150]:
            f_mark = bpm_mark / 60.0
            if f_min_hz <= f_mark <= f_max_hz:
                frac = (f_mark - f_min_hz) / (f_max_hz - f_min_hz)
                tx = int(x + 12 + frac * plot_w)
                cv2.line(canvas, (tx, y + 30), (tx, y + h - 16), self.GRID_COLOR, 1)
                cv2.putText(
                    canvas,
                    f"{bpm_mark}",
                    (tx - 10, y + h - 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.35,
                    (140, 140, 150),
                    1,
                    cv2.LINE_AA,
                )

        if freqs is None or power is None or len(freqs) == 0:
            cv2.putText(
                canvas,
                "Calculating spectrum...",
                (x + w // 2 - 80, y + h // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (120, 120, 130),
                1,
                cv2.LINE_AA,
            )
            return

        # Extract only physiological band
        mask = (freqs >= f_min_hz) & (freqs <= f_max_hz)
        sub_freqs = freqs[mask]
        sub_power = power[mask]

        if len(sub_freqs) < 2:
            return

        pts = []
        for f, p in zip(sub_freqs, sub_power):
            frac_f = (f - f_min_hz) / (f_max_hz - f_min_hz)
            px = int(x + 12 + frac_f * plot_w)
            norm_p = float(np.clip(p, 0.0, 1.0))
            py = int((y + h - 16) - norm_p * plot_h)
            pts.append((px, py))

        # Draw filled polygon for power spectrum
        poly_pts = [(x + 12, y + h - 16)] + pts + [(pts[-1][0], y + h - 16)]
        poly_array = np.array(poly_pts, dtype=np.int32).reshape((-1, 1, 2))

        # Fill under curve with transparent-like shading
        cv2.fillPoly(canvas, [poly_array], (55, 75, 45))
        # Outline
        cv2.polylines(
            canvas,
            [np.array(pts, dtype=np.int32).reshape((-1, 1, 2))],
            False,
            (90, 240, 120),
            2,
            cv2.LINE_AA,
        )

        # Highlight detected cardiac peak
        if peak_bpm > 0:
            peak_hz = peak_bpm / 60.0
            if f_min_hz <= peak_hz <= f_max_hz:
                frac_peak = (peak_hz - f_min_hz) / (f_max_hz - f_min_hz)
                pk_x = int(x + 12 + frac_peak * plot_w)
                cv2.line(canvas, (pk_x, y + 26), (pk_x, y + h - 16), (40, 210, 255), 2)
                cv2.putText(
                    canvas,
                    f"Peak: {peak_bpm:.1f} BPM ({peak_hz:.2f} Hz)",
                    (max(x + 12, pk_x - 70), y + 42),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (40, 210, 255),
                    1,
                    cv2.LINE_AA,
                )

    def draw_telemetry(
        self,
        canvas: np.ndarray,
        box: tuple[int, int, int, int],
        bpm: float,
        raw_bpm: float,
        confidence: float,
        snr: float,
        method: str,
        fps: float,
        buffer_fill: float,
        face_detected: bool,
    ):
        """Draws Heart Rate digital display and clinical metric gauges."""
        x, y, w, h = box

        # Background & border
        cv2.rectangle(canvas, (x, y), (x + w, y + h), self.PANEL_BG, -1)
        cv2.rectangle(canvas, (x, y), (x + w, y + h), self.BORDER_COLOR, 1)

        # Title
        cv2.putText(
            canvas,
            "HEART RATE & DSP TELEMETRY",
            (x + 12, y + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (180, 180, 190),
            1,
            cv2.LINE_AA,
        )

        # Heart icon / Pulse Indicator
        heart_x = x + 35
        heart_y = y + 70
        heart_color = (
            self.ACCENT_RED
            if face_detected and (bpm > 0 or confidence > 0.2)
            else (100, 100, 110)
        )
        # Pulse indicator circle
        cv2.circle(canvas, (heart_x, heart_y), 16, heart_color, -1)
        cv2.putText(
            canvas,
            "HR",
            (heart_x - 10, heart_y + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )

        # Main BPM Display (maintains stable reading without dropping to zero abruptly)
        bpm_text = f"{int(round(bpm))}" if (bpm > 0 and (confidence > 0.15 or buffer_fill >= 0.35)) else "--"
        cv2.putText(
            canvas,
            bpm_text,
            (x + 65, y + 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.8,
            (255, 255, 255),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            "BPM",
            (x + 180, y + 78),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (160, 160, 175),
            2,
            cv2.LINE_AA,
        )

        # Signal Quality Label & Tiered Display
        conf_y = y + 105
        if not face_detected:
            sq_text = "Signal Quality: NO FACE"
            bar_color = self.ACCENT_RED
            disp_fill = 0.10
        elif buffer_fill < 0.35:
            sq_text = f"Signal Quality: ACQUIRING ({int(buffer_fill * 100)}%)"
            bar_color = self.ACCENT_YELLOW
            disp_fill = buffer_fill * 0.5
        elif confidence >= 0.45 and bpm > 0:
            sq_text = "Signal Quality: OPTIMAL (LOCKED)"
            bar_color = self.ACCENT_GREEN
            disp_fill = 0.85
        elif confidence >= 0.25 and bpm > 0:
            sq_text = "Signal Quality: GOOD (TRACKING)"
            bar_color = self.ACCENT_GREEN
            disp_fill = 0.70
        elif bpm > 0:
            sq_text = "Signal Quality: STABILIZING"
            bar_color = self.ACCENT_YELLOW
            disp_fill = 0.45
        else:
            sq_text = "Signal Quality: WEAK (HOLD STILL)"
            bar_color = self.ACCENT_RED
            disp_fill = 0.20

        cv2.putText(
            canvas,
            sq_text,
            (x + 16, conf_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            self.TEXT_COLOR,
            1,
            cv2.LINE_AA,
        )
        bar_w = w - 32
        bar_h = 10
        bar_x = x + 16
        bar_y = conf_y + 8
        cv2.rectangle(
            canvas,
            (bar_x, bar_y),
            (bar_x + bar_w, bar_y + bar_h),
            (50, 50, 60),
            -1,
        )

        fill_w = int(bar_w * np.clip(disp_fill, 0.0, 1.0))
        if fill_w > 0:
            cv2.rectangle(
                canvas,
                (bar_x, bar_y),
                (bar_x + fill_w, bar_y + bar_h),
                bar_color,
                -1,
            )

        # Additional metrics
        col1_x = x + 16
        col2_x = x + w // 2 + 10
        m_y1 = bar_y + 30
        m_y2 = m_y1 + 22

        cv2.putText(
            canvas,
            f"SNR: {snr:+.1f} dB",
            (col1_x, m_y1),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (190, 190, 200),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            f"Method: {method.upper()}",
            (col2_x, m_y1),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (190, 190, 200),
            1,
            cv2.LINE_AA,
        )

        cv2.putText(
            canvas,
            f"FPS: {fps:.1f}",
            (col1_x, m_y2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (190, 190, 200),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            f"Buffer: {int(buffer_fill * 100)}%",
            (col2_x, m_y2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (190, 190, 200),
            1,
            cv2.LINE_AA,
        )

        # Status text
        status_y = m_y2 + 24
        if not face_detected:
            status_text = "STATUS: NO FACE DETECTED"
            status_color = self.ACCENT_RED
        elif buffer_fill < 0.35:
            status_text = "STATUS: INITIALIZING BUFFER..."
            status_color = self.ACCENT_YELLOW
        elif confidence >= 0.25:
            status_text = "STATUS: PULSE TRACKED (NORMAL)"
            status_color = self.ACCENT_GREEN
        elif bpm > 0:
            status_text = "STATUS: STABILIZING (HOLDING BPM)"
            status_color = (240, 200, 40)
        else:
            status_text = "STATUS: WEAK SIGNAL / HOLD STILL"
            status_color = self.ACCENT_YELLOW

        cv2.putText(
            canvas,
            status_text,
            (x + 16, status_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            status_color,
            1,
            cv2.LINE_AA,
        )

    def render_dashboard(
        self,
        frame: np.ndarray,
        face_bbox: tuple[int, int, int, int] | None,
        rois: dict[str, tuple[int, int, int, int]] | None,
        signal: np.ndarray | None,
        freqs: np.ndarray | None,
        power: np.ndarray | None,
        bpm: float,
        raw_bpm: float,
        confidence: float,
        snr: float,
        method: str,
        fps: float,
        buffer_fill: float,
        face_detected: bool,
        show_rois: bool = True,
    ) -> np.ndarray:
        """
        Assembles complete 1280x720 HUD display.
        Left half: Webcam Feed (640x480).
        Right half: Telemetry + Waveform + FFT Spectrum.
        """
        dashboard = np.full((self.height, self.width, 3), self.BG_COLOR, dtype=np.uint8)

        # 1. Overlay ROI rectangles on input video frame
        annotated_frame = frame.copy()
        self.draw_roi_boxes(annotated_frame, face_bbox, rois, show_rois)

        # Resize video feed to fit left half
        vid_w = 640
        vid_h = 480
        resized_vid = cv2.resize(annotated_frame, (vid_w, vid_h))

        # Position video on dashboard
        dashboard[40 : 40 + vid_h, 24 : 24 + vid_w] = resized_vid
        cv2.rectangle(
            dashboard,
            (24, 40),
            (24 + vid_w, 40 + vid_h),
            self.BORDER_COLOR,
            2,
        )

        # Header Title
        cv2.putText(
            dashboard,
            "REAL-TIME REMOTE PHOTOPLETHYSMOGRAPHY (rPPG) - DSP SEMESTER 5",
            (24, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (240, 240, 250),
            2,
            cv2.LINE_AA,
        )

        # Instructions / Hotkeys bar at bottom left
        instructions = "Controls: [Q] Quit | [M] Toggle Green/CHROM | [R] Reset Buffer | [C] Toggle ROIs"
        cv2.putText(
            dashboard,
            instructions,
            (24, self.height - 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (160, 160, 175),
            1,
            cv2.LINE_AA,
        )

        # Right-side layout coordinates
        panel_x = 24 + vid_w + 24
        panel_w = self.width - panel_x - 24

        # Panel 1: Telemetry & BPM
        telemetry_box = (panel_x, 40, panel_w, 190)
        self.draw_telemetry(
            dashboard,
            telemetry_box,
            bpm,
            raw_bpm,
            confidence,
            snr,
            method,
            fps,
            buffer_fill,
            face_detected,
        )

        # Panel 2: Time-Domain BVP Pulse Wave
        wave_box = (panel_x, 245, panel_w, 205)
        self.draw_waveform(dashboard, wave_box, signal, "BVP Time-Domain Pulse Wave")

        # Panel 3: FFT Frequency Spectrum
        spec_box = (panel_x, 465, panel_w, 230)
        self.draw_spectrum(
            dashboard,
            spec_box,
            freqs,
            power,
            min_bpm=45.0,
            max_bpm=180.0,
            peak_bpm=bpm if confidence > 0.2 else 0.0,
        )

        return dashboard
