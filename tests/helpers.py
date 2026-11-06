import cv2
import numpy as np
from app.cv.tracker import Det
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


class FakeTracker:
    """Stands in for YOLO: one motorcycle (id 7) moving left 4 px/frame; one extra person every frame."""
    def __init__(self):
        self.k = 0

    def update(self, frame):
        x = 300 - 4 * self.k
        self.k += 1
        return [Det(7, "motorcycle", x - 10, 170, x + 10, 200, 0.9), Det(1, "person", 5, 5, 20, 40, 0.8)]


def make_video(path, n=60, w=320, h=240, fps=10):
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for _ in range(n):
        vw.write(np.full((h, w, 3), 80, np.uint8))
    vw.release()
    return str(path)
