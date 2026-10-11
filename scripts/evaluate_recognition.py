"""Pairwise false acceptance/rejection evaluation on consented held-out embeddings."""

import argparse, json
from pathlib import Path
import numpy as np

p = argparse.ArgumentParser()
p.add_argument("data", help="Private NPZ with left,right (N,128) and same_person (N,)")
p.add_argument("--threshold", type=float, default=0.55)
p.add_argument("--output", default="evaluation-results.json")
args = p.parse_args()
with np.load(args.data, allow_pickle=False) as data:
    left = data["left"]
    right = data["right"]
    same = data["same_person"].astype(bool)
if (
    left.shape != right.shape
    or left.ndim != 2
    or left.shape[1] != 128
    or same.shape != (len(left),)
):
    raise SystemExit("Invalid evaluation array dimensions")
if not np.isfinite(left).all() or not np.isfinite(right).all():
    raise SystemExit("Non-finite embeddings")
if np.any(np.linalg.norm(left, axis=1) == 0) or np.any(
    np.linalg.norm(right, axis=1) == 0
):
    raise SystemExit("Zero embeddings")
if not same.any() or same.all():
    raise SystemExit("Both genuine and impostor pairs are required")
left = left / np.linalg.norm(left, axis=1, keepdims=True)
right = right / np.linalg.norm(right, axis=1, keepdims=True)
scores = (left * right).sum(axis=1)
accepted = scores >= args.threshold
fa = int((accepted & ~same).sum())
fr = int((~accepted & same).sum())
neg = int((~same).sum())
pos = int(same.sum())
report = {
    "threshold": args.threshold,
    "genuine_pairs": pos,
    "impostor_pairs": neg,
    "false_accepts": fa,
    "false_rejects": fr,
    "FAR": fa / neg,
    "FRR": fr / pos,
    "scope": "Pairwise verification only; excludes detector failures, temporal smoothing, ambiguity and liveness. Use subject-disjoint calibration/evaluation sets.",
}
Path(args.output).write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
