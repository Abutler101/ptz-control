import requests

from models import PTZPosition, PresetLocation


class PTZController:
    ip_address: str
    connected: bool
    current_position: PTZPosition

    def __init__(self, ip_address: str):
        self.ip_address = ip_address
        self.connected = False
        self.current_position = PTZPosition()

    def check_connection(self) -> bool:
        response = requests.get(f"http://{self.ip_address}/cgi-bin/getinfo?file=1")
        self.connected = response.status_code == 200
        return self.connected

    def refresh_position(self):
        if not self.connected:
            return
        pt_status_response = requests.get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23APC&res=1")
        if len(pt_status_response.text) != 11:
            print("Failed to retrieve PT positions")
            return
        position_hex_strings = pt_status_response.text.replace("aPC","")
        pan_pos = int(position_hex_strings[0:4], 16)
        tilt_pos = int(position_hex_strings[4:], 16)
        z_status_response = requests.get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23GZ&res=1")
        if len(z_status_response.text) != 5:
            print("Failed to retrieve Zoom Status")
            return
        zoom_hex_string = z_status_response.text.replace("gz", "")
        zoom_pos = int(zoom_hex_string, 16)
        self.current_position.pan = pan_pos
        self.current_position.tilt = tilt_pos
        self.current_position.zoom = zoom_pos

    def move_home(self):
        if not self.connected:
            return
        fast_home_str = "APS800080001D2"
        move_response = requests.get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23{fast_home_str}&res=1")
        if move_response.status_code != 200 or move_response.text.upper() != fast_home_str:
            print("Failed to Return Home")
        self.refresh_position()

    def reset_zoom(self):
        if not self.connected:
            return
        fast_zoom_reset_str = "Z01"
        zoom_response = requests.get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23{fast_zoom_reset_str}&res=1")
        if zoom_response.status_code != 200 or zoom_response.text.upper() != fast_zoom_reset_str:
            print("Failed to Reset Zoom")
        self.refresh_position()

    def move_pan(self, direction: int, speed: float = 1.0):
        """Move pan left (-1) or right (1)"""
        if not self.connected:
            return
        ...

    def move_tilt(self, direction: int, speed: float = 1.0):
        """Move tilt down (-1) or up (1)"""
        if not self.connected:
            return
        ...

    def move_zoom(self, direction: int, speed: float = 1.0):
        """Zoom out (-1) or in (1)"""
        if not self.connected:
            return
        ...

    def goto_preset(self, preset: PresetLocation):
        """Move to preset location"""
        if not self.connected:
            return
        ...
