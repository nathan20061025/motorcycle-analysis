"""All thresholds with documented defaults; each overridable via env var TRAFFIC_<NAME>."""
import os
from dataclasses import dataclass, fields, asdict


def _env(name, default):
    v = os.environ.get("TRAFFIC_" + name.upper())
    return type(default)(v) if v is not None else default


@dataclass
class Settings:
    # detection / tracking
    model: str = "yolov8s.pt"        # weights (swap in fine-tuned .pt here)
    tracker: str = "bytetrack"       # bytetrack | botsort
    device: str = "cpu"              # cpu | cuda
    conf: float = 0.25               # detection confidence
    imgsz: int = 960                 # inference size
    stride: int = 1                  # process every Nth frame
    # stitching
    max_interp_gap: int = 10         # frames of gap to interpolate
    merge_max_gap_s: float = 2.0     # max time gap to merge tracks
    merge_dist_scale: float = 1.5    # allowed distance error, in bbox heights
    merge_size_ratio: float = 1.6    # max bbox size ratio between A and B
    merge_heading_deg: float = 60.0  # max heading difference
    min_track_s: float = 0.5         # shorter tracks excluded from events
    # trajectory
    vel_window_s: float = 1.0        # velocity window
    smooth_window: int = 9           # Savitzky-Golay window (frames, odd)
    # wrong-way
    tolerance_deg: float = 60.0      # default zone angular tolerance
    ww_min_opposed_s: float = 1.5    # sustained opposed heading
    ww_borderline_s: float = 0.8     # between this and ww_min_opposed_s => insufficient_evidence
    ww_min_disp: float = 1.0         # net displacement against direction (bbox-heights, or ground units w/ homography)
    ww_turn_deg: float = 45.0        # heading change marking a turn
    ww_min_in_zone: float = 0.6      # fraction of track inside zones
    stationary_speed: float = 0.3    # bbox-heights/s (or ground units/s) below which a bike is stopped
    min_quality: float = 0.5         # track quality floor
    # crosswalk
    cw_min_frames: int = 5           # frames ground point inside
    cw_min_extent_frac: float = 0.5  # displacement through polygon / its extent
    cw_walk_speed: float = 0.8       # speed below this + person beside => walking
    event_merge_s: float = 2.0       # merge events on same track within this gap


def load() -> Settings:
    s = Settings()
    for f in fields(s):
        setattr(s, f.name, _env(f.name, getattr(s, f.name)))
    return s


def defaults() -> dict:
    return asdict(Settings())
