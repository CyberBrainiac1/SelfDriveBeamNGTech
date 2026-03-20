"""
BeamNG imitation-learning helpers.

This module trains and runs a context-aware driving policy from BeamNG teacher
captures recorded with `--teacher-dir`.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from typing import Iterable, List, Optional

import cv2
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


DEFAULT_IMG_WIDTH = 200
DEFAULT_IMG_HEIGHT = 66
DEFAULT_MAX_SPEED_KPH = 220.0
DEFAULT_MODEL_PATH = os.path.join("models", "beamng_imitation.keras")
UNKNOWN_VEHICLE = "__unknown__"
STEERING_SMOOTH_WINDOW = 5
SPEED_SMOOTH_WINDOW = 7
SPEED_LOOKAHEAD_FRAMES = 12


@dataclass
class TeacherSample:
    image_path: str
    steering: float
    current_speed_kph: float
    target_speed_kph: float
    damage: float
    vehicle: str
    map_name: str


@dataclass
class DrivePrediction:
    steering: float
    speed_target_kph: float


def preprocess_bgr_frame(
    bgr_frame: np.ndarray,
    img_width: int = DEFAULT_IMG_WIDTH,
    img_height: int = DEFAULT_IMG_HEIGHT,
) -> np.ndarray:
    """Crop, convert to RGB, and resize a BeamNG camera frame."""
    h, _w = bgr_frame.shape[:2]
    top = int(h * 0.35)
    bottom = int(h * 0.88)
    cropped = bgr_frame[top:bottom, :]
    rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (img_width, img_height), interpolation=cv2.INTER_AREA)
    return rgb.astype(np.uint8)


def _smooth_series(values: np.ndarray, window: int) -> np.ndarray:
    if len(values) <= 1 or window <= 1:
        return values.astype(np.float32)
    radius = window // 2
    padded = np.pad(values.astype(np.float32), (radius, radius), mode="edge")
    kernel = np.ones(window, dtype=np.float32) / float(window)
    return np.convolve(padded, kernel, mode="valid")


def _future_mean_speed(values: np.ndarray, horizon: int) -> np.ndarray:
    if len(values) == 0:
        return values.astype(np.float32)
    out = np.zeros_like(values, dtype=np.float32)
    for idx in range(len(values)):
        end = min(len(values), idx + max(1, horizon))
        out[idx] = float(np.mean(values[idx:end]))
    return out


def _load_teacher_rows(teacher_dir: str) -> List[TeacherSample]:
    labels_path = os.path.join(teacher_dir, "labels.csv")
    if not os.path.isfile(labels_path):
        raise FileNotFoundError(f"Teacher labels not found: {labels_path}")

    raw_rows: List[dict] = []
    with open(labels_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            image_rel = row.get("image_path")
            if not image_rel:
                continue
            image_path = os.path.join(teacher_dir, image_rel)
            if not os.path.isfile(image_path):
                continue

            steering = float(row.get("steering_input", 0.0) or 0.0)
            current_speed_kph = float(row.get("speed_kph", 0.0) or 0.0)
            damage = float(row.get("damage", 0.0) or 0.0)
            if damage > 1.0:
                continue
            if current_speed_kph < 10.0 and abs(steering) < 0.05:
                continue

            raw_rows.append(
                {
                    "image_path": image_path,
                    "steering": float(np.clip(steering, -1.0, 1.0)),
                    "speed_kph": float(np.clip(current_speed_kph, 0.0, DEFAULT_MAX_SPEED_KPH)),
                    "damage": damage,
                    "vehicle": (row.get("vehicle") or UNKNOWN_VEHICLE).strip() or UNKNOWN_VEHICLE,
                    "map_name": (row.get("map") or "").strip(),
                }
            )

    if not raw_rows:
        raise RuntimeError(f"No valid teacher samples found in {teacher_dir}")

    steering_values = np.asarray([row["steering"] for row in raw_rows], dtype=np.float32)
    speed_values = np.asarray([row["speed_kph"] for row in raw_rows], dtype=np.float32)
    smooth_steering = _smooth_series(steering_values, STEERING_SMOOTH_WINDOW)
    smooth_speed = _smooth_series(speed_values, SPEED_SMOOTH_WINDOW)
    future_speed = _future_mean_speed(smooth_speed, SPEED_LOOKAHEAD_FRAMES)
    desired_speed = np.clip(0.35 * smooth_speed + 0.65 * future_speed, 0.0, DEFAULT_MAX_SPEED_KPH)

    samples: List[TeacherSample] = []
    for idx, row in enumerate(raw_rows):
        samples.append(
            TeacherSample(
                image_path=row["image_path"],
                steering=float(np.clip(smooth_steering[idx], -1.0, 1.0)),
                current_speed_kph=float(smooth_speed[idx]),
                target_speed_kph=float(desired_speed[idx]),
                damage=float(row["damage"]),
                vehicle=str(row["vehicle"]),
                map_name=str(row["map_name"]),
            )
        )
    return samples


def load_teacher_dataset(
    teacher_dirs: Iterable[str],
    img_width: int = DEFAULT_IMG_WIDTH,
    img_height: int = DEFAULT_IMG_HEIGHT,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """Load one or more teacher directories into model arrays."""
    all_samples: List[TeacherSample] = []
    for teacher_dir in teacher_dirs:
        samples = _load_teacher_rows(teacher_dir)
        print(f"[beamng-train] Loading {len(samples)} samples from {teacher_dir}")
        all_samples.extend(samples)

    if not all_samples:
        raise RuntimeError("No teacher samples loaded.")

    vehicle_vocab = [UNKNOWN_VEHICLE]
    vehicle_vocab.extend(sorted({sample.vehicle for sample in all_samples if sample.vehicle != UNKNOWN_VEHICLE}))
    vehicle_to_index = {name: idx for idx, name in enumerate(vehicle_vocab)}

    frames: List[np.ndarray] = []
    current_speeds: List[float] = []
    target_speeds: List[float] = []
    steering_labels: List[float] = []
    vehicle_indices: List[int] = []

    for sample in all_samples:
        image = cv2.imread(sample.image_path, cv2.IMREAD_COLOR)
        if image is None:
            continue
        frames.append(preprocess_bgr_frame(image, img_width, img_height))
        current_speeds.append(sample.current_speed_kph)
        target_speeds.append(sample.target_speed_kph)
        steering_labels.append(sample.steering)
        vehicle_indices.append(vehicle_to_index.get(sample.vehicle, 0))

    if not frames:
        raise RuntimeError("No teacher frames loaded.")

    X_frames = np.stack(frames).astype(np.float32)
    X_speed = np.asarray(current_speeds, dtype=np.float32).reshape(-1, 1)
    X_vehicle = np.asarray(vehicle_indices, dtype=np.int32).reshape(-1, 1)
    y_steer = np.asarray(steering_labels, dtype=np.float32).reshape(-1, 1)
    y_speed = np.asarray(target_speeds, dtype=np.float32).reshape(-1, 1)

    print(
        f"[beamng-train] Dataset: {X_frames.shape[0]} frames  "
        f"steer min={float(y_steer.min()):+.3f} max={float(y_steer.max()):+.3f}  "
        f"speed min={float(y_speed.min()):.1f} max={float(y_speed.max()):.1f}"
    )
    print(f"[beamng-train] Vehicles: {', '.join(vehicle_vocab)}")
    return X_frames, X_speed, X_vehicle, y_steer, y_speed, vehicle_vocab


def augment_dataset(
    X_frames: np.ndarray,
    X_speed: np.ndarray,
    X_vehicle: np.ndarray,
    y_steer: np.ndarray,
    y_speed: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Mirror augmentation with steering sign flip."""
    flipped_frames = X_frames[:, :, ::-1, :]
    flipped_steer = -y_steer

    X_frames_aug = np.concatenate([X_frames, flipped_frames], axis=0)
    X_speed_aug = np.concatenate([X_speed, X_speed], axis=0)
    X_vehicle_aug = np.concatenate([X_vehicle, X_vehicle], axis=0)
    y_steer_aug = np.concatenate([y_steer, flipped_steer], axis=0)
    y_speed_aug = np.concatenate([y_speed, y_speed], axis=0)

    idx = np.random.permutation(len(X_frames_aug))
    return (
        X_frames_aug[idx],
        X_speed_aug[idx],
        X_vehicle_aug[idx],
        y_steer_aug[idx],
        y_speed_aug[idx],
    )


def build_policy_model(
    num_vehicles: int,
    img_height: int = DEFAULT_IMG_HEIGHT,
    img_width: int = DEFAULT_IMG_WIDTH,
    img_channels: int = 3,
    max_speed_kph: float = DEFAULT_MAX_SPEED_KPH,
) -> keras.Model:
    frame_in = keras.Input(shape=(img_height, img_width, img_channels), name="frame")
    speed_in = keras.Input(shape=(1,), name="current_speed")
    vehicle_in = keras.Input(shape=(1,), dtype="int32", name="vehicle_idx")

    x = layers.Rescaling(scale=1.0 / 255.0, offset=-0.5, name="normalise")(frame_in)
    x = layers.Conv2D(24, 5, strides=2, activation="elu")(x)
    x = layers.Conv2D(36, 5, strides=2, activation="elu")(x)
    x = layers.Conv2D(48, 5, strides=2, activation="elu")(x)
    x = layers.Conv2D(64, 3, activation="elu")(x)
    x = layers.Conv2D(64, 3, activation="elu")(x)
    x = layers.Dropout(0.18)(x)
    x = layers.Flatten()(x)

    speed_x = layers.Rescaling(scale=1.0 / max_speed_kph, name="normalise_speed")(speed_in)
    vehicle_dim = max(2, min(8, num_vehicles))
    vehicle_x = layers.Embedding(num_vehicles, vehicle_dim, name="vehicle_embedding")(vehicle_in)
    vehicle_x = layers.Flatten()(vehicle_x)

    x = layers.Concatenate(name="fusion")([x, speed_x, vehicle_x])
    x = layers.Dense(128, activation="elu")(x)
    x = layers.Dropout(0.25)(x)
    x = layers.Dense(64, activation="elu")(x)
    x = layers.Dense(24, activation="elu")(x)

    steer_out = layers.Dense(1, activation="tanh", name="steer_out")(x)
    speed_out = layers.Dense(1, activation="sigmoid")(x)
    speed_out = layers.Rescaling(scale=max_speed_kph, name="speed_kph")(speed_out)

    model = keras.Model(
        inputs={"frame": frame_in, "current_speed": speed_in, "vehicle_idx": vehicle_in},
        outputs={"steer_out": steer_out, "speed_kph": speed_out},
        name="BeamNGDrivePolicyNet",
    )
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-4),
        loss={"steer_out": "mse", "speed_kph": "mse"},
        loss_weights={"steer_out": 1.4, "speed_kph": 0.35},
        metrics={"steer_out": ["mae"], "speed_kph": ["mae"]},
    )
    return model


def train_model(
    teacher_dirs: Iterable[str],
    model_path: str = DEFAULT_MODEL_PATH,
    epochs: int = 18,
    batch_size: int = 32,
    img_width: int = DEFAULT_IMG_WIDTH,
    img_height: int = DEFAULT_IMG_HEIGHT,
) -> dict:
    teacher_dirs = list(teacher_dirs)
    (
        X_frames,
        X_speed,
        X_vehicle,
        y_steer,
        y_speed,
        vehicle_vocab,
    ) = load_teacher_dataset(teacher_dirs, img_width=img_width, img_height=img_height)
    (
        X_frames,
        X_speed,
        X_vehicle,
        y_steer,
        y_speed,
    ) = augment_dataset(X_frames, X_speed, X_vehicle, y_steer, y_speed)

    steer_weight = 1.0 + np.minimum(np.abs(y_steer[:, 0]) * 2.5, 1.5)
    speed_weight = 0.75 + np.clip((y_speed[:, 0] / DEFAULT_MAX_SPEED_KPH) * 0.75, 0.0, 0.75)

    model = build_policy_model(
        num_vehicles=len(vehicle_vocab),
        img_height=img_height,
        img_width=img_width,
    )
    os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)

    callbacks = [
        tf.keras.callbacks.ModelCheckpoint(
            model_path,
            monitor="val_loss",
            save_best_only=True,
            verbose=1,
        ),
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=4,
            restore_best_weights=True,
            verbose=1,
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=2,
            verbose=1,
        ),
    ]

    history = model.fit(
        {"frame": X_frames, "current_speed": X_speed, "vehicle_idx": X_vehicle},
        {"steer_out": y_steer, "speed_kph": y_speed},
        sample_weight={"steer_out": steer_weight, "speed_kph": speed_weight},
        batch_size=batch_size,
        epochs=epochs,
        validation_split=0.15,
        callbacks=callbacks,
        verbose=2,
    )

    meta = {
        "teacher_dirs": teacher_dirs,
        "model_path": model_path,
        "epochs": epochs,
        "batch_size": batch_size,
        "train_samples": int(X_frames.shape[0]),
        "best_val_loss": float(min(history.history["val_loss"])),
        "best_val_steer_mae": float(min(history.history["val_steer_out_mae"])),
        "best_val_speed_mae": float(min(history.history["val_speed_kph_mae"])),
        "vehicle_vocab": vehicle_vocab,
        "max_speed_kph": DEFAULT_MAX_SPEED_KPH,
        "steering_smooth_window": STEERING_SMOOTH_WINDOW,
        "speed_smooth_window": SPEED_SMOOTH_WINDOW,
        "speed_lookahead_frames": SPEED_LOOKAHEAD_FRAMES,
    }
    meta_path = os.path.splitext(model_path)[0] + ".json"
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(f"[beamng-train] Model saved to {model_path}")
    print(f"[beamng-train] Metadata saved to {meta_path}")
    return meta


class BeamNGDrivePredictor:
    """Runtime wrapper for the BeamNG driving policy model."""

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        img_width: int = DEFAULT_IMG_WIDTH,
        img_height: int = DEFAULT_IMG_HEIGHT,
    ) -> None:
        self.model_path = model_path
        self.img_width = img_width
        self.img_height = img_height
        self._model: Optional[keras.Model] = None
        self._vehicle_vocab: List[str] = [UNKNOWN_VEHICLE]
        self._vehicle_to_index = {UNKNOWN_VEHICLE: 0}
        self._max_speed_kph = DEFAULT_MAX_SPEED_KPH
        self._input_names: List[str] = []
        self._output_names: List[str] = []

    def load(self) -> bool:
        if not os.path.isfile(self.model_path):
            print(f"[beamng-imitation] Model not found at {self.model_path}")
            return False

        self._model = keras.models.load_model(self.model_path, safe_mode=False)
        self._input_names = [tensor.name.split(":")[0] for tensor in self._model.inputs]
        self._output_names = list(getattr(self._model, "output_names", []))

        meta_path = os.path.splitext(self.model_path)[0] + ".json"
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
                vehicle_vocab = list(meta.get("vehicle_vocab") or [])
                if vehicle_vocab:
                    self._vehicle_vocab = vehicle_vocab
                self._max_speed_kph = float(meta.get("max_speed_kph") or DEFAULT_MAX_SPEED_KPH)
            except Exception:
                pass
        if UNKNOWN_VEHICLE not in self._vehicle_vocab:
            self._vehicle_vocab = [UNKNOWN_VEHICLE] + self._vehicle_vocab
        self._vehicle_to_index = {name: idx for idx, name in enumerate(self._vehicle_vocab)}
        print(f"[beamng-imitation] Loaded model from {self.model_path}")
        return True

    def predict(
        self,
        bgr_frame: np.ndarray,
        current_speed_kph: float = 0.0,
        vehicle_model: str = UNKNOWN_VEHICLE,
    ) -> Optional[DrivePrediction]:
        if self._model is None:
            return None

        frame = preprocess_bgr_frame(
            bgr_frame,
            img_width=self.img_width,
            img_height=self.img_height,
        ).astype(np.float32)
        x_frame = frame[np.newaxis, ...]
        vehicle_idx = self._vehicle_to_index.get(vehicle_model or UNKNOWN_VEHICLE, 0)
        x_speed = np.asarray([[np.clip(current_speed_kph, 0.0, self._max_speed_kph)]], dtype=np.float32)
        x_vehicle = np.asarray([[vehicle_idx]], dtype=np.int32)

        if {"frame", "current_speed", "vehicle_idx"}.issubset(set(self._input_names)):
            inputs: object = {
                "frame": x_frame,
                "current_speed": x_speed,
                "vehicle_idx": x_vehicle,
            }
        else:
            inputs = x_frame

        outputs = self._model.predict(inputs, verbose=0)

        steer_value = 0.0
        speed_value = float(np.clip(current_speed_kph, 0.0, self._max_speed_kph))
        if isinstance(outputs, dict):
            if "steer_out" in outputs:
                steer_value = float(outputs["steer_out"][0][0])
            if "speed_kph" in outputs:
                speed_value = float(outputs["speed_kph"][0][0])
        elif isinstance(outputs, list):
            if outputs:
                steer_value = float(outputs[0][0][0])
            if len(outputs) > 1:
                speed_value = float(outputs[1][0][0])
        else:
            steer_value = float(outputs[0][0])

        return DrivePrediction(
            steering=float(np.clip(steer_value, -1.0, 1.0)),
            speed_target_kph=float(np.clip(speed_value, 0.0, self._max_speed_kph)),
        )


class BeamNGSteeringPredictor(BeamNGDrivePredictor):
    """Compatibility wrapper for older single-output call sites."""

    def predict(
        self,
        bgr_frame: np.ndarray,
        current_speed_kph: float = 0.0,
        vehicle_model: str = UNKNOWN_VEHICLE,
    ) -> Optional[float]:
        pred = super().predict(
            bgr_frame,
            current_speed_kph=current_speed_kph,
            vehicle_model=vehicle_model,
        )
        if pred is None:
            return None
        return pred.steering
