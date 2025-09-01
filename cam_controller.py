"""
For movement:
each axis gets 4 sig fig hex value
first 2 vals full 0-F range - changes to second val are very small steps
For Zoom:
gets 3 sig fig hex value
first 2 vals full 0-F range - changes to second val are very small steps
min zoom: hex 555 = 1365
max zoom: hex FFF = 4095
"""

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

    def move_pan(self, direction: int, speed: float = 5.0):
        """Move pan left (1) or right (-1)"""
        if not self.connected:
            return
        target_pan: str
        # If Direction is 1, Take step Left.
        # If Direction is -1, Take step Right
        target_pos_base_10 = int(self.current_position.pan + ((direction * 256) * speed)) + 2
        target_pos_base_10 = max(min(target_pos_base_10, 65535), 0)
        raw_target_hex = hex(target_pos_base_10).replace("0x", "")
        target_pan = (raw_target_hex[0:2] + "00").upper()
        current_tilt_raw_hex = hex(self.current_position.tilt+1).replace("0x", "")
        current_tilt = current_tilt_raw_hex.upper()

        pan_str = f"APS{target_pan}{current_tilt}1D2"
        move_response = requests.get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23{pan_str}&res=1")
        if move_response.status_code != 200 or move_response.text.upper() != pan_str:
            print(f"Failed to take Pan Step to {target_pan}")
        self.refresh_position()

    def move_tilt(self, direction: int, speed: float = 5.0):
        """Move tilt down (1) or up (-1)"""
        if not self.connected:
            return
        target_tilt: str
        # If Direction is 1, Take step Down.
        # If Direction is -1, Take step Up
        target_pos_base_10 = int(self.current_position.tilt + ((direction * 256) * speed)) + 2
        target_pos_base_10 = max(min(target_pos_base_10, 65535), 0)
        raw_target_hex = hex(target_pos_base_10).replace("0x", "")
        target_tilt = (raw_target_hex[0:2] + "00").upper()
        current_pan_raw_hex = hex(self.current_position.pan+1).replace("0x", "")
        current_pan = current_pan_raw_hex.upper()

        tilt_str = f"APS{current_pan}{target_tilt}1D2"
        move_response = requests.get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23{tilt_str}&res=1")
        if move_response.status_code != 200 or move_response.text.upper() != tilt_str:
            print(f"Failed to take Pan Step to {target_tilt}")
        self.refresh_position()

    def move_zoom(self, direction: int, speed: float = 2.0):
        """Zoom out (-1) or in (1)"""
        if not self.connected:
            return
        target_zoom: str
        target_pos_base_10 = int(self.current_position.zoom + ((direction * 16) * speed)) + 2
        target_pos_base_10 = max(min(target_pos_base_10, 4095), 1376)
        raw_target_hex = hex(target_pos_base_10).replace("0x", "")
        target_zoom = (raw_target_hex[0:2] + "0").upper()

        zoom_str = f"AXZ{target_zoom}"
        zoom_response = requests.get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23{zoom_str}&res=1")
        if zoom_response.status_code != 200 or zoom_response.text.upper() != zoom_str:
            print(f"Failed to take Zoom Step to {target_zoom}")
        self.refresh_position()

    def goto_preset(self, preset: PresetLocation):
        """Move to preset location"""
        if not self.connected:
            return
        target_pan: str
        target_tilt: str
        target_zoom: str
        raw_pan_hex = hex(preset.pan+1).replace("0x","")
        raw_tilt_hex = hex(preset.tilt+1).replace("0x","")
        raw_zoom_hex = hex(preset.zoom+1).replace("0x","")

        target_pan = (raw_pan_hex[0:2] + "00").upper()
        target_tilt = (raw_tilt_hex[0:2] + "00").upper()
        target_zoom = (raw_zoom_hex[0:2] + "5").upper()

        location_str = f"APS{target_pan}{target_tilt}1D2"
        zoom_str = f"AXZ{target_zoom}"
        zoom_response = requests.get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23{zoom_str}&res=1")
        move_response = requests.get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23{location_str}&res=1")
        if (move_response.status_code != 200 or zoom_response.status_code != 200 or
                move_response.text.upper() != location_str or zoom_response.text.upper() != zoom_str):
            print(f"Failed to Move to Preset {preset.name}")
        self.refresh_position()
