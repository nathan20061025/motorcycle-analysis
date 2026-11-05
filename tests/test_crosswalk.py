from app.core.config import Settings
from app.core.models import Crosswalk
from app.cv.rider_analysis import rider_state
from app.cv.crosswalk import detect
from app.cv.trajectory import analyze
from tests.helpers import line_track

CFG = Settings()
CW = Crosswalk(id="c1", polygon=[(400, 300), (600, 300), (600, 400), (400, 400)])


def run(t, persons=None):
    return detect(t, analyze(t), [CW], persons or {}, CFG)


def persons_for(t, dx=0, top=True):
    out = {}
    for f, b in zip(t.frames, t.boxes):
        cx = (b[0] + b[2]) / 2 + dx
        out[f] = [(cx - 8, b[1] - 30, cx + 8, b[3] - 15)] if top else [(cx - 8, b[1] - 30, cx + 8, b[3])]
    return out


def test_pass_through_flagged_riding():
    t = line_track(x0=200, y=350, vx=8, n=60)
    ev = run(t, persons_for(t))
    assert len(ev) == 1 and ev[0]["status"] == "suspected" and ev[0]["rider_state"] == "riding"
    assert 0 <= ev[0]["confidence"] <= 1


def test_pass_through_without_person_is_unknown_but_flagged_when_fast():
    ev = run(line_track(x0=200, y=350, vx=8, n=60))
    assert ev[0]["rider_state"] == "unknown" and ev[0]["status"] == "suspected"


def test_stopped_on_crosswalk_not_flagged():
    assert run(line_track(x0=500, y=350, vx=0, n=40, jitter=0.3)) == []


def test_bbox_only_overlap_not_flagged():
    # ground point (bottom) stays below the polygon (y=430) while the bbox top reaches into it
    assert run(line_track(x0=200, y=430, vx=8, n=60)) == []


def test_walking_pace_with_person_beside_not_flagged():
    t = line_track(x0=300, y=350, vx=4, n=60)   # 1 bbox-height/s
    assert run(t, persons_for(t, dx=22, top=False)) == []


def test_unclear_slow_rider_is_insufficient():
    ev = run(line_track(x0=300, y=350, vx=4, n=60))
    assert ev and ev[0]["status"] == "insufficient_evidence"


def test_enter_and_back_out_not_flagged():
    xs = [450 + 8 * k for k in range(8)] + [506 - 8 * k for k in range(8)]
    from tests.helpers import path_track
    t = path_track([200 + 8 * k for k in range(32)] + xs[:0] + [200 + 8 * 31 - 8 * k for k in range(32)], [350] * 64)
    assert run(t) == []


def test_rider_state_unknown_without_persons():
    t = line_track(x0=200, y=350, vx=8, n=20)
    a = analyze(t)
    assert rider_state(t, {}, a["speed"], 0, 19, CFG) == ("unknown", 0.0)
