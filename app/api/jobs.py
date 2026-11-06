import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from app.core import db
from app.services import jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _job(job_id):
    j = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not j:
        raise HTTPException(404, "job not found")
    return j


def _done(job_id):
    j = _job(job_id)
    if j["status"] != "done":
        raise HTTPException(409, f"job is {j['status']}")
    return j


@router.get("/{job_id}")
def status(job_id: str):
    j = _job(job_id)
    j["processing"] = json.loads(j["processing"]) if j["processing"] else None
    return j


@router.get("/{job_id}/events")
def events(job_id: str):
    _job(job_id)
    return jobs.get_events(job_id)


@router.get("/{job_id}/tracks")
def tracks(job_id: str):
    _done(job_id)
    return FileResponse(jobs.job_dir(job_id) / "tracks.json", media_type="application/json")


@router.get("/{job_id}/frames")
def frames(job_id: str):
    _done(job_id)
    return FileResponse(jobs.job_dir(job_id) / "frames.json", media_type="application/json")


@router.get("/{job_id}/video")
def video(job_id: str):
    _done(job_id)   # FileResponse serves HTTP Range requests (206) for seeking
    return FileResponse(jobs.job_dir(job_id) / "annotated.mp4", media_type="video/mp4")


@router.get("/{job_id}/evidence/{name}")
def evidence(job_id: str, name: str):
    p = jobs.job_dir(job_id) / "evidence" / Path(name).name
    if not p.is_file():
        raise HTTPException(404, "evidence not found")
    return FileResponse(p, media_type="image/jpeg")


@router.get("/{job_id}/export")
def export(job_id: str, format: str = Query("json", pattern="^(json|csv)$")):
    _done(job_id)
    if format == "csv":
        return Response(jobs.export_csv(job_id), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="events_{job_id}.csv"'})
    return JSONResponse(jobs.export_json(job_id),
                        headers={"Content-Disposition": f'attachment; filename="export_{job_id}.json"'})


@router.delete("/{job_id}")
def delete(job_id: str):
    j = _job(job_id)
    if j["status"] in ("queued", "running"):
        raise HTTPException(409, "job is still running")
    jobs.delete_job(job_id)
    return {"deleted": job_id}
