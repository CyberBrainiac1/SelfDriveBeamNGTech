"""
beamng_manager.py - High-level BeamNG session manager.

Orchestrates connection, scenario setup, and the main control loop lifecycle.
"""

import time
from pathlib import Path
from typing import Optional

import numpy as np

from logger import get_logger
from beamng_bridge import BeamNGBridge
from vehicle_state import VehicleState


class BeamNGManager:
    """
    High-level manager that wraps BeamNGBridge.

    Handles:
    - Startup: path validation, connection, scenario setup.
    - Run: delegates to main.py control loop.
    - Shutdown: clean disconnect.
    """

    def __init__(self):
        self._logger = get_logger("BeamNGManager")
        self._bridge: Optional[BeamNGBridge] = None
        self._config = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def startup(self, config) -> BeamNGBridge:
        """
        Validate BeamNG path, connect, and set up the scenario.

        Parameters
        ----------
        config : Config instance

        Returns
        -------
        BeamNGBridge - ready-to-use bridge
        """
        from beamng_detector import BeamNGDetector

        self._config = config
        self._logger = get_logger("BeamNGManager", config)

        # Validate BeamNG installation
        detector = BeamNGDetector()
        try:
            bng_home = config.beamng.home
        except AttributeError:
            bng_home = None

        bng_home = detector.detect(bng_home)
        self._logger.info("BeamNG home: %s", bng_home)

        # Create bridge
        self._bridge = BeamNGBridge(config)

        # Connect
        try:
            host = config.beamng.host
        except AttributeError:
            host = "localhost"
        try:
            port = int(config.beamng.port)
        except AttributeError:
            port = 64256
        try:
            launch = bool(config.beamng.launch)
        except AttributeError:
            launch = True

        self._bridge.connect(bng_home=bng_home, host=host, port=port, launch=launch)

        # Set deterministic physics
        try:
            hz = int(config.runtime.deterministic_hz)
        except AttributeError:
            hz = 60
        self._bridge.set_deterministic(hz)

        # Setup scenario
        self._bridge.setup_scenario()

        # Hide HUD if configured
        try:
            if config.beamng.hide_hud:
                self._bridge.hide_hud()
        except AttributeError:
            pass

        return self._bridge

    def shutdown(self) -> None:
        """Cleanly shut down the BeamNG session."""
        if self._bridge is not None:
            self._bridge.close()
            self._bridge = None
        self._logger.info("BeamNG session shut down.")

    @property
    def bridge(self) -> Optional[BeamNGBridge]:
        return self._bridge
