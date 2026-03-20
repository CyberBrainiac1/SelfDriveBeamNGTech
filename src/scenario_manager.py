"""
scenario_manager.py — Scenario lifecycle management.
"""

import time
from typing import Optional

from logger import get_logger


class ScenarioManager:
    """
    Manages the BeamNG scenario lifecycle: setup, reset, and teardown.

    Works alongside BeamNGBridge; does not duplicate sensor attachment.
    """

    def __init__(self):
        self._logger = get_logger("ScenarioManager")
        self._bng = None
        self._scenario = None
        self._vehicle = None
        self._config = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def setup(self, bng, config) -> None:
        """
        Reference an already-started scenario from BeamNGBridge.

        This is called after BeamNGBridge.setup_scenario() so we can
        issue additional commands (e.g., camera mode).

        Parameters
        ----------
        bng    : BeamNG instance (from bridge.bng)
        config : Config instance
        """
        self._bng = bng
        self._config = config
        self._logger = get_logger("ScenarioManager", config)

        # Optional: set 3rd-person camera
        try:
            self._bng.camera.set_player_camera_mode(0)
        except Exception as e:
            self._logger.debug("Could not set camera mode: %s", e)

        self._logger.info("ScenarioManager: scenario is live.")

    def reset(self) -> None:
        """
        Reload the current scenario (after off-track or damage).
        """
        if self._bng is None:
            self._logger.warning("reset() called but no BeamNG instance.")
            return

        self._logger.info("Reloading scenario...")
        try:
            self._bng.scenario.restart()
            time.sleep(1.5)
            self._logger.info("Scenario restarted.")
        except Exception as e:
            self._logger.error("Scenario restart failed: %s", e)

    def teardown(self) -> None:
        """Stop the scenario (called before bridge.close())."""
        self._logger.info("ScenarioManager teardown.")
        self._bng = None
        self._scenario = None
        self._vehicle = None
