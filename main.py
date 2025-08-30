"""
TODO: Jog Hotkeys
TODO: Preset Hotkeys
TODO: Movement based Tracking
"""
import functools
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
from typing import Dict, Optional
import json
import os

from cam_controller import PTZController
from holdable_button import HoldableButton
from models import PresetLocation
from motion_tracker import TrackingMode, MotionTracker
from rtsp_feed import RTSPFeed


class PTZControlApp:
    root: tk.Tk
    ptz_controller: Optional[PTZController]
    presets: Dict[str, PresetLocation]
    hotkeys: Dict[str, str]
    running: bool
    tracking_enabled: bool
    motion_tracker: Optional[MotionTracker]
    status_thread: threading.Thread
    connection_thread: Optional[threading.Thread]

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PTZ Camera Controller")
        self.root.geometry("610x600")

        self.ptz_controller = None
        self.motion_tracker = None
        self.presets = {}
        self.hotkeys = {}

        self.load_presets()
        self.setup_ui()
        self.setup_global_hotkeys()

        self.running = True
        self.tracking_enabled = False
        self.status_thread = threading.Thread(
            target=self.update_status_loop, daemon=True
        )
        self.status_thread.start()

        self.connection_thread = None

    def setup_ui(self):
        # Connection frame
        conn_frame = ttk.LabelFrame(self.root, text="Connection", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(conn_frame, text="Device IP:").grid(row=0, column=0, sticky="w")
        self.ip_entry = ttk.Entry(conn_frame, width=20)
        self.ip_entry.grid(row=0, column=1, padx=5)
        self.ip_entry.insert(0, "192.168.0.10")  # Default IP

        self.connect_btn = ttk.Button(
            conn_frame, text="Connect", command=self.connect_camera
        )
        self.connect_btn.grid(row=0, column=2, padx=5)

        self.status_label = ttk.Label(conn_frame, text="Disconnected", foreground="red")
        self.status_label.grid(row=0, column=3, padx=10)

        # Control frame
        control_frame = ttk.LabelFrame(self.root, text="PTZ Controls", padding=10)
        control_frame.pack(fill="both", expand=True, padx=10, pady=5)

        jog_frame = ttk.LabelFrame(control_frame, text="Jog Controls", padding=20)
        jog_frame.pack(side="left", fill="both", expand=True, padx=5)

        HoldableButton(
            jog_frame, text="▲", width=4, command=lambda: self.jog_tilt(-1), timeout=100
        ).grid(row=0, column=1, padx=5, pady=5)

        HoldableButton(
            jog_frame, text="◀", width=4, command=lambda: self.jog_pan(1), timeout=100
        ).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(jog_frame, text="𝐇", width=4, command=lambda: self.go_home()).grid(
            row=1, column=1, padx=5, pady=5
        )
        HoldableButton(
            jog_frame, text="▶", width=4, command=lambda: self.jog_pan(-1), timeout=100
        ).grid(row=1, column=2, padx=5, pady=5)

        HoldableButton(
            jog_frame, text="▼", width=4, command=lambda: self.jog_tilt(1), timeout=100
        ).grid(row=2, column=1, padx=5, pady=5)

        zoom_frame = ttk.Frame(jog_frame)
        zoom_frame.grid(row=3, column=0, columnspan=3, pady=(15, 0))

        ttk.Label(zoom_frame, text="Zoom").pack()
        zoom_buttons_frame = ttk.Frame(zoom_frame)
        zoom_buttons_frame.pack(pady=5)

        HoldableButton(
            zoom_buttons_frame,
            text="Z-",
            width=4,
            command=lambda: self.jog_zoom(-1),
            timeout=100,
        ).pack(side="left", padx=5)
        ttk.Button(
            zoom_buttons_frame, text="Zx1", width=4, command=lambda: self.reset_zoom()
        ).pack(side="left", padx=5)
        HoldableButton(
            zoom_buttons_frame,
            text="Z+",
            width=4,
            command=lambda: self.jog_zoom(1),
            timeout=100,
        ).pack(side="left", padx=5)

        tracking_frame = ttk.Frame(zoom_frame)
        tracking_frame.pack(pady=(10, 0))
        self.tracking_btn = ttk.Button(
            tracking_frame,
            text="AUTO TRACKING IS OFF",
            width=25,
            command=self.toggle_tracking,
        )
        self.tracking_btn.pack()
        self.track_mode_select = ttk.Combobox(tracking_frame, values=list(TrackingMode), state="readonly")
        self.track_mode_select.current(1)
        self.track_mode_select.bind("<<ComboboxSelected>>", self.update_track_mode)
        self.track_mode_select.pack()

        jog_frame.columnconfigure(0, weight=1)
        jog_frame.columnconfigure(1, weight=1)
        jog_frame.columnconfigure(2, weight=1)

        preset_frame = ttk.LabelFrame(control_frame, text="Presets", padding=10)
        preset_frame.pack(side="right", fill="both", expand=True, padx=5)

        self.preset_buttons_frame = ttk.Frame(preset_frame)
        self.preset_buttons_frame.pack(fill="both", expand=True)

        preset_mgmt_frame = ttk.Frame(preset_frame)
        preset_mgmt_frame.pack(fill="x", pady=(10, 0))

        ttk.Button(
            preset_mgmt_frame, text="Create Preset", command=self.create_preset
        ).pack(side="left", padx=2)
        ttk.Button(
            preset_mgmt_frame, text="Delete Preset", command=self.delete_preset
        ).pack(side="left", padx=2)
        ttk.Button(preset_mgmt_frame, text="Set Hotkey", command=self.set_hotkey).pack(
            side="left", padx=2
        )

        pos_frame = ttk.LabelFrame(self.root, text="Current Position", padding=10)
        pos_frame.pack(fill="x", padx=10, pady=5)

        self.pos_label = ttk.Label(
            pos_frame, text="Pan: 0.0° | Tilt: 0.0° | Zoom: 1.0x"
        )
        self.pos_label.pack()

        self.update_preset_buttons()

    def connect_camera(self):
        """Connect to the PTZ camera"""
        ip = self.ip_entry.get().strip()
        if not ip:
            messagebox.showerror("Error", "Enter a valid IP address")
            return

        def connect_thread():
            while self.running:
                try:
                    self.ptz_controller = PTZController(ip)
                    if self.ptz_controller.check_connection():
                        self.root.after(
                            0,
                            lambda: self.status_label.config(
                                text="Connected", foreground="green"
                            ),
                        )
                        self.root.after(
                            0, lambda: self.connect_btn.config(text="Disconnect")
                        )
                    else:
                        self.root.after(
                            0,
                            lambda: messagebox.showerror(
                                "Error", "Failed to connect to camera"
                            ),
                        )
                except Exception as e:
                    self.root.after(
                        0,
                        lambda: messagebox.showerror(
                            "Error", f"Connection failed: {str(e)}"
                        ),
                    )
                time.sleep(20)

        if self.ptz_controller and self.ptz_controller.connected:
            self.status_label.config(text="Disconnected", foreground="red")
            self.connect_btn.config(text="Connect")
        else:
            self.connection_thread = threading.Thread(
                target=connect_thread, daemon=True
            ).start()

        time.sleep(0.5)
        if self.ptz_controller and self.ptz_controller.connected:
            try:
                self.motion_tracker = MotionTracker(
                    feed=RTSPFeed(ip,554, "mediainput/h264/stream_1"),
                    mode=TrackingMode(self.track_mode_select.get().split(".")[1]),
                    cam_controller=self.ptz_controller
                )
            except Exception as e:
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "Error", f"Connection failed: {str(e)}"
                    ),
                )

    def manual_tracking_override(func):
        """
        Enables and disables tracking either side of a manual jog command
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            was_tracking: bool = False
            if args[0].tracking_enabled:
                was_tracking = True
                args[0].toggle_tracking()

            result = func(*args, **kwargs)

            if was_tracking:
                args[0].toggle_tracking()
            return result
        return wrapper

    def toggle_tracking(self):
        """Toggle auto-tracking on/off"""
        if self.motion_tracker is None:
            return

        if self.tracking_enabled:
            # Disable auto-tracking
            self.motion_tracker.stop_tracking()
            if not self.motion_tracker.is_tracking():
                self.tracking_enabled = False
                self.tracking_btn.configure(text="AUTO TRACKING IS OFF")
        else:
            # Enable auto-tracking
            self.motion_tracker.start_tracking()
            if self.motion_tracker.is_tracking():
                self.tracking_enabled = True
                self.tracking_btn.config(text="AUTO TRACKING IS ON")

    def update_track_mode(self, _: tk.Event):
        new_track_mode = TrackingMode(self.track_mode_select.get().split(".")[1])
        self.motion_tracker.track_mode = new_track_mode

    @manual_tracking_override
    def jog_pan(self, direction: int):
        # left=1, right=-1
        if self.ptz_controller:
            self.ptz_controller.move_pan(direction)

    @manual_tracking_override
    def go_home(self):
        if self.ptz_controller:
            self.ptz_controller.move_home()

    @manual_tracking_override
    def reset_zoom(self):
        if self.ptz_controller:
            self.ptz_controller.reset_zoom()

    @manual_tracking_override
    def jog_tilt(self, direction: int):
        # down=-1, up=1
        if self.ptz_controller:
            self.ptz_controller.move_tilt(direction)

    @manual_tracking_override
    def jog_zoom(self, direction: int):
        # Zoom Out=-1, Zoom In=1
        if self.ptz_controller:
            self.ptz_controller.move_zoom(direction)

    def create_preset(self):
        """Create a new preset location"""
        if not self.ptz_controller or not self.ptz_controller.connected:
            messagebox.showerror("Error", "Camera not connected")
            return

        name = simpledialog.askstring("Create Preset", "Enter preset name:")
        if not name:
            return

        if name in self.presets:
            if not messagebox.askyesno(
                "Overwrite", f"Preset '{name}' exists. Overwrite?"
            ):
                return

        current_pos = self.ptz_controller.current_position
        self.presets[name] = PresetLocation(
            name=name, pan=current_pos.pan, tilt=current_pos.tilt, zoom=current_pos.zoom
        )

        self.save_presets()
        self.update_preset_buttons()
        messagebox.showinfo("Success", f"Preset '{name}' created")

    def delete_preset(self):
        """Delete a preset location"""
        if not self.presets:
            messagebox.showinfo("Info", "No presets to delete")
            return

        preset_names = list(self.presets.keys())
        name = simpledialog.askstring(
            "Delete Preset", f"Enter preset name to delete:\n{', '.join(preset_names)}"
        )

        if name and name in self.presets:
            del self.presets[name]
            self.hotkeys = {
                k: v for k, v in self.hotkeys.items() if v != f"preset_{name}"
            }
            self.save_presets()
            self.update_preset_buttons()
            messagebox.showinfo("Success", f"Preset '{name}' deleted")
        elif name:
            messagebox.showerror("Error", f"Preset '{name}' not found")

    @manual_tracking_override
    def goto_preset(self, preset_name: str):
        """Go to a preset location"""
        if not self.ptz_controller or not self.ptz_controller.connected:
            messagebox.showerror("Error", "Camera not connected")
            return

        if preset_name in self.presets:
            self.ptz_controller.goto_preset(self.presets[preset_name])

    def set_hotkey(self):
        """Set a hotkey for a preset or jog function"""
        # Simplified hotkey setting - in a real app, use a proper key capture dialog
        messagebox.showinfo(
            "Hotkey Setup", "This is a placeholder for the hotkey setup dialog."
        )

    def setup_global_hotkeys(self):
        """Setup global hotkeys (placeholder)"""
        # This would require libraries like 'keyboard' or 'pynput'
        # Example hotkeys:
        # keyboard.add_hotkey('ctrl+shift+up', lambda: self.jog_tilt(1))
        # keyboard.add_hotkey('ctrl+shift+down', lambda: self.jog_tilt(-1))
        # keyboard.add_hotkey('ctrl+shift+left', lambda: self.jog_pan(-1))
        # keyboard.add_hotkey('ctrl+shift+right', lambda: self.jog_pan(1))
        # etc.
        pass

    def update_preset_buttons(self):
        """Update the preset buttons display"""
        # Clear existing buttons
        for widget in self.preset_buttons_frame.winfo_children():
            widget.destroy()

        # Create buttons for each preset
        row = 0
        col = 0
        for preset_name in self.presets:
            btn = ttk.Button(
                self.preset_buttons_frame,
                text=preset_name,
                command=lambda name=preset_name: self.goto_preset(name),
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="ew")

            col += 1
            if col > 2:  # 3 columns max
                col = 0
                row += 1

        # Configure column weights for even distribution
        for i in range(3):
            self.preset_buttons_frame.columnconfigure(i, weight=1)

    def update_status_loop(self):
        """Update status information in a separate thread"""
        while self.running:
            if self.ptz_controller and self.ptz_controller.connected:
                self.ptz_controller.refresh_position()
                pos = self.ptz_controller.current_position

                pos_text = (
                    f"Pan: {pos.pan:.1f} | Tilt: {pos.tilt:.1f} | Zoom: {pos.zoom:.1f}"
                )
                self.root.after(0, lambda: self.pos_label.config(text=pos_text))

            time.sleep(0.1)  # Update 10 times per second

    def load_presets(self):
        """Load presets from file"""
        try:
            if os.path.exists("ptz_presets.json"):
                with open("ptz_presets.json", "r") as f:
                    data = json.load(f)
                    self.presets = {
                        name: PresetLocation(**preset_data)
                        for name, preset_data in data.get("presets", {}).items()
                    }
                    self.hotkeys = data.get("hotkeys", {})
        except Exception as e:
            print(f"Error loading presets: {e}")

    def save_presets(self):
        """Save presets to file"""
        try:
            data = {
                "presets": {
                    name: {
                        "name": preset.name,
                        "pan": preset.pan,
                        "tilt": preset.tilt,
                        "zoom": preset.zoom,
                    }
                    for name, preset in self.presets.items()
                },
                "hotkeys": self.hotkeys,
            }
            with open("ptz_presets.json", "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving presets: {e}")

    def run(self):
        """Start the application"""
        try:
            self.root.mainloop()
        finally:
            self.running = False


if __name__ == "__main__":
    app = PTZControlApp()
    app.run()
