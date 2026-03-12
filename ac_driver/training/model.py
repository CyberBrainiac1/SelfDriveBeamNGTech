"""
model.py
========
NVIDIA end-to-end self-driving CNN — adapted for Assetto Corsa.

Architecture based on:
    "End to End Learning for Self-Driving Cars" — Bojarski et al. 2016

Input  : (H, W, 3) colour frame — default 66 × 200, float32 [0, 1]
Output : single float — steer_norm in [-1, +1]

Improvements over original ACDriver kerascnn.py
-----------------------------------------------
• Uses TensorFlow 2 / Keras (replaces broken keras 1.x calls)
  - `keras.optimizers.adam()` → `tf.keras.optimizers.Adam()`
  - `K.set_image_dim_ordering` removed (TF2 always channels-last)
• Output: 1 neuron (regression), `tanh` → -1 … +1
  Original had Dense(3, tanh) with categorical_crossentropy — WRONG.
  A steering angle is a continuous value, not a 3-class problem.
• Loss: `mse`  (mean squared error for regression)
• BatchNorm added for training stability
• Dropout tuned for small datasets
"""

from __future__ import annotations

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers


def build_model(img_h: int = 66, img_w: int = 200, img_c: int = 3) -> keras.Model:
    """Build and return the NVIDIA-style steering regression model."""
    inp = keras.Input(shape=(img_h, img_w, img_c), name="frame")

    # Normalisation inside the model so it's baked in at inference time
    x = layers.Lambda(lambda z: z / 255.0 - 0.5, name="normalise")(inp)

    # 5 convolutional layers (NVIDIA architecture)
    x = layers.Conv2D(24, 5, strides=2, activation="elu", name="conv1")(x)
    x = layers.Conv2D(36, 5, strides=2, activation="elu", name="conv2")(x)
    x = layers.Conv2D(48, 5, strides=2, activation="elu", name="conv3")(x)
    x = layers.Conv2D(64, 3, activation="elu", name="conv4")(x)
    x = layers.Conv2D(64, 3, activation="elu", name="conv5")(x)
    x = layers.Dropout(0.2)(x)

    x = layers.Flatten(name="flatten")(x)

    # Fully connected
    x = layers.Dense(100, activation="elu", name="fc1")(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(50,  activation="elu", name="fc2")(x)
    x = layers.Dense(10,  activation="elu", name="fc3")(x)

    # Steering output — tanh clamps to [-1, +1]
    out = layers.Dense(1, activation="tanh", name="steer_out")(x)

    model = keras.Model(inputs=inp, outputs=out, name="ACDriverNet")
    return model


def compile_model(model: keras.Model, lr: float = 1e-4) -> keras.Model:
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=lr),
        loss="mse",
        metrics=["mae"],
    )
    return model


def load_model(path: str) -> keras.Model:
    return keras.models.load_model(path)


if __name__ == "__main__":
    m = build_model()
    compile_model(m)
    m.summary()
