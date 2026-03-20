"""
Manages the BeamNG.tech simulator connection lifecycle.
"""

from __future__ import annotations
import sys
from typing import Optional

from beamngpy import BeamNGpy

from config import CFG


class SimConnection:
    """Thin wrapper around a BeamNGpy instance with clean startup/shutdown."""

    def __init__(self) -> None:
        self._bng: Optional[BeamNGpy] = None

    # ── public ─────────────────────────────────────────────────────
    def open(self) -> BeamNGpy:
        """Launch (or connect to) the simulator and return the handle."""
        cfg = CFG.beamng
        print(f"[conn] Connecting to BeamNG @ {cfg.host}:{cfg.port} …")
        try:
            self._bng = BeamNGpy(
                cfg.host,
                cfg.port,
                home=cfg.home or None,
                user=cfg.user_folder or None,
            )
            self._bng.open()
            print("[conn] Connected OK.")
        except Exception as exc:
            print(f"[conn] FAILED to connect: {exc}", file=sys.stderr)
            raise
        return self._bng

    def close(self) -> None:
        """Cleanly disconnect from the simulator."""
        if self._bng is not None:
            try:
                self._bng.close()
                print("[conn] Disconnected.")
            except Exception as exc:
                print(f"[conn] Error during disconnect: {exc}", file=sys.stderr)
            finally:
                self._bng = None

    @property
    def bng(self) -> BeamNGpy:
        assert self._bng is not None, "SimConnection not open yet."
        return self._bng

    # context‑manager support
    def __enter__(self) -> BeamNGpy:
        return self.open()

    def __exit__(self, *_: object) -> None:
        self.close()
