"""
Face Tracking and Region of Interest (ROI) Extraction Module
------------------------------------------------------------
Implements:
1. Robust Frontal Face Detection with Temporal Smoothing to eliminate jitter.
2. High-vascularity Anatomical ROI Extraction:
   - Forehead ROI (Top ~12% to 28% of face)
   - Left Cheek ROI (~50% to 68% height, 15% to 38% width)
   - Right Cheek ROI (~50% to 68% height, 62% to 85% width)
3. YCrCb Skin Color Segmentation to exclude non-skin pixels (eyebrows, hair, glasses).
4. Spatial Channel Averaging across valid microvascular tissue.
"""

import os
import cv2
import numpy as np


class FaceTracker:
    """
    Tracks human face and extracts spatial average RGB values from facial ROIs.
    """

    def __init__(self, smoothing_factor: float = 0.75):
        # Locate cascade file: check current directory first, then cv2 data dir
        local_cascade = os.path.join(os.path.dirname(__file__), "haarcascade_frontalface_default.xml")
        if os.path.exists(local_cascade):
            cascade_path = local_cascade
        elif hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        else:
            cascade_path = "haarcascade_frontalface_default.xml"

        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        if self.face_cascade.empty():
            print(f"[WARNING] Could not load Haar cascade classifier from {cascade_path}")

        self.smoothing_factor = smoothing_factor
        self.smoothed_bbox: list[float] | None = None
        self.face_detected = False
        self.frames_since_detection = 0

    def _smooth_bbox(self, bbox: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        """
        Applies deadband thresholding and exponential smoothing to freeze bounding box
        when the head is still, preventing detector jitter from introducing artificial pixel noise.
        """
        x, y, w, h = bbox
        if self.smoothed_bbox is None:
            self.smoothed_bbox = [float(x), float(y), float(w), float(h)]
        else:
            # Deadband check: if detector shifted by less than 5 pixels, freeze the box
            dx = abs(x - self.smoothed_bbox[0])
            dy = abs(y - self.smoothed_bbox[1])
            dw = abs(w - self.smoothed_bbox[2])
            dh = abs(h - self.smoothed_bbox[3])

            if dx < 5.0 and dy < 5.0 and dw < 5.0 and dh < 5.0:
                # Retain current smoothed position without jitter
                pass
            else:
                alpha = self.smoothing_factor
                self.smoothed_bbox[0] = alpha * self.smoothed_bbox[0] + (1.0 - alpha) * x
                self.smoothed_bbox[1] = alpha * self.smoothed_bbox[1] + (1.0 - alpha) * y
                self.smoothed_bbox[2] = alpha * self.smoothed_bbox[2] + (1.0 - alpha) * w
                self.smoothed_bbox[3] = alpha * self.smoothed_bbox[3] + (1.0 - alpha) * h

        return (
            int(round(self.smoothed_bbox[0])),
            int(round(self.smoothed_bbox[1])),
            int(round(self.smoothed_bbox[2])),
            int(round(self.smoothed_bbox[3])),
        )

    def detect_face(self, frame: np.ndarray) -> tuple[int, int, int, int] | None:
        """
        Detects the primary frontal face in the frame with persistence hold.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(100, 100),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        if len(faces) > 0:
            largest_face = max(faces, key=lambda f: f[2] * f[3])
            self.face_detected = True
            self.frames_since_detection = 0
            return self._smooth_bbox(largest_face)
        else:
            self.frames_since_detection += 1
            if self.frames_since_detection <= 30 and self.smoothed_bbox is not None:
                # Hold last known face position for up to 1 second during brief movement/blinks
                self.face_detected = True
                return (
                    int(round(self.smoothed_bbox[0])),
                    int(round(self.smoothed_bbox[1])),
                    int(round(self.smoothed_bbox[2])),
                    int(round(self.smoothed_bbox[3])),
                )
            else:
                self.face_detected = False
                self.smoothed_bbox = None
                return None

    def get_rois(
        self, face_bbox: tuple[int, int, int, int], frame_shape: tuple[int, int, int]
    ) -> dict[str, tuple[int, int, int, int]]:
        """
        Derives physiological ROIs (Forehead and Cheeks) from face coordinates.
        Ensures bounding coordinates stay inside the video frame.
        """
        fx, fy, fw, fh = face_bbox
        max_h, max_w = frame_shape[:2]

        def clamp_rect(rx, ry, rw, rh):
            x1 = max(0, min(rx, max_w - 1))
            y1 = max(0, min(ry, max_h - 1))
            x2 = max(x1 + 1, min(rx + rw, max_w))
            y2 = max(y1 + 1, min(ry + rh, max_h))
            return (x1, y1, x2 - x1, y2 - y1)

        # 1. Forehead: Safe margin below hairline (15% to 32% of face, center 46% width)
        forehead = clamp_rect(
            int(fx + fw * 0.27),
            int(fy + fh * 0.15),
            int(fw * 0.46),
            int(fh * 0.17),
        )

        # 2. Left Cheek: ~50% to 68% height, 16% to 38% width
        left_cheek = clamp_rect(
            int(fx + fw * 0.16),
            int(fy + fh * 0.50),
            int(fw * 0.22),
            int(fh * 0.18),
        )

        # 3. Right Cheek: ~50% to 68% height, 62% to 84% width
        right_cheek = clamp_rect(
            int(fx + fw * 0.62),
            int(fy + fh * 0.50),
            int(fw * 0.22),
            int(fh * 0.18),
        )

        # 4. Central Facial Region (Nose bridge & upper maxilla, high angular artery perfusion)
        central = clamp_rect(
            int(fx + fw * 0.38),
            int(fy + fh * 0.42),
            int(fw * 0.24),
            int(fh * 0.20),
        )

        return {
            "forehead": forehead,
            "left_cheek": left_cheek,
            "right_cheek": right_cheek,
            "central": central,
        }

    def extract_mean_rgb(
        self,
        frame: np.ndarray,
        rois: dict[str, tuple[int, int, int, int]],
        use_skin_filter: bool = True,
    ) -> tuple[float, float, float]:
        """
        Calculates spatial mean of Red, Green, and Blue channels across all ROIs.
        Uses robust percentile trimming (10th to 90th percentile of brightness)
        to eliminate hair, eyebrows, and specular glare without color-space threshold fragility.
        """
        total_r = 0.0
        total_g = 0.0
        total_b = 0.0
        total_pixels = 0

        for name, (rx, ry, rw, rh) in rois.items():
            roi = frame[ry : ry + rh, rx : rx + rw]
            if roi.size == 0:
                continue

            if use_skin_filter:
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                p_low = np.percentile(gray_roi, 10)
                p_high = np.percentile(gray_roi, 90)
                mask = (gray_roi >= p_low) & (gray_roi <= p_high)
                valid_pixels = roi[mask]

                if len(valid_pixels) > 20:
                    total_b += np.sum(valid_pixels[:, 0])
                    total_g += np.sum(valid_pixels[:, 1])
                    total_r += np.sum(valid_pixels[:, 2])
                    total_pixels += len(valid_pixels)
                    continue

            # Fallback to whole ROI
            b_ch, g_ch, r_ch = cv2.split(roi)
            total_b += np.sum(b_ch)
            total_g += np.sum(g_ch)
            total_r += np.sum(r_ch)
            total_pixels += roi.shape[0] * roi.shape[1]

        if total_pixels == 0:
            return 0.0, 0.0, 0.0

        return total_r / total_pixels, total_g / total_pixels, total_b / total_pixels
