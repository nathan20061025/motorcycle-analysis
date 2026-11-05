"""Riding vs walking heuristic from YOLO `person` boxes near a motorcycle track.
on top + moving      -> riding     beside + walking pace -> walking     otherwise -> unknown"""


def _inter(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(w, 0) * max(h, 0)


def classify(bike, person):
    """'on' | 'beside' | None for one person box relative to one bike box."""
    bx1, by1, bx2, by2 = bike
    bw, bh = max(bx2 - bx1, 1), max(by2 - by1, 1)
    px1, py1, px2, py2 = person
    pw, ph = max(px2 - px1, 1), max(py2 - py1, 1)
    pcx, bcx = (px1 + px2) / 2, (bx1 + bx2) / 2
    frac = _inter(bike, person) / (pw * ph)
    if frac >= 0.3 and bx1 - 0.1 * bw <= pcx <= bx2 + 0.1 * bw and py1 <= by1 + 0.25 * bh:
        return "on"
    if frac < 0.2 and abs(pcx - bcx) <= bw / 2 + pw / 2 + bw and ph >= 0.6 * bh and abs(py2 - by2) <= 0.4 * bh:
        return "beside"
    return None


def rider_state(track, persons, speed, s, e, cfg):
    """persons: {frame: [boxes]}; speed: per-sample series; s..e sample range. Returns (state, confidence)."""
    votes = {"riding": 0, "walking": 0}
    n = e - s + 1
    for i in range(s, e + 1):
        kinds = {classify(track.boxes[i], p) for p in persons.get(track.frames[i], [])}
        if "on" in kinds and speed[i] > cfg.stationary_speed:
            votes["riding"] += 1
        elif "beside" in kinds and cfg.stationary_speed < speed[i] <= cfg.cw_walk_speed:
            votes["walking"] += 1
    voted = sum(votes.values())
    if voted < 3 or voted < 0.3 * n:
        return "unknown", 0.0
    state = max(votes, key=votes.get)
    share = votes[state] / voted
    if share < 0.6:
        return "unknown", 0.0
    return state, round(share * min(1.0, voted / (0.5 * n)), 3)
