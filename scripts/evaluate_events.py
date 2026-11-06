"""Event precision/recall/F1 against a ground-truth CSV (video,type,start_s,end_s,track_hint).
A prediction matches a ground-truth event of the same type if interval IoU >= --iou OR both start and end are
within --tol seconds. Matching is one-to-one (best IoU first).

  python -m scripts.evaluate_events --pred export.json --gt gt.csv [--video clip.mp4] [--out docs/results.md]
"""
import argparse, csv, datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts._md import upsert


def iou(a, b):
    inter = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    union = (a[1] - a[0]) + (b[1] - b[0]) - inter
    return inter / union if union > 0 else 0.0


def match(preds, gts, iou_thr=0.3, tol=None):
    """preds/gts: dicts with type,start_s,end_s. Returns (tp, fp, fn)."""
    pairs = []
    for i, p in enumerate(preds):
        for j, g in enumerate(gts):
            if p["type"] != g["type"]:
                continue
            s = iou((p["start_s"], p["end_s"]), (g["start_s"], g["end_s"]))
            near = tol is not None and abs(p["start_s"] - g["start_s"]) <= tol and abs(p["end_s"] - g["end_s"]) <= tol
            if s >= iou_thr or near:
                pairs.append((s, i, j))
    pairs.sort(reverse=True)
    up, ug = set(), set()
    for _, i, j in pairs:
        if i not in up and j not in ug:
            up.add(i); ug.add(j)
    tp = len(up)
    return tp, len(preds) - tp, len(gts) - tp


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True, help="export JSON from the app")
    ap.add_argument("--gt", required=True)
    ap.add_argument("--video", help="video filename to filter GT rows (default: video in the export)")
    ap.add_argument("--iou", type=float, default=0.3)
    ap.add_argument("--tol", type=float, default=None, help="alternative match: start/end within this many seconds")
    ap.add_argument("--include-insufficient", action="store_true", help="count insufficient_evidence events as predictions")
    ap.add_argument("--out", default="docs/results.md")
    a = ap.parse_args()
    ex = json.load(open(a.pred, encoding="utf-8"))
    video = a.video or ex["video"]["filename"]
    gts = [{"type": r["type"], "start_s": float(r["start_s"]), "end_s": float(r["end_s"])}
           for r in csv.DictReader(open(a.gt, encoding="utf-8")) if os.path.basename(r["video"]) == os.path.basename(video)]
    preds = [{"type": e["type"], "start_s": e["start_time_s"], "end_s": e["end_time_s"]} for e in ex["events"]
             if a.include_insufficient or e["status"] == "suspected"]
    if not gts:
        sys.exit(f"no ground-truth rows for video '{video}' in {a.gt}")
    rows = []
    for t in (None, "wrong_way", "crosswalk_riding"):
        P = [p for p in preds if t is None or p["type"] == t]
        G = [g for g in gts if t is None or g["type"] == t]
        if t and not (P or G):
            continue
        tp, fp, fn = match(P, G, a.iou, a.tol)
        pr, rc, f1 = prf(tp, fp, fn)
        rows.append(f"| {t or 'all'} | {len(G)} | {tp} | {fp} | {fn} | {pr:.2f} | {rc:.2f} | {f1:.2f} |")
    body = (f"### Event accuracy\nVideo: `{video}` · run {datetime.date.today()} · IoU>={a.iou}"
            f"{'' if a.tol is None else f' or tol {a.tol}s'} · predictions: "
            f"{'suspected + insufficient' if a.include_insufficient else 'suspected only'}\n\n"
            "| type | GT | TP | FP | FN | precision | recall | F1 |\n|---|---|---|---|---|---|---|---|\n" + "\n".join(rows))
    print(body)
    upsert(a.out, "events", body)


if __name__ == "__main__":
    main()
