from dataclasses import dataclass


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
