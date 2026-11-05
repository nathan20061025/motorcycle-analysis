import json
import cv2
import numpy as np
from app.core.config import Settings
from app.core.models import Event, VideoConfig, Zone, Crosswalk
from app.cv.event_verifier import finalize, build_events
from app.cv.evidence import render_evidence
from app.cv.render import render_annotated
from tests.helpers import line_track

CFG = Settings()


def cand(t, s, e, status="suspected", conf=0.8):
    return {"track": t, "type": "wrong_way", "status": status, "zone_id": "z", "start_frame": s, "end_frame": e,
            "confidence": conf, "reasons": ["r"], "metrics": {"peak_frame": s}}


def test_dedupe_merges_close_and_keeps_far():
    t = line_track()
    ev = finalize([cand(t, 0, 10), cand(t, 20, 30), cand(t, 100, 110)], CFG)   # fps10: gap 1s merge, 7 s keep
    assert [(e.start_frame, e.end_frame) for e in ev] == [(0, 30), (100, 110)]


def test_confidence_range_and_status_merge():
    t = line_track()
    ev = finalize([cand(t, 0, 10, "insufficient_evidence", 0.4), cand(t, 12, 20, "suspected", 0.9)], CFG)
    assert len(ev) == 1 and ev[0].status == "suspected" and 0 <= ev[0].confidence <= 1


def test_event_schema_roundtrip_json():
    t = line_track()
    e = finalize([cand(t, 0, 10)], CFG)[0]
    d = json.loads(json.dumps(e.model_dump()))
    assert Event.model_validate(d) == e
    assert {"event_id", "type", "status", "track_id", "raw_track_ids", "start_frame", "end_frame", "start_time_s",
            "end_time_s", "confidence", "reasons", "rider_state", "metrics", "evidence", "review"} <= d.keys()
    assert d["review"] == "pending"


def test_build_events_skips_short_tracks_and_handles_empty():
    vc = VideoConfig(zones=[Zone(id="z", polygon=[(0, 0), (1000, 0), (1000, 600), (0, 600)], direction_deg=0)])
    assert build_events([], CFG, vc, {}) == []
    assert build_events([line_track(n=3)], CFG, vc, {}) == []
    ev = build_events([line_track(n=40)], CFG, vc, {})
    assert len(ev) == 1 and ev[0].type == "wrong_way"


def test_evidence_and_annotated_video(tmp_path):
    t = line_track(n=40, x0=600, y=200, vx=-8)
    vc = VideoConfig(zones=[Zone(id="z", polygon=[(0, 0), (700, 0), (700, 400), (0, 400)], direction_deg=0)],
                     crosswalks=[Crosswalk(id="c", polygon=[(100, 100), (200, 100), (200, 200), (100, 200)])])
    ev = build_events([t], CFG, vc, {})
    assert ev
    vid = str(tmp_path / "v.mp4")
    w = cv2.VideoWriter(vid, cv2.VideoWriter_fourcc(*"mp4v"), 10, (704, 416))
    for _ in range(40):
        w.write(np.zeros((416, 704, 3), np.uint8))
    w.release()
    names = render_evidence(vid, ev[0], t, vc, str(tmp_path))
    assert 3 <= len(names) <= 5
    assert all(cv2.imread(str(tmp_path / "evidence" / n)) is not None for n in names)
    frames = [{"frame": f, "dets": [{"id": 1, "cls": "motorcycle", "box": list(b)}]} for f, b in zip(t.frames, t.boxes)]
    out = str(tmp_path / "a.mp4")
    render_annotated(vid, out, frames, {1: 1}, [t], ev, vc)
    assert cv2.VideoCapture(out).read()[0]
