import threading
import time
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np
from ultralytics import YOLO

from cam_controller import PTZController
from models import TrackingMode, ZoomDirection
from rtsp_feed import RTSPFeed


MODEL_PATH = Path(__file__).parent.joinpath("yolo_weights.pt")


class MotionTracker:
    rtsp_feed: RTSPFeed
    cam_control: PTZController
    track_thread_created: bool
    _activate_tracking: threading.Event = threading.Event()
    detector: YOLO
    player_class_id: int

    # Deviation sensitivities - how far to move for a pixel deviation
    pan_sensitivity: float
    tilt_sensitivity: float
    zoom_sensitivity: int

    # Zoom thresholds - If composite bounding box fills x% of frame zoom in/out
    zoom_in_threshold: float
    zoom_out_threshold: float

    # Deadzones - allow for good enough centering
    pan_dead_zone: int
    tilt_dead_zone: int

    def __init__(self, feed: RTSPFeed, cam_controller: PTZController):
        self.rtsp_feed = feed
        self.cam_control = cam_controller
        self.track_thread_created = False

        self.pan_sensitivity = 0.05
        self.tilt_sensitivity = 0.05
        self.zoom_sensitivity = 50
        self.zoom_in_threshold = 0.3
        self.zoom_out_threshold = 0.6
        self.pan_dead_zone = 125
        self.tilt_dead_zone = 125

    def is_tracking(self) -> bool:
        return self._activate_tracking.is_set()

    def _configure_tracking(self):
        self.rtsp_feed.start()
        time.sleep(5)
        ret, frame = self.rtsp_feed.read()
        if not ret:
            print("Failed to read from video source")
            return
        self.frame_h, self.frame_w = frame.shape[:2]
        self.frame_center_x = self.frame_w / 2
        self.frame_center_y = self.frame_h / 2
        self.frame_area = self.frame_w * self.frame_h
        self.detector = YOLO(MODEL_PATH)
        class_names = self.detector.names
        self.player_class_id = [k for k, v in class_names.items() if v == "player"][0]

    def _tracking_loop(self, activate_tracking_event: threading.Event):
        while True:
            activate_tracking_event.wait()
            ret, frame = self.rtsp_feed.read()
            if not ret:
                activate_tracking_event.set()
            detection_results = self.detector(frame, conf=0.8, iou=0.4, verbose=False)

            player_centroids = []
            player_bbox_widths = []
            for r in detection_results:
                boxes = r.boxes.xyxy.cpu().numpy()  # Bounding boxes (x1, y1, x2, y2)
                confs = r.boxes.conf.cpu().numpy()
                class_ids = r.boxes.cls.cpu().numpy()

                for idx, box in enumerate(boxes):
                    conf = confs[idx]
                    class_id = class_ids[idx]

                    if class_id == self.player_class_id:
                        x1, y1, x2, y2 = map(int, box)
                        # Get centroid of the player's bounding box
                        centroid_x = (x1 + x2) / 2
                        centroid_y = (y1 + y2) / 2
                        player_centroids.append((centroid_x, centroid_y))
                        player_bbox_widths.append(x2 - x1)

                if player_centroids:
                    # Calculate the average centroid of all detected players
                    avg_centroid_x = np.mean([c[0] for c in player_centroids])
                    avg_centroid_y = np.mean([c[1] for c in player_centroids])

                    # Calculate combined bounding box area
                    centroid_array = np.array(player_centroids)
                    min_coords = np.min(centroid_array, axis=0)
                    max_coords = np.max(centroid_array, axis=0)
                    total_area = (max_coords[0] - min_coords[0]) * (max_coords[1] - min_coords[1])

                    # Calculate deviation from frame center
                    delta_x = avg_centroid_x - self.frame_center_x
                    delta_y = avg_centroid_y - self.frame_center_y

                    # Move to correct for delta
                    if abs(delta_x) > self.pan_dead_zone and abs(delta_y) > self.tilt_dead_zone:
                        # Needs to be a composite correction
                        self._move_camera(
                            (delta_x*-1*self.pan_sensitivity, delta_y*self.tilt_sensitivity)
                        )
                    elif abs(delta_x) > self.pan_dead_zone:
                        # Need to correct pan only
                        self._move_camera(
                            (delta_x*-1*self.pan_sensitivity,0)
                        )
                    elif abs(delta_y) > self.tilt_dead_zone:
                        # Need to correct tilt only
                        self._move_camera(
                            (0,delta_y*self.tilt_sensitivity)
                        )

                    # Zoom to correct for under or overfill
                    fill_ratio = total_area / self.frame_area
                    if fill_ratio < self.zoom_in_threshold:
                        # Need to zoom in
                        self._zoom_camera(
                            ZoomDirection.IN,
                            max(1, int((fill_ratio - self.zoom_in_threshold) * self.zoom_sensitivity))
                        )
                    elif fill_ratio > self.zoom_out_threshold:
                        # Need to zoom out
                        self._zoom_camera(
                            ZoomDirection.OUT,
                            max(1, int((self.zoom_out_threshold - fill_ratio) * self.zoom_sensitivity))
                        )

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
