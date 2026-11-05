from app.core.config import Settings
from app.cv.track_stitcher import stitch, interpolate_gaps, is_low_confidence
from app.cv.trajectory import Track

CFG = Settings()


def mk(id, f0, n, x0, y, vx=5.0, fps=10.0, h=40, w=20, vy=0.0):
    t = Track(id, fps=fps, raw_ids=[id])
    for k in range(n):
        x, yy = x0 + vx * k, y + vy * k
        t.add(f0 + k, (x - w / 2, yy - h, x + w / 2, yy), 0.9)
    return t


def test_merges_broken_track_and_interpolates_small_gap():
    a = mk(1, 0, 30, 100, 200)            # ends frame 29 at x=245
    b = mk(2, 40, 30, 245 + 5 * 11, 200)  # starts frame 40, on the constant-velocity path
    out, m = stitch([a, b], CFG)
    assert len(out) == 1 and m == {1: [1, 2]}
    t = out[0]
    assert t.frames == list(range(0, 70))   # 10-frame gap interpolated
    assert len(t.interpolated) == 10


def test_no_merge_when_overlapping_in_time():
    a = mk(1, 0, 30, 100, 200)
    b = mk(2, 20, 30, 260, 200)
    out, _ = stitch([a, b], CFG)
    assert len(out) == 2


def test_no_merge_when_far_apart_or_gap_too_long():
    a = mk(1, 0, 30, 100, 200)
    far = mk(2, 40, 30, 245 + 5 * 11, 600)          # same time window, 400px off path
    late = mk(3, 100, 30, 245 + 5 * 71, 200)         # 7 s later
    out, _ = stitch([a, far], CFG)
    assert len(out) == 2
    out, _ = stitch([a, late], CFG)
    assert len(out) == 2


def test_no_merge_opposite_heading_or_size():
    a = mk(1, 0, 30, 100, 200)
    back = mk(2, 40, 30, 300, 200, vx=-5.0)
    big = mk(3, 40, 30, 300, 200, h=120, w=60)
    assert len(stitch([a, back], CFG)[0]) == 2
    assert len(stitch([a, big], CFG)[0]) == 2


def test_hungarian_resolves_conflict():
    a1, a2 = mk(1, 0, 30, 100, 100), mk(2, 0, 30, 100, 300)
    b1, b2 = mk(3, 35, 30, 100 + 5 * 35, 300), mk(4, 35, 30, 100 + 5 * 35, 100)
    out, m = stitch([a1, a2, b1, b2], CFG)
    assert sorted(m.values()) == [[1, 4], [2, 3]]


def test_chain_merge():
    a, b, c = mk(1, 0, 20, 0, 200), mk(2, 25, 20, 125, 200), mk(3, 50, 20, 250, 200)
    out, m = stitch([a, b, c], CFG)
    assert m == {1: [1, 2, 3]}


def test_interpolation_only_small_gaps():
    t = Track(1, fps=10)
    for f in [0, 1, 2, 8, 9, 30]:   # gap of 5 filled, gap of 20 not
        t.add(f, (f, 0, f + 10, 20), 0.8)
    o = interpolate_gaps(t, 10)
    assert o.frames == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 30]


def test_edge_cases_and_low_confidence():
    assert stitch([], CFG) == ([], {})
    one = mk(1, 0, 1, 10, 10)
    out, _ = stitch([one], CFG)
    assert len(out) == 1 and is_low_confidence(out[0], CFG)
    assert not is_low_confidence(mk(2, 0, 30, 0, 0), CFG)
    many = [mk(i, 0, 5, i * 50, i * 7) for i in range(60)]   # crowded: must not crash
    stitch(many, CFG)
