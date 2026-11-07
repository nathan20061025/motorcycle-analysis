import bisect, os, shutil, subprocess
import cv2
import numpy as np

COL = {"motorcycle": (0, 200, 255), "person": (200, 200, 0)}
RED, GREEN, GREY = (0, 0, 255), (0, 220, 0), (150, 150, 150)
LABEL = {"wrong_way": "WRONG WAY", "crosswalk_riding": "CROSSWALK"}


def draw_dets(img, dets, trails=None):
    """Phase-1 raw drawing (used while tracking, before events exist)."""
    for d in dets:
        c = COL.get(d.cls, (255, 255, 255))
        cv2.rectangle(img, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)), c, 2)
        if d.cls == "motorcycle":
            cv2.putText(img, f"#{d.track_id}", (int(d.x1), max(int(d.y1) - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
    for pts in (trails or {}).values():
        for a, b in zip(pts, pts[1:]):
            cv2.line(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), GREEN, 2)
    return img


def _ffmpeg():
    """System ffmpeg, else the binary bundled by imageio-ffmpeg, else None."""
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def to_h264(src, dst):
    """Re-encode to browser-playable H.264 via ffmpeg; plain copy if no ffmpeg is available."""
    ff = _ffmpeg()
    if ff:
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", src, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", dst], check=True)
    else:
        shutil.copy(src, dst)


def _ip(p):
    return int(p[0]), int(p[1])


def draw_zones(img, vc, alpha=0.25):
    ov = img.copy()
    for z in vc.zones:
        if z.polygon:
            cv2.fillPoly(ov, [np.int32(z.polygon)], (255, 120, 0))
    for c in vc.crosswalks:
        cv2.fillPoly(ov, [np.int32(c.polygon)], (0, 220, 255))
    cv2.addWeighted(ov, alpha, img, 1 - alpha, 0, img)
    for z in vc.zones:
        if not z.polygon:
            continue
        cv2.polylines(img, [np.int32(z.polygon)], True, (255, 120, 0), 2)
        c = np.mean(z.polygon, 0)
        d = np.array([np.cos(np.radians(z.direction_deg)), np.sin(np.radians(z.direction_deg))]) * 50
        cv2.arrowedLine(img, _ip(c - d / 2), _ip(c + d / 2), (255, 120, 0), 3, tipLength=0.3)
        if z.two_way:
            cv2.arrowedLine(img, _ip(c + d / 2), _ip(c - d / 2), (255, 120, 0), 3, tipLength=0.3)
    for c in vc.crosswalks:
        cv2.polylines(img, [np.int32(c.polygon)], True, (0, 220, 255), 2)
    return img


def draw_traj(img, pts, color=GREEN, thick=2, arrow_every=12):
    """Polyline with direction arrowheads."""
    pts = [_ip(p) for p in pts]
    for a, b in zip(pts, pts[1:]):
        cv2.line(img, a, b, color, thick)
    for i in range(arrow_every, len(pts), arrow_every):
        cv2.arrowedLine(img, pts[max(i - 3, 0)], pts[i], color, thick, tipLength=0.9)
    return img


def render_annotated(video, out_path, frames, stable_of, tracks, events, vc, stride=1, progress=None):
    """Second pass over the source video: boxes, stable IDs, trailing trajectories, zones, event highlight.
    frames: list of {frame, dets:[{id,cls,box}]} from tracking; stable_of: raw id -> stable id."""
    by_frame = {f["frame"]: f for f in frames}
    ground = {t.id: (t.frames, t.ground_px()) for t in tracks}
    low = {t.id for t in tracks if t.duration_s < 0.5}
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w, h = int(cap.get(3)), int(cap.get(4))
    tmp = out_path + ".raw.mp4"
    vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps / stride, (w, h))
    total, i = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1, 0
    while True:
        ok, img = cap.read()
        if not ok:
            break
        if i in by_frame:
            draw_zones(img, vc)
            active = {e.track_id: e for e in events if e.start_frame <= i <= e.end_frame}
            for d in by_frame[i]["dets"]:
                x1, y1, x2, y2 = (int(v) for v in d["box"])
                if d["cls"] != "motorcycle":
                    cv2.rectangle(img, (x1, y1), (x2, y2), COL["person"], 1)
                    continue
                sid = stable_of.get(d["id"], d["id"])
                ev = active.get(sid)
                col = RED if ev and ev.status == "suspected" else (0, 140, 255) if ev else GREY if sid in low else COL["motorcycle"]
                cv2.rectangle(img, (x1, y1), (x2, y2), col, 4 if ev else 2)
                txt = f"#{sid}" + (f" {LABEL[ev.type]}{'' if ev.status == 'suspected' else '?'}" if ev else "")
                cv2.putText(img, txt, (x1, max(y1 - 5, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
            for sid, (fr, g) in ground.items():
                k = bisect.bisect_right(fr, i)
                if k > 1 and fr[k - 1] >= i - 60:
                    draw_traj(img, g[max(0, k - 40):k], RED if sid in active else GREEN, 2, 15)
            cv2.putText(img, f"t={i / fps:.2f}s f={i}", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            vw.write(img)
            if progress:
                progress(i / total)
        i += 1
    cap.release(); vw.release()
    to_h264(tmp, out_path)
    os.remove(tmp)
