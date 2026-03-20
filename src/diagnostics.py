"""
diagnostics.py - Startup self-diagnostics.

Checks the environment (Python version, BeamNGpy, numpy, scipy, BeamNG path)
and prints a diagnostic report.
"""

import sys
import platform
from pathlib import Path
from typing import List, Tuple


class Diagnostics:
    """
    Run startup checks and print a diagnostics report.

    Each check returns (name, ok: bool, message: str).
    """

    MIN_PYTHON = (3, 9)
    MIN_BEAMNGPY = (1, 28)

    def __init__(self):
        self._results: List[Tuple[str, bool, str]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, bng_home: str = None) -> bool:
        """
        Run all checks.

        Parameters
        ----------
        bng_home : BeamNG installation path to validate (optional)

        Returns
        -------
        bool - True if all critical checks passed
        """
        self._results.clear()

        self._check_python()
        self._check_beamngpy()
        self._check_numpy()
        self._check_scipy()
        self._check_yaml()

        if bng_home is not None:
            self._check_beamng_path(bng_home)

        self._check_output_dirs()

        return self._print_report()

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_python(self) -> None:
        major, minor = sys.version_info[:2]
        version_str = f"{major}.{minor}.{sys.version_info[2]}"
        ok = (major, minor) >= self.MIN_PYTHON
        msg = f"Python {version_str}"
        if not ok:
            msg += f" (need >= {self.MIN_PYTHON[0]}.{self.MIN_PYTHON[1]})"
        self._results.append(("Python version", ok, msg))

    def _check_beamngpy(self) -> None:
        try:
            import beamngpy
            version_str = getattr(beamngpy, "__version__", "unknown")
            # Try to parse version
            parts = version_str.split(".")
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            ok = (major, minor) >= self.MIN_BEAMNGPY
            msg = f"beamngpy {version_str}"
            if not ok:
                msg += f" (need >= {self.MIN_BEAMNGPY[0]}.{self.MIN_BEAMNGPY[1]})"
        except ImportError:
            ok = False
            msg = "beamngpy NOT INSTALLED  ->  pip install beamngpy"
        self._results.append(("BeamNGpy", ok, msg))

    def _check_numpy(self) -> None:
        try:
            import numpy as np
            ok = True
            msg = f"numpy {np.__version__}"
        except ImportError:
            ok = False
            msg = "numpy NOT INSTALLED  ->  pip install numpy"
        self._results.append(("numpy", ok, msg))

    def _check_scipy(self) -> None:
        try:
            import scipy
            ok = True
            msg = f"scipy {scipy.__version__}"
        except ImportError:
            ok = False
            msg = "scipy NOT INSTALLED  ->  pip install scipy  (optional but recommended)"
        self._results.append(("scipy", ok, msg))  # Not critical

    def _check_yaml(self) -> None:
        try:
            import yaml
            ok = True
            msg = f"PyYAML {yaml.__version__}"
        except ImportError:
            ok = False
            msg = "PyYAML NOT INSTALLED  ->  pip install pyyaml"
        self._results.append(("PyYAML", ok, msg))

    def _check_beamng_path(self, bng_home: str) -> None:
        path = Path(bng_home)
        if not path.is_dir():
            ok = False
            msg = f"{bng_home}  <- directory not found"
        elif not (path / "BeamNG.tech.exe").is_file():
            ok = False
            msg = f"{bng_home}  <- BeamNG.tech.exe not found in directory"
        else:
            ok = True
            msg = f"{bng_home}  OK"
        self._results.append(("BeamNG path", ok, msg))

    def _check_output_dirs(self) -> None:
        dirs = [Path("output/logs"), Path("output/diagnostics")]
        all_ok = True
        created = []
        for d in dirs:
            if not d.exists():
                try:
                    d.mkdir(parents=True, exist_ok=True)
                    created.append(str(d))
                except OSError:
                    all_ok = False
        msg = "output directories ready"
        if created:
            msg += f" (created: {', '.join(created)})"
        self._results.append(("Output dirs", all_ok, msg))

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def _print_report(self) -> bool:
        width = 60
        print()
        print("=" * width)
        print("  BeamNG Self-Drive - Startup Diagnostics")
        print("=" * width)
        print(f"  Platform : {platform.system()} {platform.release()}")
        print(f"  Python   : {sys.executable}")
        print("-" * width)

        # Non-critical checks (scipy)
        critical_failures = []
        for name, ok, msg in self._results:
            status = "OK   " if ok else "FAIL "
            print(f"  [{status}] {name:<18} {msg}")
            # scipy is optional
            if not ok and name not in ("scipy",):
                critical_failures.append(name)

        print("-" * width)
        if critical_failures:
            print(f"  CRITICAL FAILURES: {', '.join(critical_failures)}")
            print("  Cannot start.  Please fix the issues above.")
            print("=" * width)
            print()
            return False
        else:
            print("  All critical checks passed.")
            print("=" * width)
            print()
            return True
