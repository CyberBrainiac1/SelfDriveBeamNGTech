"""
Creates scenarios, spawns vehicles, and manages scenario lifecycle.
"""

from __future__ import annotations
from typing import Optional

from beamngpy import BeamNGpy, Scenario, Vehicle

from config import CFG


class ScenarioManager:
    """Builds a test scenario and spawns the ego vehicle."""

    def __init__(self, bng: BeamNGpy) -> None:
        self._bng = bng
        self.scenario: Optional[Scenario] = None
        self.vehicle: Optional[Vehicle] = None

    # ── public ─────────────────────────────────────────────────────
    def create_and_start(self) -> Vehicle:
        """Create scenario, add vehicle, load, and start. Returns the ego vehicle."""
        cfg = CFG.scenario
        print(f"[scene] Creating scenario '{cfg.name}' on '{cfg.level}' …")

        self.vehicle = Vehicle(cfg.vehicle_name, model=cfg.vehicle_model)
        self.scenario = Scenario(cfg.level, cfg.name)
        self.scenario.add_vehicle(
            self.vehicle,
            pos=cfg.spawn_pos,
            rot_quat=cfg.spawn_rot_quat,
        )
        self.scenario.make(self._bng)

        print("[scene] Loading scenario …")
        self._bng.scenario.load(self.scenario)
        self._bng.scenario.start()

        # Pause the sim so we can step manually
        self._bng.control.pause()
        print("[scene] Scenario started (paused for stepping).")
        return self.vehicle

    def cleanup(self) -> None:
        """Stop scenario if running."""
        try:
            if self.scenario is not None:
                self._bng.scenario.stop()
                print("[scene] Scenario stopped.")
        except Exception as exc:
            print(f"[scene] Cleanup warning: {exc}")
