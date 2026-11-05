"""Phase-1 pipeline/CLI: detect+track -> trajectory JSON + annotated video.
Usage: python -m app.cv.pipeline VIDEO OUT_DIR"""
import json, os, sys, time
from collections import defaultdict
import cv2
from app.core import config
from app.cv import render
from app.cv.trajectory import Track, analyze


def run(video, out_dir, cfg=None, progress=None, model=None):
    cfg = cfg or config.load()
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(3)), int(cap.get(4))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    if model is None:
        from app.cv.detector import load_model
        model = load_model(cfg.model)
    from app.cv.tracker import Tracker
    tr = Tracker(model, cfg)
    tmp = os.path.join(out_dir, "_raw.mp4")
    vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps / cfg.stride, (w, h))
    tracks, trails, frames_json = {}, defaultdict(list), []
    t0, i = time.time(), 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % cfg.stride == 0:
            dets = tr.update(frame)
            for d in dets:
                if d.cls != "motorcycle":
                    continue
                t = tracks.setdefault(d.track_id, Track(d.track_id, fps=fps, raw_ids=[d.track_id]))
                t.add(i, (d.x1, d.y1, d.x2, d.y2), d.conf)
                trails[d.track_id].append(d.ground)
            frames_json.append({"frame": i, "t": round(i / fps, 3), "dets": [
                {"id": d.track_id, "cls": d.cls, "box": [round(v, 1) for v in (d.x1, d.y1, d.x2, d.y2)],
                 "conf": round(d.conf, 3)} for d in dets]})
            vw.write(render.draw_dets(frame, dets, {k: v[-30:] for k, v in trails.items()}))
            if progress:
                progress(i / total)
        i += 1
    cap.release(); vw.release()
    render.to_h264(tmp, os.path.join(out_dir, "annotated.mp4")); os.remove(tmp)
    out = []
    for t in tracks.values():
        a = analyze(t, None, cfg.vel_window_s, cfg.smooth_window) if len(t.frames) > 1 else None
        out.append({"id": t.id, "frames": t.frames, "boxes": t.boxes, "confs": t.confs,
                    "speed": a["speed"].round(3).tolist() if a else [],
                    "heading": a["heading"].round(1).tolist() if a else []})
    json.dump({"fps": fps, "size": [w, h], "tracks": out}, open(os.path.join(out_dir, "tracks.json"), "w"))
    json.dump(frames_json, open(os.path.join(out_dir, "frames.json"), "w"))
    return {"frames": i, "elapsed_s": time.time() - t0, "tracks": len(out)}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(run(sys.argv[1], sys.argv[2]))
