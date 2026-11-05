"""Crosswalk-riding candidates. Bbox overlap is NOT enough: the ground point must be inside >= cw_min_frames,
the path must traverse the polygon (entry/exit on different edges, or displacement >= cw_min_extent_frac of its
extent), speed must exceed the stopped threshold, and a walking rider (person beside bike, walking pace) is excluded."""
import numpy as np
from app.cv.geometry import edge_of, point_in_polygon, polygon_extent
from app.cv.rider_analysis import rider_state
from app.cv.trajectory import runs


def detect(track, a, crosswalks, persons, cfg):
    t, px, sp = a["t"], a["px"], a["speed"]
    n = len(t)
    if n < 2:
        return []
    q = track.quality()
    out = []
    for cw in crosswalks:
        inside = np.array([point_in_polygon(p, cw.polygon) for p in px])
        ext = polygon_extent(cw.polygon)
        for s, e in runs(inside, t, 0.3):
            cnt = int(inside[s:e + 1].sum())
            through = float(np.linalg.norm(px[e] - px[s]))
            inner = s > 0 and e < n - 1
            edge_pass = inner and edge_of(px[s], cw.polygon) != edge_of(px[e], cw.polygon)
            if not (edge_pass or through >= cfg.cw_min_extent_frac * ext):
                continue                       # entered and left / loitered: not a passage
            mean_sp = float(sp[s:e + 1].mean())
            if mean_sp <= cfg.stationary_speed or cnt < max(2, cfg.cw_min_frames // 2):
                continue                       # stopped or glancing
            state, rconf = rider_state(track, persons, sp, s, e, cfg)
            if state == "walking":
                continue                       # walking the bike across: not a violation
            reasons = []
            ok = True
            if cnt < cfg.cw_min_frames:
                ok = False; reasons.append(f"only {cnt} frames inside crosswalk (< {cfg.cw_min_frames})")
            if q < cfg.min_quality:
                ok = False; reasons.append(f"low track quality {q:.2f}")
            if state == "unknown" and mean_sp <= cfg.cw_walk_speed:
                ok = False; reasons.append("walking pace and rider not visible: riding vs walking unclear")
            if ok:
                reasons.append(f"ground point traversed crosswalk ({cnt} frames, speed {mean_sp:.2f}/s)")
                if state == "unknown":
                    reasons.append("rider state unknown (no clear person association)")
            conf = (0.3 * min(1.0, cnt / (2 * cfg.cw_min_frames)) + 0.3 * min(1.0, through / max(ext, 1))
                    + 0.2 * q + 0.2 * (rconf if state == "riding" else 0.4))
            conf = float(np.clip(conf if ok else min(conf, 0.5), 0, 1))
            pk = s + int(np.argmax(sp[s:e + 1]))
            out.append({
                "type": "crosswalk_riding", "status": "suspected" if ok else "insufficient_evidence",
                "zone_id": None, "crosswalk_id": cw.id, "rider_state": state, "rider_confidence": rconf,
                "start_frame": int(track.frames[s]), "end_frame": int(track.frames[e]),
                "confidence": conf, "reasons": reasons,
                "metrics": {"duration_s": round(float(t[e] - t[s]), 2), "frames_inside": cnt,
                            "displacement": round(through / max(ext, 1), 3), "speed": round(mean_sp, 3),
                            "track_quality": round(q, 3), "peak_frame": int(track.frames[pk])},
            })
    return out
