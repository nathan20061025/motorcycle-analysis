import json
from app.core.config import Settings
from app.core.models import VideoConfig, Zone
from app.cv import pipeline
from tests.helpers import FakeTracker, make_video

ZONE = Zone(id="z", polygon=[(0, 0), (320, 0), (320, 240), (0, 240)], direction_deg=0)


def test_pipeline_end_to_end_with_mocked_detector(tmp_path):
    vid = make_video(tmp_path / "v.mp4")
    out = tmp_path / "out"
    calls = []
    res = pipeline.run(vid, str(out), Settings(), VideoConfig(zones=[ZONE]),
                       lambda f, s, fps: calls.append(s), FakeTracker(), "t-")
    assert len(res["events"]) == 1
    e = res["events"][0]
    assert e.type == "wrong_way" and e.status == "suspected" and e.event_id.startswith("t-")
    assert 3 <= len(e.evidence) <= 5
    for f in ("annotated.mp4", "tracks.json", "frames.json", "events.json"):
        assert (out / f).stat().st_size > 0
    assert (out / "evidence" / e.evidence[0]).is_file()
    frames = json.load(open(out / "frames.json"))
    assert frames[0]["dets"][0]["sid"] == 7
    assert {"tracking", "stitching", "events", "evidence", "rendering", "done"} <= set(calls)
    assert res["processing"]["fps"] > 0


def test_pipeline_no_detections_and_no_config(tmp_path):
    class Empty:
        def update(self, frame):
            return []
    res = pipeline.run(make_video(tmp_path / "v.mp4", n=5), str(tmp_path / "o"), Settings(), None, None, Empty())
    assert res["events"] == [] and res["n_tracks"] == 0
