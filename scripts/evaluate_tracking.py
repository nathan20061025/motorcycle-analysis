"""Tracking quality from a job's tracks.json.
Always: track count (vs --expected), low-confidence tracks, tracks merged by the stitcher.
With --gt (CSV: frame,id,x1,y1,x2,y2): ID switches and fragmentation vs ground-truth tracks.

  python -m scripts.evaluate_tracking --tracks data/jobs/<id>/tracks.json [--expected N] [--gt gt_tracks.csv]
"""
import argparse, csv, datetime, json, os, sys
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts._md import upsert


def box_iou(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
    inter = max(w, 0) * max(h, 0)
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def switches_and_fragments(gt, pred, iou_thr=0.5):
    """gt: {frame: {gt_id: box}}, pred: {frame: {pred_id: box}}. Greedy per-frame IoU matching.
    ID switch = a GT track matched to a different predicted ID than its previous match.
    Fragmentation = times a GT track goes matched -> unmatched -> matched again."""
    seq = defaultdict(list)   # gt_id -> [pred_id or None per frame]
    for f in sorted(gt):
        cand = sorted(((box_iou(g, p), gi, pi) for gi, g in gt[f].items() for pi, p in pred.get(f, {}).items()), reverse=True)
        ug, up = {}, set()
        for s, gi, pi in cand:
            if s >= iou_thr and gi not in ug and pi not in up:
                ug[gi] = pi; up.add(pi)
        for gi in gt[f]:
            seq[gi].append(ug.get(gi))
    sw = fr = 0
    for s in seq.values():
        last, gap = None, False
        for m in s:
            if m is None:
                gap = last is not None
                continue
            if last is not None and m != last:
                sw += 1
            if gap:
                fr += 1
            last, gap = m, False
    return sw, fr, len(seq)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", required=True)
    ap.add_argument("--expected", type=int)
    ap.add_argument("--gt")
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--out", default="docs/results.md")
    a = ap.parse_args()
    tr = json.load(open(a.tracks))["tracks"]
    good = [t for t in tr if not t["low_confidence"]]
    lines = [f"### Tracking\nrun {datetime.date.today()} · `{a.tracks}`\n",
             f"- stable tracks: {len(tr)} ({len(good)} usable, {len(tr) - len(good)} low-confidence)",
             f"- tracks merged by stitcher: {sum(len(t['raw_ids']) > 1 for t in tr)} "
             f"(raw IDs absorbed: {sum(len(t['raw_ids']) - 1 for t in tr)})"]
    if a.expected is not None:
        lines.append(f"- expected tracks: {a.expected} · usable tracks: {len(good)} · difference: {len(good) - a.expected:+d}")
    if a.gt:
        gt, pred = defaultdict(dict), defaultdict(dict)
        for r in csv.DictReader(open(a.gt)):
            gt[int(r["frame"])][r["id"]] = [float(r[k]) for k in ("x1", "y1", "x2", "y2")]
        for t in tr:
            for f, b in zip(t["frames"], t["boxes"]):
                pred[f][t["id"]] = b
        sw, fr, n = switches_and_fragments(gt, pred, a.iou)
        lines.append(f"- vs ground truth ({n} GT tracks, IoU>={a.iou}): ID switches {sw}, fragmentations {fr}")
    body = "\n".join(lines)
    print(body)
    upsert(a.out, "tracking", body)


if __name__ == "__main__":
    main()
