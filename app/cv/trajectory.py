"""Per-track trajectories: smoothing, velocity, heading, displacement. Ground point = bbox bottom-center.
Without homography, distances/speeds are normalized by median bbox height (pixel-space fallback;
biased by perspective: far bikes look slower). With homography they are in ground-plane units."""
from dataclasses import dataclass, field
import numpy as np
from scipy.signal import savgol_filter
from app.cv.geometry import angle_of, project


@dataclass
class Track:
    id: int
    cls: str = "motorcycle"
    frames: list = field(default_factory=list)
    boxes: list = field(default_factory=list)   # (x1,y1,x2,y2)
    confs: list = field(default_factory=list)
    fps: float = 25.0
    raw_ids: list = field(default_factory=list)
    interpolated: set = field(default_factory=set)   # frames filled by interpolation

    def add(self, frame, box, conf):
        self.frames.append(frame); self.boxes.append(tuple(box)); self.confs.append(conf)

    @property
    def duration_s(self):
        return (self.frames[-1] - self.frames[0]) / self.fps if len(self.frames) > 1 else 0.0

    def ground_px(self):
        b = np.asarray(self.boxes, float).reshape(-1, 4)
        return np.stack([(b[:, 0] + b[:, 2]) / 2, b[:, 3]], 1)

    def scale(self, H=None):
        """Normalizer: median bbox height in px (1.0 when a homography is used)."""
        if H is not None or not self.boxes:
            return 1.0
        b = np.asarray(self.boxes, float).reshape(-1, 4)
        return float(max(np.median(b[:, 3] - b[:, 1]), 1.0))

    def quality(self):
        """0..1: mean confidence x frame coverage (observed / spanned)."""
        if not self.frames:
            return 0.0
        span = self.frames[-1] - self.frames[0] + 1
        return float(np.clip(np.mean(self.confs) * len(self.frames) / span, 0, 1))


def smooth(xy, window=9):
    n = len(xy)
    w = min(window, n if n % 2 else n - 1)
    if w < 5:
        return xy.copy()
    return savgol_filter(xy, w, 2, axis=0)


def analyze(track: Track, H=None, vel_window_s=1.0, smooth_window=9):
    """Dict of per-sample arrays: xy (smoothed, normalized units), t, vel, speed, heading (deg)."""
    g = track.ground_px()
    px = smooth(g, smooth_window)
    if H is not None and len(g):
        g = project(H, g)
    xy = smooth(g, smooth_window) / track.scale(H)
    t = np.asarray(track.frames, float) / track.fps
    n = len(xy)
    vel = np.zeros((n, 2))
    for i in range(n):
        j = int(np.searchsorted(t, t[i] - vel_window_s, side="left"))
        k = min(n - 1, int(np.searchsorted(t, t[i] + vel_window_s / 2, side="right")) - 1)
        if k > j and t[k] > t[j]:
            vel[i] = (xy[k] - xy[j]) / (t[k] - t[j])
    speed = np.hypot(vel[:, 0], vel[:, 1])
    heading = np.array([angle_of(*v) for v in vel])
    return {"xy": xy, "px": px, "t": t, "vel": vel, "speed": speed, "heading": heading}


def runs(mask, t, bridge_s=0.3):
    """(start,end) index pairs of True runs; gaps <= bridge_s are bridged."""
    idx = np.flatnonzero(mask)
    out = []
    if not len(idx):
        return out
    s = p = idx[0]
    for i in idx[1:]:
        if t[i] - t[p] <= bridge_s:
            p = i
        else:
            out.append((int(s), int(p))); s = p = i
    out.append((int(s), int(p)))
    return out


def net_displacement(xy):
    return float(np.linalg.norm(xy[-1] - xy[0])) if len(xy) > 1 else 0.0
