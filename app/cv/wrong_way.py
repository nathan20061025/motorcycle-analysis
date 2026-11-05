"""Wrong-way candidates from whole trajectories (never single frames).

Flag (suspected) only if, inside one permitted-direction zone: heading is opposed (> 180-tolerance) continuously
>= ww_min_opposed_s AND net displacement against the permitted direction >= ww_min_disp AND track quality OK.
Not flagged: turns (heading rotated > ww_turn_deg), brief deviations (< ww_borderline_s), stationary bikes,
tracks mostly outside the zone, two-way zones. Borderline -> insufficient_evidence with reasons."""
import numpy as np
from app.core.models import Zone
from app.cv.geometry import angle_diff, angle_of, point_in_polygon, project
from app.cv.trajectory import runs


def _contains(z, p):
    return True if not z.polygon else point_in_polygon(p, z.polygon)


def zone_direction(z, H=None):
    """Permitted heading in the analysis space (ground plane if H given)."""
    if H is None:
        return z.direction_deg
    c = np.mean(z.polygon, 0) if z.polygon else np.zeros(2)
    u = np.array([np.cos(np.radians(z.direction_deg)), np.sin(np.radians(z.direction_deg))])
    p = project(H, [c, c + 20 * u])
    return angle_of(*(p[1] - p[0]))


def detect(track, a, zones, cfg, H=None, default_direction=None):
    zones = list(zones)
    if not zones and default_direction is not None:
        zones = [Zone(id="default", polygon=[], direction_deg=default_direction, tolerance_deg=cfg.tolerance_deg)]
    t = a["t"]
    n = len(t)
    if n < 2 or not zones:
        return []
    px, head, sp, xy = a["px"], a["heading"], a["speed"], a["xy"]
    member = np.array([[_contains(z, p) for z in zones] for p in px])
    nz = member.sum(1)
    moving = sp > cfg.stationary_speed
    dt = float(np.median(np.diff(t)))
    q = track.quality()
    vis = 1 - len(track.interpolated) / max(len(track.frames), 1)
    out = []
    for zi, z in enumerate(zones):
        inz = member[:, zi]
        if z.two_way or inz.mean() < cfg.ww_min_in_zone or not (inz & moving).any():
            continue
        pdir = zone_direction(z, H)
        u = np.array([np.cos(np.radians(pdir)), np.sin(np.radians(pdir))])
        diff = np.array([angle_diff(h, pdir) for h in head])
        opp = inz & moving & (diff > 180 - z.tolerance_deg)
        first = int(np.flatnonzero(inz & moving)[0])
        for s, e in runs(opp, t, 0.3):
            dur = float(t[e] - t[s] + dt)
            if dur < cfg.ww_borderline_s:
                continue
            seg = slice(s, e + 1)
            rotation = angle_diff(head[s], head[first])
            spread = float(np.degrees(np.ptp(np.unwrap(np.radians(head[seg])))))
            if rotation > cfg.ww_turn_deg or spread > cfg.ww_turn_deg:
                continue  # gradual heading change = a turn, not wrong-way
            against = float(-np.dot(xy[e] - xy[s], u))
            frac = float(opp.sum() / max((inz & moving).sum(), 1))
            reasons, ok = [], True
            if dur < cfg.ww_min_opposed_s:
                ok = False; reasons.append(f"opposed only {dur:.1f}s (< {cfg.ww_min_opposed_s}s)")
            if against < cfg.ww_min_disp:
                ok = False; reasons.append(f"net displacement against direction {against:.2f} < {cfg.ww_min_disp}")
            if q < cfg.min_quality:
                ok = False; reasons.append(f"low track quality {q:.2f}")
            if (nz[seg] > 1).mean() > 0.5:
                ok = False; reasons.append("path inside overlapping zones (lane ambiguity)")
            if track.duration_s < cfg.ww_min_opposed_s:
                ok = False; reasons.append(f"very short track ({track.duration_s:.1f}s)")
            if ok:
                reasons.append(f"heading opposed to permitted direction for {dur:.1f}s, "
                               f"moved {against:.2f} against it")
            conf = (0.35 * frac + 0.25 * min(1.0, against / (2 * cfg.ww_min_disp)) + 0.25 * q + 0.15 * vis)
            conf = float(np.clip(conf if ok else min(conf, 0.5), 0, 1))
            pk = s + int(np.argmax(diff[seg]))
            out.append({
                "type": "wrong_way", "status": "suspected" if ok else "insufficient_evidence",
                "zone_id": z.id, "crosswalk_id": None, "rider_state": None,
                "start_frame": int(track.frames[s]), "end_frame": int(track.frames[e]),
                "confidence": conf, "reasons": reasons,
                "metrics": {"angles": {"permitted_deg": round(float(pdir), 1),
                                       "mean_heading_deg": round(float(np.degrees(np.angle(np.mean(np.exp(1j * np.radians(head[seg])))))) % 360, 1),
                                       "mean_diff_deg": round(float(diff[seg].mean()), 1)},
                            "duration_s": round(dur, 2), "displacement": round(against, 3),
                            "speed": round(float(sp[seg].mean()), 3), "fraction_opposed": round(frac, 3),
                            "track_quality": round(q, 3), "peak_frame": int(track.frames[pk])},
            })
    return out
