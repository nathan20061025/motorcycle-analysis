from dataclasses import fields
from typing import Literal, Optional
from pydantic import BaseModel, Field

Pt = tuple[float, float]


class Zone(BaseModel):
    """Direction zone. Empty polygon = whole frame (used for a global default direction)."""
    id: str
    polygon: list[Pt]
    direction_deg: float                 # permitted heading, image coords (0=right, 90=down)
    tolerance_deg: float = 60.0
    two_way: bool = False


class Crosswalk(BaseModel):
    id: str
    polygon: list[Pt]


class VideoConfig(BaseModel):
    zones: list[Zone] = []
    crosswalks: list[Crosswalk] = []
    homography_points: Optional[list[Pt]] = None   # 4 image pts (TL,TR,BR,BL of a ground rectangle)
    ground_size: Pt = (10.0, 10.0)                 # that rectangle's real size (metres) -> ground units
    default_direction: Optional[float] = None
    thresholds: dict[str, float] = {}              # overrides of core.config.Settings fields

    def settings(self, base):
        from dataclasses import replace
        ok = {f.name: type(getattr(base, f.name))(self.thresholds[f.name])
              for f in fields(base) if f.name in self.thresholds}
        return replace(base, **ok)


class Event(BaseModel):
    event_id: str
    type: Literal["wrong_way", "crosswalk_riding"]
    status: Literal["suspected", "insufficient_evidence"]
    track_id: int
    raw_track_ids: list[int]
    start_frame: int
    end_frame: int
    start_time_s: float
    end_time_s: float
    confidence: float = Field(ge=0, le=1)
    reasons: list[str] = []
    rider_state: Optional[Literal["riding", "walking", "unknown"]] = None
    rider_confidence: Optional[float] = None
    zone_id: Optional[str] = None
    crosswalk_id: Optional[str] = None
    metrics: dict = {}
    evidence: list[str] = []
    review: Literal["pending", "confirmed", "rejected"] = "pending"
