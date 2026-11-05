"""3-5 evidence JPEGs per event: entry, mid, exit, peak (+ quarter points), with bbox, stable ID, full
trajectory with direction arrowheads, zone/crosswalk overlay and timestamp."""
import os
import cv2
import numpy as np
from app.cv.render import draw_traj, draw_zones, RED, LABEL


def pick_frames(event, track):
    s, e = event.start_frame, event.end_frame
    peak = event.metrics.get("peak_frame", (s + e) // 2)
    named = {"entry": s, "q1": s + (e - s) // 4, "mid": (s + e) // 2, "peak": peak, "q3": s + 3 * (e - s) // 4, "exit": e}
    seen, out = set(), []
    for name in ("entry", "mid", "exit", "peak", "q1", "q3"):
        f = min(track.frames, key=lambda x: abs(x - named[name]))   # snap to an observed frame
        if f not in seen and len(out) < 5:
            seen.add(f); out.append((name, f))
    for f in (track.frames[0], track.frames[-1]):                    # very short events: pad to >= 3
        if len(out) < 3 and f not in seen:
            seen.add(f); out.append(("track", f))
    return out


def draw_evidence(img, event, track, vc, frame, fps):
    draw_zones(img, vc)
    g = track.ground_px()
    draw_traj(img, g, (0, 220, 0), 2, 10)
    sel = [i for i, f in enumerate(track.frames) if event.start_frame <= f <= event.end_frame]
    if len(sel) > 1:
        draw_traj(img, g[sel], RED, 3, 10)
    i = int(np.argmin([abs(f - frame) for f in track.frames]))
    x1, y1, x2, y2 = (int(v) for v in track.boxes[i])
    cv2.rectangle(img, (x1, y1), (x2, y2), RED, 3)
    cv2.putText(img, f"#{track.id}", (x1, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, RED, 2)
    cv2.putText(img, f"{LABEL[event.type]} ({event.status}) conf {event.confidence:.2f}", (8, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(img, f"t={frame / fps:.2f}s frame {frame}", (8, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    return img


def render_evidence(video, event, track, vc, out_dir):
    """Writes JPEGs under out_dir/evidence/. Returns list of file names (relative to evidence/)."""
    ev_dir = os.path.join(out_dir, "evidence")
    os.makedirs(ev_dir, exist_ok=True)
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or track.fps
    names = []
    for label, f in pick_frames(event, track):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, img = cap.read()
        if not ok:
            continue
        name = f"{event.event_id}_{label}.jpg"
        cv2.imwrite(os.path.join(ev_dir, name), draw_evidence(img, event, track, vc, f, fps))
        names.append(name)
    cap.release()
    return names
