"""Turn detector candidates into verified, deduplicated Events.
Dedupe: candidates on the same stable track and type whose gap is <= event_merge_s become one event.
Insufficient evidence is kept as its own status instead of being forced into suspected/not."""
from collections import defaultdict
from app.core.models import Event
from app.cv import crosswalk, wrong_way
from app.cv.track_stitcher import is_low_confidence
from app.cv.trajectory import analyze


def _merge(group):
    best = max(group, key=lambda c: (c["status"] == "suspected", c["confidence"]))
    sus = [c for c in group if c["status"] == "suspected"]
    m = dict(best)
    m["start_frame"] = min(c["start_frame"] for c in group)
    m["end_frame"] = max(c["end_frame"] for c in group)
    m["status"] = "suspected" if sus else "insufficient_evidence"
    m["confidence"] = max(c["confidence"] for c in (sus or group))
    m["reasons"] = list(dict.fromkeys(r for c in group for r in c["reasons"]))
    m["metrics"] = dict(best["metrics"])
    if len(group) > 1:
        m["metrics"]["merged_events"] = len(group)
    return m


def finalize(cands, cfg):
    """cands: dicts with 'track' (stable Track) + detector fields. Returns list[Event]."""
    groups = defaultdict(list)
    for c in cands:
        groups[(c["track"].id, c["type"])].append(c)
    merged = []
    for (_, _), g in groups.items():
        g.sort(key=lambda c: c["start_frame"])
        fps = g[0]["track"].fps
        cur = [g[0]]
        for c in g[1:]:
            if (c["start_frame"] - max(x["end_frame"] for x in cur)) / fps <= cfg.event_merge_s:
                cur.append(c)
            else:
                merged.append(_merge(cur)); cur = [c]
        merged.append(_merge(cur))
    merged.sort(key=lambda c: (c["start_frame"], c["type"]))
    events = []
    for i, c in enumerate(merged, 1):
        tr, fps = c["track"], c["track"].fps
        events.append(Event(
            event_id=f"E{i:04d}", type=c["type"], status=c["status"], track_id=tr.id,
            raw_track_ids=tr.raw_ids or [tr.id], start_frame=c["start_frame"], end_frame=c["end_frame"],
            start_time_s=round(c["start_frame"] / fps, 3), end_time_s=round(c["end_frame"] / fps, 3),
            confidence=min(1.0, max(0.0, c["confidence"])), reasons=c["reasons"], rider_state=c.get("rider_state"),
            rider_confidence=c.get("rider_confidence"), zone_id=c.get("zone_id"),
            crosswalk_id=c.get("crosswalk_id"), metrics=c["metrics"]))
    return events


def build_events(tracks, cfg, vc, persons, H=None):
    """tracks: stitched stable Tracks. Tracks < min_track_s are excluded from event analysis."""
    cands = []
    for t in tracks:
        if is_low_confidence(t, cfg) or len(t.frames) < 2:
            continue
        a = analyze(t, H, cfg.vel_window_s, cfg.smooth_window)
        found = wrong_way.detect(t, a, vc.zones, cfg, H, vc.default_direction)
        found += crosswalk.detect(t, a, vc.crosswalks, persons, cfg)
        for c in found:
            c["track"] = t
            cands.append(c)
    return finalize(cands, cfg)
