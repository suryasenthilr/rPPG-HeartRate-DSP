"""
Real-Time Remote Photoplethysmography (rPPG) System
Digital Signal Processing (DSP) - Semester 5 Project
---------------------------------------------------
Execution entry point for live camera stream, video playback,
or synthetic pulse benchmark.
"""

import argparse
import sys
import time
import cv2
import numpy as np

from dsp_pipeline import RPPGSignalProcessor
from face_tracker import FaceTracker
from visualizer import OscilloscopeVisualizer


class SyntheticPulseGenerator:
    """
    Generates a synthetic facial video feed with an injected microvascular
    pulsatile color variation for automated pipeline testing and benchmarking.
    """

    def __init__(self, target_bpm: float = 72.0, fps: float = 30.0):
        self.target_bpm = target_bpm
        self.fps = fps
        self.frame_idx = 0
        self.pulse_freq = target_bpm / 60.0  # Hz

    def read(self) -> tuple[bool, np.ndarray]:
        t = self.frame_idx / self.fps
        self.frame_idx += 1

        # Base image: 480x640 portrait
        frame = np.full((480, 640, 3), (40, 30, 30), dtype=np.uint8)

        # Draw a synthetic face oval
        center = (320, 240)
        axes = (110, 150)
        cv2.ellipse(frame, center, axes, 0, 0, 360, (140, 160, 200), -1)  # Skin base

        # Microvascular pulse: subtle sinusoidal modulation on green channel (amplitude ~ 1.5%)
        pulse_mod = 1.0 + 0.015 * np.sin(2 * np.pi * self.pulse_freq * t)
        # Add slight respiratory drift and sensor noise
        drift = 0.005 * np.sin(2 * np.pi * 0.25 * t)
        noise = np.random.normal(0, 0.002)

        green_val = np.clip(160.0 * (pulse_mod + drift + noise), 0, 255)
        skin_color = (130, int(green_val), 205)

        cv2.ellipse(frame, center, axes, 0, 0, 360, skin_color, -1)

        # Draw eyes and mouth so Haar cascade can detect a face
        cv2.circle(frame, (280, 210), 10, (40, 40, 40), -1)
        cv2.circle(frame, (360, 210), 10, (40, 40, 40), -1)
        cv2.ellipse(frame, (320, 290), (30, 10), 0, 0, 180, (50, 50, 140), -1)

        cv2.putText(
            frame,
            f"SYNTHETIC TEST (Target: {self.target_bpm:.0f} BPM)",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
        )

        time.sleep(1.0 / self.fps)
        return True, frame

    def release(self):
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Real-Time Remote Photoplethysmography (rPPG) DSP System"
    )
    parser.add_argument(
        "--camera", type=int, default=0, help="Camera index (default: 0)"
    )
    parser.add_argument(
        "--video", type=str, default=None, help="Path to input video file"
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Run synthetic benchmark generator without webcam",
    )
    parser.add_argument(
        "--target-bpm",
        type=float,
        default=72.0,
        help="Target BPM for synthetic mode (default: 72)",
    )
    parser.add_argument(
        "--method",
        type=str,
        default="chrom",
        choices=["green", "chrom"],
        help="rPPG extraction algorithm: 'chrom' (recommended for webcams) or 'green'",
    )
    parser.add_argument(
        "--buffer",
        type=int,
        default=250,
        help="Buffer size in frames (~8-10s at 30fps)",
    )
    args = parser.parse_args()

    print("=" * 65)
    print("  Real-Time Remote Photoplethysmography (rPPG) System")
    print("  Digital Signal Processing - Semester 5")
    print("=" * 65)
    print(f"Algorithm Method   : {args.method.upper()}")
    print(f"Buffer Size Frames : {args.buffer}")

    # Initialize Video Capture Source
    if args.synthetic:
        print(f"Source             : Synthetic Generator ({args.target_bpm} BPM)")
        cap = SyntheticPulseGenerator(target_bpm=args.target_bpm)
    elif args.video:
        print(f"Source             : Video File ({args.video})")
        cap = cv2.VideoCapture(args.video)
        if not cap.isOpened():
            print(f"[ERROR] Could not open video file: {args.video}")
            sys.exit(1)
    else:
        print(f"Source             : Webcam (Device {args.camera})")
        cap = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print(f"[WARNING] DirectShow camera open failed, trying default backend...")
            cap = cv2.VideoCapture(args.camera)
        if not cap.isOpened():
            print(f"[ERROR] Unable to access camera device {args.camera}.")
            print("Tip: Run with --synthetic to test without a physical webcam.")
            sys.exit(1)

    # Initialize Modules
    tracker = FaceTracker()
    processor = RPPGSignalProcessor(buffer_size=args.buffer, method=args.method)
    visualizer = OscilloscopeVisualizer(width=1280, height=720)

    fps = 30.0
    prev_time = time.perf_counter()
    show_rois = True
    paused = False

    print("\nStarting real-time processing loop...")
    print("Press [Q] or [ESC] to quit.")
    print("Press [M] to toggle Green / CHROM algorithm.")
    print("Press [R] to reset signal buffer.")
    print("Press [C] to toggle ROI display.")
    print("Press [S] to save dashboard screenshot.\n")

    try:
        while True:
            if not paused:
                ret, frame = cap.read()
                if not ret:
                    if args.video:
                        print("\nEnd of video file reached. Looping...")
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        print("\n[WARNING] Frame read failed.")
                        break

                current_time = time.perf_counter()
                dt = current_time - prev_time
                prev_time = current_time
                if dt > 0:
                    fps = 0.9 * fps + 0.1 * (1.0 / dt)

                # 1. Face & ROI Detection
                face_bbox = tracker.detect_face(frame)
                if face_bbox is None and args.synthetic:
                    face_bbox = (210, 90, 220, 300)
                    tracker.face_detected = True

                rois = None
                face_detected = face_bbox is not None

                if face_detected:
                    rois = tracker.get_rois(face_bbox, frame.shape)
                    # Extract spatial average RGB
                    mean_r, mean_g, mean_b = tracker.extract_mean_rgb(
                        frame, rois, use_skin_filter=True
                    )
                    processor.add_sample(mean_r, mean_g, mean_b, current_time)

                # 2. Run DSP Pipeline
                bpm, raw_bpm, conf, bvp_pulse, freqs, power = processor.process()

                buffer_fill = len(processor.raw_g) / processor.buffer_size

                # 3. Assemble and render real-time oscilloscope HUD
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
                    fps=fps,
                    buffer_fill=buffer_fill,
                    face_detected=face_detected,
                    show_rois=show_rois,
                )

                cv2.imshow("rPPG Heart Rate Monitoring System [DSP]", dashboard)

            # Handle Key Events
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                print("Exit requested by user.")
                break
            elif key == ord("m"):
                new_method = "chrom" if processor.method == "green" else "green"
                processor.method = new_method
                print(f"[INFO] Switched rPPG algorithm to: {new_method.upper()}")
            elif key == ord("r"):
                processor.reset()
                print("[INFO] Signal buffer reset.")
            elif key == ord("c"):
                show_rois = not show_rois
                print(f"[INFO] ROI visibility set to: {show_rois}")
            elif key == ord("p"):
                paused = not paused
                print(f"[INFO] Playback {'paused' if paused else 'resumed'}.")
            elif key == ord("s"):
                filename = f"rppg_snapshot_{int(time.time())}.png"
                cv2.imwrite(filename, dashboard)
                print(f"[INFO] Dashboard snapshot saved as: {filename}")

    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("System shutdown complete.")


if __name__ == "__main__":
    main()
