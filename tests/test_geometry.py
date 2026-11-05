import numpy as np
from app.cv.geometry import point_in_polygon, angle_diff, angle_of, homography, project, edge_of
from app.cv.trajectory import Track, analyze

SQ = [(0, 0), (10, 0), (10, 10), (0, 10)]


def test_pip():
    assert point_in_polygon((5, 5), SQ)
    assert not point_in_polygon((15, 5), SQ)
    assert not point_in_polygon((-1, -1), SQ)


def test_angle_diff():
    assert angle_diff(10, 350) == 20
    assert angle_diff(0, 180) == 180
    assert angle_diff(90, 90) == 0


def test_angle_of():
    assert angle_of(1, 0) == 0 and angle_of(0, 1) == 90 and angle_of(-1, 0) == 180


def test_homography():
    src = [(100, 100), (300, 120), (320, 300), (80, 280)]
    p = project(homography(src), src)
    assert np.allclose(p, [(0, 0), (100, 0), (100, 100), (0, 100)], atol=1e-3)


def test_edge_of():
    assert edge_of((5, -1), SQ) == 0
    assert edge_of((11, 5), SQ) == 1


def test_trajectory_heading_rightward():
    t = Track(1, fps=10)
    for f in range(30):
        t.add(f, (10 * f, 100, 10 * f + 20, 140), 0.9)
    a = analyze(t)
    assert abs(a["heading"][-1]) < 1 or abs(a["heading"][-1] - 360) < 1
    assert a["speed"][-1] > 0
