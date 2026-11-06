from fastapi import APIRouter, HTTPException
from app.core import config as core_config, db
from app.core.models import VideoConfig
from app.services.jobs import load_config

router = APIRouter(prefix="/api/videos", tags=["config"])


@router.get("/{video_id}/config")
def get_config(video_id: str):
    if not db.one("SELECT id FROM videos WHERE id=?", (video_id,)):
        raise HTTPException(404, "video not found")
    return {"config": load_config(video_id).model_dump(), "defaults": core_config.defaults()}


@router.put("/{video_id}/config")
def put_config(video_id: str, vc: VideoConfig):
    if not db.one("SELECT id FROM videos WHERE id=?", (video_id,)):
        raise HTTPException(404, "video not found")
    for z in vc.zones:
        if z.polygon and len(z.polygon) < 3:
            raise HTTPException(422, f"zone {z.id}: polygon needs >= 3 points")
    for c in vc.crosswalks:
        if len(c.polygon) < 3:
            raise HTTPException(422, f"crosswalk {c.id}: polygon needs >= 3 points")
    if vc.homography_points is not None and len(vc.homography_points) != 4:
        raise HTTPException(422, "homography needs exactly 4 points")
    bad = set(vc.thresholds) - set(core_config.defaults())
    if bad:
        raise HTTPException(422, f"unknown thresholds: {sorted(bad)}")
    db.execute("INSERT OR REPLACE INTO configs VALUES(?,?)", (video_id, vc.model_dump_json()))
    return {"config": vc.model_dump()}
