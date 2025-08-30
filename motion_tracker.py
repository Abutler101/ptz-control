import threading
import time
from enum import Enum
from typing import Optional

import cv2
import numpy as np

from cam_controller import PTZController
from rtsp_feed import RTSPFeed


class TrackingMode(str, Enum):
    LARGEST = "LARGEST"
    MULTI = "MULTI"


class Direction(Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UP = "UP"
    DOWN = "DOWN"


class ZoomDirection(Enum):
    IN = "IN"
    OUT = "OUT"


class MotionTracker:
    rtsp_feed: RTSPFeed
    track_mode: TrackingMode
    cam_control: PTZController
    track_thread_created: bool
    move_scale: float
    min_fill: float
    max_fill: float
    back_sub: Optional[cv2.BackgroundSubtractorMOG2]
    _tracking_active: threading.Event = threading.Event()

    def __init__(self, feed: RTSPFeed, mode: TrackingMode, cam_controller: PTZController):
        self.rtsp_feed = feed
        self.track_mode = mode
        self.cam_control = cam_controller
        self.track_thread_created = False
        self.back_sub = None

        self.move_scale = 0.1  # proportional control factor
        self.min_fill = 0.10  # if object(s) < 10% of frame → zoom in
        self.max_fill = 0.40  # if object(s) > 40% of frame → zoom out

    def is_tracking(self) -> bool:
        return self._tracking_active.is_set()

    def _configure_tracking(self):
        self.rtsp_feed.start()
        time.sleep(0.5)
        ret, frame = self.rtsp_feed.read()
        if not ret:
            print("Failed to read from video source")
            return

        self.frame_h, self.frame_w = frame.shape[:2]
        self.center_x, self.center_y = self.frame_w // 2, self.frame_h // 2
        self.frame_area = self.frame_w * self.frame_h

        self.back_sub = cv2.createBackgroundSubtractorMOG2(
            history=80, varThreshold=50, detectShadows=False
        )

    def _tracking_loop(self, tracking_activation_event: threading.Event):
        while True:
            tracking_activation_event.wait()
            ret, frame = self.rtsp_feed.read()
            if not ret:
                break

            # Apply background subtraction
            fg_mask = self.back_sub.apply(frame)
            # Threshold and clean up mask
            _, thresh = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)
            thresh = cv2.medianBlur(thresh, 5)
            # Get contours of moving things
            contours, _ = cv2.findContours(
                thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            tracked_obj_x, tracked_obj_y = None, None
            total_area = 0

            if contours:
                if self.track_mode == TrackingMode.LARGEST:
                    # Pick the largest moving object
                    largest = max(contours, key=cv2.contourArea)
                    if cv2.contourArea(largest) > 500:  # ignore small noise
                        x, y, w, h = cv2.boundingRect(largest)
                        tracked_obj_x, tracked_obj_y = x + w // 2, y + h // 2
                        total_area = w * h

                elif self.track_mode == TrackingMode.MULTI:
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
                        tracked_obj_x = int(np.mean([c[0] for c in centroids]))
                        tracked_obj_y = int(np.mean([c[1] for c in centroids]))
                        # Compute bounding box around all objects
                        min_x = min([b[0] for b in boxes])
                        min_y = min([b[1] for b in boxes])
                        max_x = max([b[0] + b[2] for b in boxes])
                        max_y = max([b[1] + b[3] for b in boxes])
                        total_area = (max_x - min_x) * (max_y - min_y)

            if tracked_obj_x is not None and tracked_obj_y is not None:
                # Compute offset from center
                dx = tracked_obj_x - self.center_x
                dy = tracked_obj_y - self.center_y

                # Normalize offset to percentage of frame size
                offset_x = dx / self.frame_w
                offset_y = dy / self.frame_h

                # Move camera proportionally
                if abs(offset_x) > 0.05:  # deadzone
                    direction = Direction.RIGHT if offset_x > 0 else Direction.LEFT
                    amount = min(100.0, abs(offset_x) * 100 * self.move_scale)
                    self.move_camera(direction, amount)

                if abs(offset_y) > 0.05:
                    direction = Direction.DOWN if offset_y > 0 else Direction.UP
                    amount = min(100.0, abs(offset_y) * 100 * self.move_scale)
                    self.move_camera(direction, amount)

                # Zoom control
                fill_ratio = total_area / self.frame_area
                if fill_ratio < self.min_fill:
                    steps = int(min(100, (self.min_fill - fill_ratio) * 200))
                    if steps > 0:
                        self.zoom_camera(ZoomDirection.IN, steps)
                elif fill_ratio > self.max_fill:
                    steps = int(min(100, (fill_ratio - self.max_fill) * 200))
                    if steps > 0:
                        self.zoom_camera(ZoomDirection.OUT, steps)

    def move_camera(self, direction: Direction, amount: float):
        if direction == Direction.LEFT:
            self.cam_control.move_pan(1, amount)
        elif direction == Direction.RIGHT:
            self.cam_control.move_pan(-1, amount)

        elif direction == Direction.DOWN:
            self.cam_control.move_tilt(1, amount)
        elif direction == Direction.UP:
            self.cam_control.move_tilt(-1, amount)

    def zoom_camera(self, direction: ZoomDirection, amount: int):
        if direction == ZoomDirection.IN:
            self.cam_control.move_zoom(1, amount)
        else:
            self.cam_control.move_zoom(-1, amount)

    def start_tracking(self):

        def _tracking_thread(tracking_activation_event: threading.Event):
            self._configure_tracking()
            self._tracking_loop(tracking_activation_event)

        if not self.track_thread_created:
            self.tracking_thread = threading.Thread(
                target=_tracking_thread, args=(self._tracking_active,), daemon=True
            ).start()
            self.track_thread_created = True
            self._tracking_active.set()
        elif self.track_thread_created and not self._tracking_active.isSet():
            self._tracking_active.set()

    def stop_tracking(self):
        if self._tracking_active.isSet():
            self._tracking_active.clear()
