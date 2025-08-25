"""
Basic Motion based realtime tracker camera control. Seems to run fast enough?
Not sure how well it'll cope when given actual control of camera
"""
import threading
from typing import Optional, Tuple

import cv2
import numpy as np
from enum import Enum


# Camera movement directions
class Direction(Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UP = "UP"
    DOWN = "DOWN"


# Zoom directions
class ZoomDirection(Enum):
    IN = "IN"
    OUT = "OUT"


# Tracking modes
class TrackingMode(Enum):
    LARGEST = "LARGEST"
    MULTI = "MULTI"


class CameraFeed:
    def __init__(self, ip: str, port: int, stream_path: str):
        self.url = f"rtsp://{ip}:{port}/{stream_path}"
        self.cap = cv2.VideoCapture(self.url)
        self.is_running = False
        self.lock = threading.Lock()
        self.frame: Optional[Tuple[bool, cv2.Mat]] = None

    def start(self) -> None:
        self.is_running = True
        thread = threading.Thread(target=self._update_frame, args=())
        thread.start()

    def stop(self) -> None:
        self.is_running = False
        if self.cap.isOpened():
            self.cap.release()

    def _update_frame(self) -> None:
        while self.is_running:
            ret, frame = self.cap.read()
            with self.lock:
                self.frame = (ret, frame)

    def read(self) -> Tuple[bool, Optional[cv2.Mat]]:
        with self.lock:
            if self.frame is not None:
                return self.frame
            return False, None


# Stub for camera movement API
def move_camera(direction: Direction, amount: float):
    # Replace this with actual API call
    print(f"Moving camera {direction.value} by {amount:.2f}")


# Stub for camera zoom API
def zoom_camera(direction: ZoomDirection, steps: int):
    # Replace this with actual API call
    print(f"Zooming {direction.value} by {steps}")


def main(tracking_mode: TrackingMode = TrackingMode.LARGEST):
    ptz_cam = CameraFeed("192.168.0.10",554, "mediainput/h264/stream_1")
    ptz_cam.start()

    cap = cv2.VideoCapture(0)

    # Background subtractor for motion detection
    back_sub = cv2.createBackgroundSubtractorMOG2(
        history=100, varThreshold=50, detectShadows=False
    )

    # Frame dimensions (grab one frame to get size)
    ret, frame = cap.read()
    if not ret:
        print("Failed to read from video source")
        return

    frame_h, frame_w = frame.shape[:2]
    center_x, center_y = frame_w // 2, frame_h // 2
    frame_area = frame_w * frame_h

    # Control sensitivity
    move_scale = 0.1  # proportional control factor

    # Zoom thresholds (percentage of frame area)
    min_fill = 0.10  # if object(s) < 10% of frame → zoom in
    max_fill = 0.40  # if object(s) > 40% of frame → zoom out

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Apply background subtraction
        fg_mask = back_sub.apply(frame)

        # Threshold and clean up mask
        _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
        thresh = cv2.medianBlur(thresh, 5)

        # Find contours of moving objects
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        obj_x, obj_y = None, None
        total_area = 0

        if contours:
            if tracking_mode == TrackingMode.LARGEST:
                # Pick the largest moving object
                largest = max(contours, key=cv2.contourArea)
                if cv2.contourArea(largest) > 500:  # ignore small noise
                    x, y, w, h = cv2.boundingRect(largest)
                    obj_x, obj_y = x + w // 2, y + h // 2
                    total_area = w * h

            elif tracking_mode == TrackingMode.MULTI:
                # Track all significant moving objects
                centroids = []
                boxes = []
                for c in contours:
                    if cv2.contourArea(c) > 500:
                        x, y, w, h = cv2.boundingRect(c)
                        centroids.append((x + w // 2, y + h // 2))
                        boxes.append((x, y, w, h))

                if centroids:
                    # Average centroid
                    obj_x = int(np.mean([c[0] for c in centroids]))
                    obj_y = int(np.mean([c[1] for c in centroids]))

                    # Compute bounding box around all objects
                    min_x = min([b[0] for b in boxes])
                    min_y = min([b[1] for b in boxes])
                    max_x = max([b[0] + b[2] for b in boxes])
                    max_y = max([b[1] + b[3] for b in boxes])
                    total_area = (max_x - min_x) * (max_y - min_y)

        if obj_x is not None and obj_y is not None:
            # Compute offset from center
            dx = obj_x - center_x
            dy = obj_y - center_y

            # Normalize offset to percentage of frame size
            offset_x = dx / frame_w
            offset_y = dy / frame_h

            # Move camera proportionally
            if abs(offset_x) > 0.05:  # deadzone
                direction = Direction.RIGHT if offset_x > 0 else Direction.LEFT
                amount = min(100, abs(offset_x) * 100 * move_scale)
                move_camera(direction, amount)

            if abs(offset_y) > 0.05:
                direction = Direction.DOWN if offset_y > 0 else Direction.UP
                amount = min(100, abs(offset_y) * 100 * move_scale)
                move_camera(direction, amount)

            # Zoom control
            fill_ratio = total_area / frame_area
            if fill_ratio < min_fill:
                steps = int(min(100, (min_fill - fill_ratio) * 200))
                if steps > 0:
                    zoom_camera(ZoomDirection.IN, steps)
            elif fill_ratio > max_fill:
                steps = int(min(100, (fill_ratio - max_fill) * 200))
                if steps > 0:
                    zoom_camera(ZoomDirection.OUT, steps)

        # Optional: show debug view
        # cv2.imshow("Frame", frame)
        # cv2.imshow("Mask", thresh)

        # Exit on 'q'
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    # Change mode here: TrackingMode.LARGEST or TrackingMode.MULTI
    main(tracking_mode=TrackingMode.MULTI)
