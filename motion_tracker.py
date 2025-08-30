import threading
import time
from enum import Enum
from typing import Optional

import cv2

from cam_controller import PTZController
from rtsp_feed import RTSPFeed


class TrackingMode(str, Enum):
    LARGEST = "LARGEST"
    MULTI = "MULTI"


class MotionTracker:
    rtsp_feed: RTSPFeed
    track_mode: TrackingMode
    cam_control: PTZController
    track_thread_created: bool
    _pause_tracking: threading.Event = threading.Event()

    def __init__(self, feed: RTSPFeed, mode: TrackingMode, cam_controller: PTZController):
        self.rtsp_feed = feed
        self.track_mode = mode
        self.cam_control = cam_controller
        self.track_thread_created = False

    def is_tracking(self) -> bool:
        return not self._pause_tracking.is_set()

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

        self.move_scale = 0.1  # proportional control factor
        self.min_fill = 0.10  # if object(s) < 10% of frame → zoom in
        self.max_fill = 0.40  # if object(s) > 40% of frame → zoom out

    def _tracking_loop(self, pause_event: threading.Event):
        while True:
            pause_event.wait()
            ...

    def start_tracking(self):

        def _tracking_thread(pause_event: threading.Event):
            self._configure_tracking()
            self._tracking_loop(pause_event)

        if not self.track_thread_created:
            self.tracking_thread = threading.Thread(
                target=_tracking_thread, args=(self._pause_tracking,), daemon=True
            ).start()
            self.track_thread_created = True
        elif self.track_thread_created and self._pause_tracking.isSet():
            self._pause_tracking.clear()

    def stop_tracking(self):
        if not self._pause_tracking.isSet():
            self._pause_tracking.set()
