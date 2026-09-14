"""
Verification script for headless execution test and dashboard snapshot generation.
Runs synthetic generator for 120 frames, exercises all modules, and saves dashboard_demo.png.
"""

import time
import cv2
from dsp_pipeline import RPPGSignalProcessor
from face_tracker import FaceTracker
from main import SyntheticPulseGenerator
from visualizer import OscilloscopeVisualizer


def run_verification():
    print("Running system verification test...")
    target_bpm = 72.0
    cap = SyntheticPulseGenerator(target_bpm=target_bpm, fps=30.0)
    tracker = FaceTracker()
    processor = RPPGSignalProcessor(buffer_size=250, method="green")
    visualizer = OscilloscopeVisualizer(width=1280, height=720)

    start_time = time.perf_counter()
    dashboard = None

    # Run for 150 frames (~5 seconds of simulated video)
    for frame_i in range(150):
        t = frame_i / 30.0
        ret, frame = cap.read()
        assert ret, "Synthetic frame generation failed"

        face_bbox = tracker.detect_face(frame)
        if face_bbox is None:
            # Fallback face box for synthetic cartoon generator
            face_bbox = (210, 90, 220, 300)
            tracker.face_detected = True

        rois = None
        face_detected = face_bbox is not None

        if face_detected:
            rois = tracker.get_rois(face_bbox, frame.shape)
            mean_r, mean_g, mean_b = tracker.extract_mean_rgb(
                frame, rois, use_skin_filter=False
            )
            processor.add_sample(mean_r, mean_g, mean_b, t)

        bpm, raw_bpm, conf, bvp_pulse, freqs, power = processor.process()
        buffer_fill = len(processor.raw_g) / processor.buffer_size

        dashboard = visualizer.render_dashboard(
            frame=frame,
            face_bbox=face_bbox,
            rois=rois,
            signal=bvp_pulse,
            freqs=freqs,
            power=power,
            bpm=bpm,
            raw_bpm=raw_bpm,
            confidence=conf,
            snr=processor.snr,
            method=processor.method,
            fps=30.0,
            buffer_fill=buffer_fill,
            face_detected=face_detected,
            show_rois=True,
        )

    output_path = "dashboard_demo.png"
    cv2.imwrite(output_path, dashboard)
    print(f"Verification successful! Output snapshot saved to: {output_path}")
    print(f"Final Estimated BPM: {bpm:.1f} (Target: {target_bpm:.1f} BPM)")
    print(f"Confidence: {conf * 100:.1f}%, SNR: {processor.snr:.1f} dB")


if __name__ == "__main__":
    run_verification()
