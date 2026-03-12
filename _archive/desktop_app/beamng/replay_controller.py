"""
desktop_app/beamng/replay_controller.py — Steering replay recorder and player.
Records live steering to a CSV file and plays back recorded sessions.
"""
import csv
import os
import time
import threading
from typing import Optional, List
from PySide6.QtCore import QObject, Signal


class ReplayController(QObject):
    """
    Records/plays back steering angle sequences.
    File format: CSV with columns: timestamp_s, angle_deg
    """
    recording_started = Signal()
    recording_stopped = Signal(str)   # filepath
    playback_started  = Signal()
    playback_stopped  = Signal()
    playback_progress = Signal(int, int)  # current_frame, total_frames

    def __init__(self, serial_manager, logger, output_dir: str = "output/logs"):
        super().__init__()
        self._serial = serial_manager
        self._log = logger
        self._output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        self._recording: bool = False
        self._recording_data: List[tuple] = []
        self._recording_start: float = 0.0

        self._playback_active: bool = False
        self._playback_thread: Optional[threading.Thread] = None
        self._playback_data: List[tuple] = []

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def start_recording(self):
        self._recording_data = []
        self._recording_start = time.time()
        self._recording = True
        self._log.info("Replay recording started")
        self.recording_started.emit()

    def record_frame(self, angle: float):
        """Call with current wheel angle each control cycle."""
        if not self._recording:
            return
        ts = time.time() - self._recording_start
        self._recording_data.append((ts, angle))

    def stop_recording(self) -> str:
        """Stop recording and save to CSV. Returns filepath."""
        self._recording = False
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(self._output_dir, f"replay_{timestamp}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp_s", "angle_deg"])
            writer.writerows(self._recording_data)
        self._log.info(f"Replay saved: {filepath} ({len(self._recording_data)} frames)")
        self.recording_stopped.emit(filepath)
        return filepath

    @property
    def is_recording(self) -> bool:
        return self._recording

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def load(self, filepath: str) -> bool:
        """Load a replay CSV file."""
        try:
            data = []
            with open(filepath, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append((float(row["timestamp_s"]), float(row["angle_deg"])))
            self._playback_data = data
            self._log.info(f"Replay loaded: {filepath} ({len(data)} frames)")
            return True
        except Exception as e:
            self._log.error(f"Replay load error: {e}")
            return False

    def start_playback(self, loop: bool = False):
        if self._playback_active:
            return
        self._playback_active = True
        self._playback_thread = threading.Thread(
            target=self._playback_loop,
            args=(loop,),
            daemon=True
        )
        self._playback_thread.start()
        self._log.info("Replay playback started")
        self.playback_started.emit()

    def stop_playback(self):
        self._playback_active = False
        if self._serial.is_connected:
            self._serial.set_target(0.0)
        self._log.info("Replay playback stopped")
        self.playback_stopped.emit()

    @property
    def is_playing(self) -> bool:
        return self._playback_active

    def _playback_loop(self, loop: bool):
        data = self._playback_data
        if not data:
            self._playback_active = False
            self.playback_stopped.emit()
            return

        start_time = time.time()
        total = len(data)
        i = 0
        t_offset = 0.0

        while self._playback_active:
            target_ts, angle = data[i]
            elapsed = (time.time() - start_time) + t_offset

            wait = target_ts - elapsed
            if wait > 0.001:
                time.sleep(min(wait, 0.02))
                continue

            if self._serial.is_connected:
                self._serial.set_target(angle)

            self.playback_progress.emit(i, total)
            i += 1

            if i >= total:
                if loop:
                    start_time = time.time()
                    t_offset = 0.0
                    i = 0
                else:
                    break

        self._playback_active = False
        if self._serial.is_connected:
            self._serial.set_target(0.0)
        self.playback_stopped.emit()
