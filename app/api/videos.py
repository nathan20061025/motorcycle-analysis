import shutil, time, uuid
from pathlib import Path
import cv2
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from app.core import config, db
from app.services import jobs

router = APIRouter(prefix="/api/videos", tags=["videos"])


def _vid(video_id):
    v = db.one("SELECT * FROM videos WHERE id=?", (video_id,))
    if not v:
        raise HTTPException(404, "video not found")
    return v


def _pub(v):
    return {k: v[k] for k in ("id", "filename", "fps", "width", "height", "frames", "duration_s", "created")}


@router.post("")
def upload(file: UploadFile):
    vid = uuid.uuid4().hex[:12]
    d = config.data_dir() / "videos" / vid
    d.mkdir(parents=True, exist_ok=True)
    path = d / ("video" + (Path(file.filename or "").suffix.lower() or ".mp4"))
    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    cap = cv2.VideoCapture(str(path))
    ok, frame = cap.read() if cap.isOpened() else (False, None)
    if not ok:
        cap.release(); shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(400, "not a readable video file")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    h, w = frame.shape[:2]
    cap.release()
    cv2.imwrite(str(d / "frame.jpg"), frame)
    db.execute("INSERT INTO videos VALUES(?,?,?,?,?,?,?,?,?)",
               (vid, file.filename, str(path), fps, w, h, n, n / fps, time.time()))
    return _pub(_vid(vid))


@router.get("")
def list_videos():
    return [_pub(v) for v in db.query("SELECT * FROM videos ORDER BY created DESC")]


@router.get("/{video_id}")
def get_video(video_id: str):
    return _pub(_vid(video_id))


@router.get("/{video_id}/frame")
def first_frame(video_id: str):
    _vid(video_id)
    return FileResponse(config.data_dir() / "videos" / video_id / "frame.jpg", media_type="image/jpeg")


@router.get("/{video_id}/jobs")
def video_jobs(video_id: str):
    _vid(video_id)
    return db.query("SELECT id,status,progress,created,finished,error FROM jobs WHERE video_id=? ORDER BY created DESC",
                    (video_id,))


@router.post("/{video_id}/process")
def process(video_id: str):
    _vid(video_id)
    return {"job_id": jobs.submit(video_id)}


@router.delete("/{video_id}")
def delete_video(video_id: str):
    _vid(video_id)
    for j in db.query("SELECT id,status FROM jobs WHERE video_id=?", (video_id,)):
        if j["status"] in ("queued", "running"):
            raise HTTPException(409, "a job is still running for this video")
        jobs.delete_job(j["id"])
    db.execute("DELETE FROM configs WHERE video_id=?", (video_id,))
    db.execute("DELETE FROM videos WHERE id=?", (video_id,))
    shutil.rmtree(config.data_dir() / "videos" / video_id, ignore_errors=True)
    return {"deleted": video_id}
