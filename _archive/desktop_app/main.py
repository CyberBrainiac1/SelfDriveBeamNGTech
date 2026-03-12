"""
desktop_app/main.py — Entry point for SelfDriveBeamNGTech desktop app.
"""
import sys
import argparse
from PySide6.QtWidgets import QApplication
from app import MainApp


def parse_args():
    parser = argparse.ArgumentParser(description="SelfDriveBeamNGTech Desktop App")
    parser.add_argument("--beamng-mode", action="store_true",
                        help="Launch directly into BeamNG AI mode tab")
    return parser.parse_args()


def main():
    args = parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName("SelfDriveBeamNGTech")
    app.setOrganizationName("SelfDriveBeamNGTech")

    window = MainApp(start_in_beamng_mode=args.beamng_mode)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
