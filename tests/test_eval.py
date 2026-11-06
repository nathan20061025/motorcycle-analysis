from scripts.evaluate_events import match, prf, iou
from scripts.evaluate_tracking import switches_and_fragments


def ev(t, s, e):
    return {"type": t, "start_s": s, "end_s": e}


def test_event_matching():
    gts = [ev("wrong_way", 1, 5), ev("crosswalk_riding", 10, 12)]
    preds = [ev("wrong_way", 1.5, 5.5), ev("wrong_way", 20, 22), ev("crosswalk_riding", 30, 31)]
    tp, fp, fn = match(preds, gts)
    assert (tp, fp, fn) == (1, 2, 1)
    p, r, f1 = prf(tp, fp, fn)
    assert abs(p - 1 / 3) < 1e-9 and r == 0.5 and 0 < f1 < 1
    assert match([ev("wrong_way", 1, 2)], [ev("wrong_way", 1.4, 2.6)], 0.9, tol=0.7) == (1, 0, 0)   # tolerance match
    assert match([ev("wrong_way", 1, 5)], [ev("crosswalk_riding", 1, 5)]) == (0, 1, 1)               # type must match
    assert abs(iou((0, 2), (1, 3)) - 1 / 3) < 1e-9


def test_id_switches_and_fragments():
    b = [0, 0, 10, 10]
    gt = {f: {"g": b} for f in range(6)}
    pred = {0: {"a": b}, 1: {"a": b}, 2: {"b": b}, 3: {"b": b}, 5: {"b": b}}   # switch a->b at 2, gap at 4
    assert switches_and_fragments(gt, pred) == (1, 1, 1)
    assert switches_and_fragments({}, {}) == (0, 0, 0)
