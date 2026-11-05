import numpy as np
from app.cv.trajectory import Track


def line_track(id=1, f0=0, n=40, x0=800, y=300, vx=-8.0, vy=0.0, fps=10.0, h=40, w=20, jitter=0.0, seed=0):
    rng = np.random.default_rng(seed)
    t = Track(id, fps=fps, raw_ids=[id])
    for k in range(n):
        x, yy = x0 + vx * k + rng.normal(0, jitter), y + vy * k + rng.normal(0, jitter)
        t.add(f0 + k, (x - w / 2, yy - h, x + w / 2, yy), 0.9)
    return t


def path_track(xs, ys, id=1, fps=10.0, h=40, w=20):
    t = Track(id, fps=fps, raw_ids=[id])
    for k, (x, y) in enumerate(zip(xs, ys)):
        t.add(k, (x - w / 2, y - h, x + w / 2, y), 0.9)
    return t
