"""Full analysis pipeline for one video.
Stages: track (detect+track) -> stitch -> events -> evidence -> render.
CLI: python -m app.cv.pipeline VIDEO OUT_DIR  (no zones configured => tracking/trajectories only)"""
import json, os, sys, time
import cv2
from app import __version__
from app.core import config
from app.core.models import VideoConfig
from app.cv.event_verifier import build_events
from app.cv.evidence import render_evidence
from app.cv.geometry import homography
from app.cv.render import render_annotated
from app.cv.track_stitcher import stitch, is_low_confidence
from app.cv.trajectory import Track


def make_tracker(cfg):
    from app.cv.detector import load_model
    from app.cv.tracker import Tracker
    return Tracker(load_model(cfg.model), cfg)


def run(video, out_dir, cfg=None, vc=None, progress=None, tracker=None, id_prefix=""):
    cfg, vc = cfg or config.load(), vc or VideoConfig()
    os.makedirs(out_dir, exist_ok=True)
    prog = progress or (lambda *a: None)
    T = {}
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError("cannot open video")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    tracker = tracker or make_tracker(cfg)

    # 1. detect + track
    raws, persons, frames_json = {}, {}, []
    t_read = t_track = 0.0
    t0 = time.time()
    i = 0
    while True:
        a = time.time()
        ok, frame = cap.read()
        t_read += time.time() - a
        if not ok:
            break
        if i % cfg.stride == 0:
            a = time.time()
            dets = tracker.update(frame)
            t_track += time.time() - a
            for d in dets:
                if d.cls == "motorcycle":
                    raws.setdefault(d.track_id, Track(d.track_id, fps=fps, raw_ids=[d.track_id])).add(
                        i, (d.x1, d.y1, d.x2, d.y2), d.conf)
                elif d.cls == "person":
                    persons.setdefault(i, []).append((d.x1, d.y1, d.x2, d.y2))
            frames_json.append({"frame": i, "t": round(i / fps, 3), "dets": [
                {"id": d.track_id, "cls": d.cls, "box": [round(v, 1) for v in (d.x1, d.y1, d.x2, d.y2)],
                 "conf": round(d.conf, 3)} for d in dets]})
            el = time.time() - t0
            prog(min(0.7, 0.7 * i / total), "tracking", len(frames_json) / max(el, 1e-6))
        i += 1
    cap.release()
    n_proc = len(frames_json)
    T["read_s"], T["detect_track_s"] = t_read, t_track

    # 2. stitch
    a = time.time()
    prog(0.72, "stitching", None)
    stable, mapping = stitch(list(raws.values()), cfg)
    stable_of = {r: s for s, rs in mapping.items() for r in rs}
    for f in frames_json:
        for d in f["dets"]:
            d["sid"] = stable_of.get(d["id"], d["id"]) if d["cls"] == "motorcycle" else None
    T["stitch_s"] = time.time() - a

    # 3. events
    a = time.time()
    prog(0.75, "events", None)
    H = None
    if vc.homography_points and len(vc.homography_points) == 4:
        gw, gh = vc.ground_size
        H = homography(vc.homography_points, [(0, 0), (gw, 0), (gw, gh), (0, gh)])
    events = build_events(stable, cfg, vc, persons, H)
    by_id = {t.id: t for t in stable}
    for e in events:
        e.event_id = f"{id_prefix}{e.event_id}"
    T["events_s"] = time.time() - a

    # 4. evidence
    a = time.time()
    prog(0.8, "evidence", None)
    for e in events:
        e.evidence = render_evidence(video, e, by_id[e.track_id], vc, out_dir)
    T["evidence_s"] = time.time() - a

    # 5. render
    a = time.time()
    render_annotated(video, os.path.join(out_dir, "annotated.mp4"), frames_json, stable_of, stable, events, vc,
                     cfg.stride, lambda f: prog(0.85 + 0.15 * min(f, 1), "rendering", None))
    T["render_s"] = time.time() - a

    tracks_out = [{"id": t.id, "raw_ids": t.raw_ids, "low_confidence": is_low_confidence(t, cfg),
                   "quality": round(t.quality(), 3), "start_frame": t.frames[0], "end_frame": t.frames[-1],
                   "frames": t.frames, "boxes": [[round(v, 1) for v in b] for b in t.boxes]} for t in stable]
    json.dump({"fps": fps, "tracks": tracks_out}, open(os.path.join(out_dir, "tracks.json"), "w"))
    json.dump(frames_json, open(os.path.join(out_dir, "frames.json"), "w"))
    json.dump([e.model_dump() for e in events], open(os.path.join(out_dir, "events.json"), "w"), indent=1)
    total_s = time.time() - t0
    prog(1.0, "done", n_proc / max(total_s, 1e-6))
    return {"events": events, "n_tracks": len(stable), "frames_processed": n_proc,
            "processing": {"model": cfg.model, "tracker": cfg.tracker, "device": cfg.device,
                           "fps": round(n_proc / max(total_s, 1e-6), 2), "duration_s": round(total_s, 2),
                           "version": __version__, "stage_s": {k: round(v, 3) for k, v in T.items()}}}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    r = run(sys.argv[1], sys.argv[2])
    print(r["processing"], len(r["events"]), "events")
