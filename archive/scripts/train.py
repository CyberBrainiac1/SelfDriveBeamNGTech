"""
train.py
========
CLI entry point for model training.

Usage
-----
  python scripts/train.py
  python scripts/train.py --epochs 50 --batch-size 64

The trained model is saved to  models/acdriver_model.keras.
"""

from __future__ import annotations
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import CFG
from training.model import build_model, compile_model
from training.train_model import train


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train the ACDriver steering CNN")
    p.add_argument("--epochs",     type=int, default=CFG.training.epochs)
    p.add_argument("--batch-size", type=int, default=CFG.training.batch_size)
    return p.parse_args()


if __name__ == "__main__":
    args = _parse()
    CFG.training.epochs     = args.epochs
    CFG.training.batch_size = args.batch_size

    print("=== ACDriver Model Training ===")
    print(f"Data dir  : {CFG.training.data_dir}")
    print(f"Model out : {CFG.training.model_path}")
    print(f"Epochs    : {CFG.training.epochs}")
    print(f"Batch     : {CFG.training.batch_size}\n")

    model = build_model(CFG.training.img_height, CFG.training.img_width)
    model = compile_model(model, lr=CFG.training.learning_rate)
    train(model, CFG)
