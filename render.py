"""Render top and side projections of a PLY cloud written by listen.py."""
import sys
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

src = sys.argv[1] if len(sys.argv) > 1 else "cloud.ply"
dst = sys.argv[2] if len(sys.argv) > 2 else "cloud.png"
with open(src) as f:
    skip = next(i for i, line in enumerate(f) if line.strip() == "end_header") + 1
x, y, z, _ = np.loadtxt(src, skiprows=skip).T
d = np.sqrt(x * x + y * y + z * z)
fig, ax = plt.subplots(1, 3, figsize=(18, 6))
for a, (u, v, t) in zip(ax, [(x, y, "top XY"), (x, z, "side XZ"), (y, z, "side YZ")]):
    a.scatter(u, v, s=0.05, c=d, cmap="turbo", vmax=4)
    a.set_title(t); a.set_aspect("equal"); a.grid(alpha=.3)
fig.tight_layout(); fig.savefig(dst, dpi=90)
print(f"{len(x)} points, z {z.min():.2f}..{z.max():.2f} m -> {dst}")
