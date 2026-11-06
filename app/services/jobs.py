"""Background job runner (one heavy job at a time; others queue) + export."""
import csv, io, json, shutil, time, traceback, uuid
from concurrent.futures import ThreadPoolExecutor
from app.core import config, db
from app.core.models import VideoConfig
from app.cv import pipeline

make_tracker = pipeline.make_tracker   # tests monkeypatch this
_pool = ThreadPoolExecutor(max_workers=1)


def mark_stale():
    db.execute("UPDATE jobs SET status='error', error='interrupted by restart' WHERE status IN ('queued','running')")


def load_config(video_id) -> VideoConfig:
    r = db.one("SELECT json FROM configs WHERE video_id=?", (video_id,))
    return VideoConfig.model_validate_json(r["json"]) if r else VideoConfig()


def submit(video_id) -> str:
    job_id = uuid.uuid4().hex[:12]
    db.execute("INSERT INTO jobs(id,video_id,status,progress,created) VALUES(?,?,?,?,?)",
               (job_id, video_id, "queued", 0.0, time.time()))
    _pool.submit(_run, job_id)
    return job_id


def _run(job_id):
    try:
        job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        video = db.one("SELECT * FROM videos WHERE id=?", (job["video_id"],))
        if not video:
            raise RuntimeError("video deleted")
        vc = load_config(video["id"])
        cfg = vc.settings(config.load())
        t0 = time.time()
        db.execute("UPDATE jobs SET status='running', started=?, stage='starting' WHERE id=?", (t0, job_id))
        last = [0.0]

        def cb(frac, stage, fps):
            now = time.time()
            if now - last[0] < 0.5 and frac < 1:
                return
            last[0] = now
            el = now - t0
            eta = el / frac * (1 - frac) if frac > 0.02 else None
            db.execute("UPDATE jobs SET progress=?, eta_s=?, fps=COALESCE(?,fps), stage=? WHERE id=?",
                       (frac, eta, fps, stage, job_id))

        res = pipeline.run(video["path"], str(config.data_dir() / "jobs" / job_id), cfg, vc, cb,
                           make_tracker(cfg), id_prefix=f"{job_id[:6]}-")
        for e in res["events"]:
            db.execute("INSERT INTO events VALUES(?,?,?,?,?,?)",
                       (e.event_id, job_id, e.type, e.status, e.review, e.model_dump_json()))
        db.execute("UPDATE jobs SET status='done', progress=1, eta_s=0, finished=?, processing=? WHERE id=?",
                   (time.time(), json.dumps(res["processing"]), job_id))
    except Exception as ex:   # surface a clear error state instead of dying silently
        traceback.print_exc()
        db.execute("UPDATE jobs SET status='error', error=?, finished=? WHERE id=?",
                   (f"{type(ex).__name__}: {ex}", time.time(), job_id))


def job_dir(job_id):
    return config.data_dir() / "jobs" / job_id


def delete_job(job_id):
    db.execute("DELETE FROM events WHERE job_id=?", (job_id,))
    db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    shutil.rmtree(job_dir(job_id), ignore_errors=True)


def get_events(job_id):
    out = []
    for r in db.query("SELECT json, review FROM events WHERE job_id=?", (job_id,)):
        e = json.loads(r["json"]); e["review"] = r["review"]
        out.append(e)
    return sorted(out, key=lambda e: (e["start_frame"], e["event_id"]))


def _ev_paths(job_id, events):
    for e in events:
        e["evidence"] = [f"jobs/{job_id}/evidence/{n}" for n in e["evidence"]]
    return events


def export_json(job_id):
    job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    video = db.one("SELECT * FROM videos WHERE id=?", (job["video_id"],)) or {}
    tr = json.load(open(job_dir(job_id) / "tracks.json"))["tracks"]
    return {"video": {k: video.get(k) for k in ("id", "filename", "fps", "width", "height", "frames", "duration_s")},
            "config": load_config(job["video_id"]).model_dump(),
            "processing": json.loads(job["processing"] or "{}"),
            "tracks": [{k: t[k] for k in ("id", "raw_ids", "low_confidence", "quality", "start_frame", "end_frame")}
                       for t in tr],
            "events": _ev_paths(job_id, get_events(job_id))}


CSV_COLS = ["event_id", "type", "status", "track_id", "raw_track_ids", "start_frame", "end_frame", "start_time_s",
            "end_time_s", "confidence", "reasons", "rider_state", "review", "evidence"]


def export_csv(job_id) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, CSV_COLS)
    w.writeheader()
    for e in _ev_paths(job_id, get_events(job_id)):
        row = {c: e.get(c) for c in CSV_COLS}
        row["raw_track_ids"] = ";".join(map(str, e["raw_track_ids"]))
        row["reasons"] = " | ".join(e["reasons"])
        row["evidence"] = ";".join(e["evidence"])
        w.writerow(row)
    return buf.getvalue()
