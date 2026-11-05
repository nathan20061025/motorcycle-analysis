"""Wraps Ultralytics built-in tracking (ByteTrack default, BoT-SORT selectable)."""
from dataclasses import dataclass
from app.cv.detector import CLASSES


@dataclass
class Det:
    track_id: int
    cls: str
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float

    @property
    def ground(self):
        return ((self.x1 + self.x2) / 2, self.y2)


class Tracker:
    def __init__(self, model, cfg):
        self.model, self.cfg = model, cfg

    def update(self, frame):
        r = self.model.track(frame, persist=True, conf=self.cfg.conf, imgsz=self.cfg.imgsz,
                             classes=list(CLASSES), tracker=f"{self.cfg.tracker}.yaml",
                             device=self.cfg.device, verbose=False)[0]
        b = r.boxes
        if b is None or b.id is None:
            return []
        return [Det(i, CLASSES[k], *xyxy, c) for xyxy, i, c, k in
                zip(b.xyxy.tolist(), b.id.int().tolist(), b.conf.tolist(), b.cls.int().tolist())]
