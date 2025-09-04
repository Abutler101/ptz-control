"""
TODO: Need to fine-tune detector for hockey players
"""

from enum import Enum
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

# MODEL_PATH = Path(__file__).parent.joinpath("yolo11n.pt")
MODEL_PATH = Path(__file__).parent.joinpath("fine-tuned-70-epoch-850-images.pt")
TEST_VIDEO_PATH = Path(__file__).parent.joinpath("test.mp4")

PAN_SENSITIVITY = 0.05  # How much camera moves per pixel deviation
TILT_SENSITIVITY = 0.05
ZOOM_SENSITIVITY = 100  # Pixels deviation for one zoom step
PAN_DEAD_ZONE = 250      # Pixels around center where camera doesn't move horizontally
TILT_DEAD_ZONE = 250     # Pixels around center where camera doesn't move vertically
ZOOM_IN_THRESHOLD = 0.6  # If average player bounding box fills this % of frame width, zoom out
ZOOM_OUT_THRESHOLD = 0.2 # If average player bounding box fills this % of frame width, zoom in


class Direction(Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UP = "UP"
    DOWN = "DOWN"


class ZoomDirection(Enum):
    IN = "IN"
    OUT = "OUT"


def move_camera(direction: Direction, amount: float):
    # Replace this with actual API call
    print(f"Moving camera {direction.value} by {amount:.2f}")


def zoom_camera(direction: ZoomDirection, steps: int):
    # Replace this with actual API call
    print(f"Zooming {direction.value} by {steps}")


def main():
    detector = YOLO(MODEL_PATH)
    class_names = detector.names
    target_class_id = [k for k, v in class_names.items() if v == "player"][0]

    cap = cv2.VideoCapture(str(TEST_VIDEO_PATH))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_center_x = frame_width / 2
    frame_center_y = frame_height / 2
    fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"Processing video: ({frame_width}x{frame_height} @ {fps:.2f} FPS)")

    frame_count = 0


    while True:
        start_time = time.perf_counter()
        ret, frame = cap.read()
        if not ret:
            print("End of video stream or error reading frame.")
            break
        frame_count += 1

        results = detector(frame, conf=0.8, iou=0.4, verbose=False)

        player_centroids = []
        player_bbox_widths = []

        for r in results:
            boxes = r.boxes.xyxy.cpu().numpy()  # Bounding boxes (x1, y1, x2, y2)
            confs = r.boxes.conf.cpu().numpy()  # Confidence scores
            class_ids = r.boxes.cls.cpu().numpy()  # Class IDs

            for i in range(len(boxes)):
                box = boxes[i]
                conf = confs[i]
                cls_id = int(class_ids[i])

                if cls_id == target_class_id:
                    x1, y1, x2, y2 = map(int, box)

                    # Calculate centroid of the player's bounding box
                    centroid_x = (x1 + x2) / 2
                    centroid_y = (y1 + y2) / 2
                    player_centroids.append((centroid_x, centroid_y))
                    player_bbox_widths.append(x2 - x1)

                    # Draw bounding box and label
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.circle(frame, (int(centroid_x), int(centroid_y)), 5, (0, 0, 255), -1)
                    label = f"Player: {conf:.2f}"
                    cv2.putText(frame, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        if player_centroids:
            # Calculate the average centroid of all detected players
            avg_centroid_x = np.mean([c[0] for c in player_centroids])
            avg_centroid_y = np.mean([c[1] for c in player_centroids])

            # Calculate average bounding box width
            avg_bbox_width = np.mean(player_bbox_widths) if player_bbox_widths else 0

            # Draw average centroid
            cv2.circle(frame, (int(avg_centroid_x), int(avg_centroid_y)),
                       10, (255, 0, 0), -1)
            cv2.putText(frame, "Avg Player Center",
                        (int(avg_centroid_x) + 15, int(avg_centroid_y) - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

            # Calculate deviation from frame center
            delta_x = avg_centroid_x - frame_center_x
            delta_y = avg_centroid_y - frame_center_y

            # Pan Control
            if abs(delta_x) > PAN_DEAD_ZONE:
                if delta_x < 0:
                    move_camera(Direction.LEFT, abs(delta_x) * PAN_SENSITIVITY)
                else:
                    move_camera(Direction.RIGHT, abs(delta_x) * PAN_SENSITIVITY)

            # Tilt Control
            if abs(delta_y) > TILT_DEAD_ZONE:
                if delta_y < 0:
                    move_camera(Direction.UP, abs(delta_y) * TILT_SENSITIVITY)
                else:
                    move_camera(Direction.DOWN, abs(delta_y) * TILT_SENSITIVITY)

            # Zoom Control
            if avg_bbox_width > 0:
                # Percentage of frame width the average bbox occupies
                bbox_width_ratio = avg_bbox_width / frame_width

                if bbox_width_ratio > ZOOM_IN_THRESHOLD:
                    # Players are too big/close, zoom out
                    zoom_camera(ZoomDirection.OUT, max(1, int((bbox_width_ratio - ZOOM_IN_THRESHOLD) * ZOOM_SENSITIVITY)))
                elif bbox_width_ratio < ZOOM_OUT_THRESHOLD:
                    # Players are too small/far, zoom in
                    zoom_camera(ZoomDirection.IN, max(1, int((ZOOM_OUT_THRESHOLD - bbox_width_ratio) * ZOOM_SENSITIVITY)))

        # Draw center lines for reference
        cv2.line(frame, (int(frame_center_x), 0), (int(frame_center_x), frame_height), (255, 255, 255), 1)
        cv2.line(frame, (0, int(frame_center_y)), (frame_width, int(frame_center_y)), (255, 255, 255), 1)

        # Draw dead zones
        cv2.rectangle(
            frame,
            (int(frame_center_x - PAN_DEAD_ZONE), int(frame_center_y - TILT_DEAD_ZONE)),
            (int(frame_center_x + PAN_DEAD_ZONE), int(frame_center_y + TILT_DEAD_ZONE)),
            (0, 255, 255),
            1
        )
        fps = 1 / (time.perf_counter() - start_time)
        cv2.putText(frame, "{:.2f}".format(fps),
                    (40,40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 3)
        cv2.imshow("Tracking", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break


if __name__ == '__main__':
    main()
