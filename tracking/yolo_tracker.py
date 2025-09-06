import threading
from typing import Tuple

import cv2
import numpy as np
from ultralytics import YOLO

from cam_controller import PTZController
from models import TrackingMode, ZoomDirection
from rtsp_feed import RTSPFeed


class MotionTracker:
    rtsp_feed: RTSPFeed
    track_mode: TrackingMode
    cam_control: PTZController
    track_thread_created: bool
    _activate_tracking: threading.Event = threading.Event()

    def __init__(self, feed: RTSPFeed, mode: TrackingMode, cam_controller: PTZController):
        ...

    def is_tracking(self) -> bool:
        return self._activate_tracking.is_set()

    def _configure_tracking(self):
        ...

    def _tracking_loop(self, activate_tracking_event: threading.Event):
        while True:
            activate_tracking_event.wait()
            ret, frame = self.rtsp_feed.read()
            if not ret:
                activate_tracking_event.set()
            detection_results = ...

    def _move_camera(self, amounts: Tuple[float, float]):
        """
        amounts[0] - pan direction and step size (negative is move to right by amount)
        amounts[1] - tilt direction and step size (negative is move up by amount)
        """
        ...

    def _zoom_camera(self, direction: ZoomDirection, amount: int):
        ...

    def start_tracking(self):
        def _tracking_thread(tracking_activation_event: threading.Event):
            self._configure_tracking()
            self._tracking_loop(tracking_activation_event)

        if not self.track_thread_created:
            threading.Thread(
                target=_tracking_thread, args=(self._activate_tracking,), daemon=True
            ).start()
            self.track_thread_created = True
            self._activate_tracking.set()

        elif self.track_thread_created and not self._activate_tracking.isSet():
            self._activate_tracking.set()

    def stop_tracking(self):
        if self._activate_tracking.is_set():
            self._activate_tracking.clear()
