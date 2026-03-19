Training data lives here.

Structure:
- `assetto_corsa/`: `.npz` shards from the AC screen/telemetry collector
- `beamng_teacher/`: BeamNG teacher captures with `labels.csv`, `images/`, and `run_summary.json`

BeamNG usage:
- `python main.py --stage ai --teacher-dir auto ...`
- `python main.py --stage ai --teacher-dir hirochi_bolide_fast ...`
- `python scripts/import_beamng_teacher_run.py --source-dir logs/teacher_ai_hirochi_bolide_110_6laps --summary-json logs/teacher_ai_hirochi_bolide_110_6laps.json`
- `python scripts/train_beamng_imitation.py`

BeamNG training curation:
- Only canonical teacher runs under `training_data/beamng_teacher/` are considered by default
- Each run must carry its own `run_summary.json`
- The trainer rejects runs that are failed, damaged, too short, or outside the approved race-map list

AC usage:
- `python scripts/collect_data.py`
