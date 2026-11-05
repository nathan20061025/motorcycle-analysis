import math
import numpy as np
import cv2


def point_in_polygon(pt, poly) -> bool:
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def angle_of(dx, dy) -> float:
    """Heading in degrees in [0,360), image coords (y down)."""
    return math.degrees(math.atan2(dy, dx)) % 360


def angle_diff(a, b) -> float:
    """Smallest absolute difference in degrees, [0,180]."""
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def polygon_extent(poly) -> float:
    p = np.asarray(poly, float)
    return float(np.hypot(*(p.max(0) - p.min(0))))


def _seg_dist(p, a, b) -> float:
    p, a, b = (np.asarray(v, float) for v in (p, a, b))
    ab = b - a
    t = 0.0 if not ab.any() else float(np.clip(np.dot(p - a, ab) / np.dot(ab, ab), 0, 1))
    return float(np.linalg.norm(p - (a + t * ab)))


def edge_of(pt, poly) -> int:
    """Index of polygon edge nearest to pt."""
    ds = [_seg_dist(pt, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
    return int(np.argmin(ds))


def homography(src4, dst4=None):
    """3x3 matrix mapping 4 image points to a ground plane (default 100x100 square)."""
    dst4 = dst4 or [(0, 0), (100, 0), (100, 100), (0, 100)]
    return cv2.getPerspectiveTransform(np.float32(src4), np.float32(dst4))


def project(H, pts):
    p = np.asarray(pts, np.float32).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(p, np.asarray(H, np.float64)).reshape(-1, 2)
