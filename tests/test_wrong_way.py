import numpy as np
from app.core.config import Settings
from app.core.models import Zone
from app.cv.trajectory import analyze
from app.cv.wrong_way import detect
from tests.helpers import line_track, path_track

CFG = Settings()
BIG = [(0, 0), (1000, 0), (1000, 600), (0, 600)]
ZONE = Zone(id="z1", polygon=BIG, direction_deg=0)   # permitted: rightwards


def run(t, zones=(ZONE,)):
    return detect(t, analyze(t), list(zones), CFG)


def test_clear_wrong_way_flagged():
    ev = run(line_track(vx=-8, n=40))
    assert len(ev) == 1 and ev[0]["status"] == "suspected"
    assert 0 <= ev[0]["confidence"] <= 1 and ev[0]["metrics"]["duration_s"] >= 1.5


def test_correct_direction_not_flagged():
    assert run(line_track(x0=100, vx=8)) == []


def test_legal_turn_not_flagged():
    th = np.linspace(0, np.pi, 40)          # U-turn: heading rotates gradually 0 -> 180 deg
    xs = 300 + np.cumsum(8 * np.cos(th)); ys = 300 + np.cumsum(8 * np.sin(th))
    assert run(path_track(xs, ys)) == []


def test_brief_deviation_not_flagged():
    xs = np.cumsum([8] * 20 + [-8] * 4 + [8] * 20) + 100
    assert run(path_track(xs, np.full(len(xs), 300.0))) == []


def test_stationary_not_flagged():
    assert run(line_track(vx=0, jitter=0.3)) == []


def test_borderline_is_insufficient_evidence():
    ev = run(line_track(vx=-8, n=12))       # ~1.2 s opposed
    assert len(ev) == 1 and ev[0]["status"] == "insufficient_evidence" and ev[0]["reasons"]


def test_overlapping_zones_ambiguous():
    z2 = Zone(id="z2", polygon=BIG, direction_deg=0)
    ev = run(line_track(vx=-8), [ZONE, z2])
    assert ev and all(e["status"] == "insufficient_evidence" for e in ev)


def test_mostly_outside_zone_and_two_way():
    small = Zone(id="s", polygon=[(0, 0), (100, 0), (100, 100), (0, 100)], direction_deg=0)
    assert run(line_track(vx=-8), [small]) == []
    assert run(line_track(vx=-8), [Zone(id="tw", polygon=BIG, direction_deg=0, two_way=True)]) == []


def test_default_direction_and_empty():
    t = line_track(vx=-8)
    assert detect(t, analyze(t), [], CFG, default_direction=0)[0]["status"] == "suspected"
    assert detect(t, analyze(t), [], CFG) == []
