from dataclasses import dataclass
from enum import Enum


@dataclass
class PresetLocation:
    name: str
    pan: int
    tilt: int
    zoom: int


@dataclass
class PTZPosition:
    pan: int = 0
    tilt: int = 0
    zoom: int = 1


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
