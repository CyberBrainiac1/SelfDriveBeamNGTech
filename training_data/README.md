Training data lives here.

Structure:
- `assetto_corsa/`: `.npz` shards from the AC screen/telemetry collector
- `beamng_teacher/`: BeamNG teacher captures with `labels.csv` and `images/`

BeamNG usage:
- `python main.py --stage ai --teacher-dir auto ...`
- `python main.py --stage ai --teacher-dir hirochi_bolide_fast ...`

AC usage:
- `python scripts/collect_data.py`
