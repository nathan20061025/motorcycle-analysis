"""Gap interpolation + merging of fragmented tracks (ID switches / long occlusions).

Merge ended track A into later track B only if ALL hold:
  - B starts strictly after A ends (never overlap in time) and gap <= merge_max_gap_s
  - B's first ground point is within merge_dist_scale * bbox height of A's constant-velocity prediction
  - similar bbox height (ratio <= merge_size_ratio) and, if both are moving, similar heading
Conflicts (several A's wanting one B, or vice versa) are resolved by Hungarian assignment on a cost matrix.
Tracks are merged in rounds until stable, so chains A->B->C collapse into one.
"""
import numpy as np
from scipy.optimize import linear_sum_assignment
from app.cv.geometry import angle_of, angle_diff
from app.cv.trajectory import Track

INF = 1e6
K = 10  # samples used to estimate end/start motion


def _h(t, sl):
    b = np.asarray(t.boxes, float)[sl]
    return float(max(np.median(b[:, 3] - b[:, 1]), 1.0))


def _end_state(t):
    g, f = t.ground_px(), np.asarray(t.frames, float)
    j = max(0, len(f) - K)
    v = (g[-1] - g[j]) / (f[-1] - f[j]) if f[-1] > f[j] else np.zeros(2)
    return g[-1], v, _h(t, slice(j, None))


def _start_state(t):
    g, f = t.ground_px(), np.asarray(t.frames, float)
    j = min(len(f) - 1, K - 1)
    v = (g[j] - g[0]) / (f[j] - f[0]) if f[j] > f[0] else np.zeros(2)
    return g[0], v, _h(t, slice(0, K))


def pair_cost(A, B, cfg):
    """Merge cost of A->B in ~[0,4], or INF if any hard condition fails."""
    if not A.frames or not B.frames:
        return INF
    gap = B.frames[0] - A.frames[-1]
    gap_s = gap / A.fps
    if gap <= 0 or gap_s > cfg.merge_max_gap_s:
        return INF
    pa, va, ha = _end_state(A)
    pb, vb, hb = _start_state(B)
    thr = cfg.merge_dist_scale * max(ha, hb)
    dist = float(np.linalg.norm(pa + va * gap - pb))
    if dist > thr:
        return INF
    ratio = max(ha / hb, hb / ha)
    if ratio > cfg.merge_size_ratio:
        return INF
    hd = 0.0
    moving = lambda v, h: np.linalg.norm(v) * A.fps / h > cfg.stationary_speed
    if moving(va, ha) and moving(vb, hb):
        hd = angle_diff(angle_of(*va), angle_of(*vb))
        if hd > cfg.merge_heading_deg:
            return INF
    return (dist / thr + np.log(ratio) / np.log(cfg.merge_size_ratio)
            + hd / cfg.merge_heading_deg + gap_s / cfg.merge_max_gap_s)


def _concat(chain):
    m = Track(chain[0].id, chain[0].cls, fps=chain[0].fps)
    for t in chain:
        m.frames += t.frames; m.boxes += t.boxes; m.confs += t.confs
        m.raw_ids += t.raw_ids or [t.id]
        m.interpolated |= t.interpolated
    m.raw_ids = sorted(set(m.raw_ids))
    return m


def interpolate_gaps(t, max_gap=10, stride=1):
    """Linearly fill runs of <= max_gap missing (processed) frames inside a track. Returns new Track."""
    out = Track(t.id, t.cls, fps=t.fps, raw_ids=list(t.raw_ids), interpolated=set(t.interpolated))
    for i, f in enumerate(t.frames):
        if i:
            f0, f1 = t.frames[i - 1], f
            miss = (f1 - f0) // stride - 1
            if 1 <= miss <= max_gap:
                b0, b1 = np.asarray(t.boxes[i - 1]), np.asarray(t.boxes[i])
                c = 0.5 * (t.confs[i - 1] + t.confs[i]) * 0.5
                for k in range(1, miss + 1):
                    a = k / (miss + 1)
                    out.add(f0 + k * stride, tuple(b0 + a * (b1 - b0)), c)
                    out.interpolated.add(f0 + k * stride)
        out.add(f, t.boxes[i], t.confs[i])
    return out


def stitch(tracks, cfg):
    """Returns (merged_tracks, {stable_id: [raw_ids]}). Input tracks are not modified."""
    cur = [t for t in tracks if t.frames]
    for t in cur:
        if not t.raw_ids:
            t.raw_ids = [t.id]
    while len(cur) > 1:
        n = len(cur)
        M = np.full((n, n), INF)
        for i in range(n):
            for j in range(n):
                if i != j:
                    M[i, j] = pair_cost(cur[i], cur[j], cfg)
        rows, cols = linear_sum_assignment(M)
        nxt = {r: c for r, c in zip(rows, cols) if M[r, c] < INF}
        if not nxt:
            break
        has_pred = set(nxt.values())
        used, merged = set(), []
        for i in range(n):
            if i in has_pred:
                continue
            chain, k = [cur[i]], i
            used.add(i)
            while k in nxt:
                k = nxt[k]; used.add(k); chain.append(cur[k])
            merged.append(_concat(chain) if len(chain) > 1 else cur[i])
        cur = merged + [cur[i] for i in range(n) if i not in used]
    cur = [interpolate_gaps(t, cfg.max_interp_gap, cfg.stride) for t in cur]
    for t in cur:
        t.raw_ids = sorted(set(t.raw_ids))
    return cur, {t.id: t.raw_ids for t in cur}


def is_low_confidence(t, cfg) -> bool:
    """Tracks shorter than min_track_s: shown in UI as low-confidence, excluded from event analysis."""
    return t.duration_s < cfg.min_track_s
