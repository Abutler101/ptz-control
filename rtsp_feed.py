import threading
import time
from typing import Optional, Tuple

import cv2


class RTSPFeed:
    url: str
    is_running: bool

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

    def release(self) -> None:
        self.is_running = False
        if self.cap.isOpened():
            self.cap.release()

    def _update_frame(self) -> None:
        max_fps = 20
        target_frame_time = 1/max_fps
        last_frame_at: float = 0.0
        while self.is_running:
            if time.perf_counter() < last_frame_at + target_frame_time:
                time.sleep((last_frame_at + target_frame_time) - time.perf_counter())
            ret, frame = self.cap.read()
            last_frame_at = time.perf_counter()
            with self.lock:
                self.frame = (ret, frame)

    def read(self) -> Tuple[bool, Optional[cv2.Mat]]:
        with self.lock:
            if self.frame is not None:
                return self.frame
            return False, None
