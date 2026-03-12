"""
desktop_app/app.py — Main application window controller.
Wires together all pages, core services, and the main window UI.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtCore import QTimer
from ui.main_window import MainWindow
from core.serial_manager import SerialManager
from core.config_manager import ConfigManager
from core.logger import AppLogger
from core.safety_manager import SafetyManager
from core.telemetry import TelemetryBuffer
from beamng.beamng_manager import BeamNGManager
from profiles.profile_manager import ProfileManager


class MainApp:
    """
    Top-level application controller.
    Owns all service singletons and passes them to the UI.
    """

    def __init__(self, start_in_beamng_mode: bool = False):
        # ---- Core services ----
        self.logger = AppLogger()
        self.config = ConfigManager()
        self.telemetry = TelemetryBuffer()
        self.serial = SerialManager()
        self.safety = SafetyManager(self.serial, self.logger)
        self.beamng_manager = BeamNGManager(self.serial, self.logger)
        self.profiles = ProfileManager(self.config, self.logger)

        # ---- Main window ----
        self.window = MainWindow(
            serial=self.serial,
            config=self.config,
            logger=self.logger,
            safety=self.safety,
            telemetry=self.telemetry,
            beamng_manager=self.beamng_manager,
            profiles=self.profiles,
        )

        if start_in_beamng_mode:
            self.window.navigate_to("beamng_ai")

        # Main window owns its own refresh timer — no duplicate needed here.
        # Remove the app-level timer to avoid double-tick.

    def show(self):
        self.window.show()

    def _tick(self):
        pass  # main_window._refresh_timer handles periodic refresh
