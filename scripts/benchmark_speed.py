"""Processing speed (FPS) and per-stage timing on a real clip.

  python -m scripts.benchmark_speed VIDEO [--device cpu|cuda] [--model yolov8n.pt] [--imgsz 960] [--stride 1] [--label cpu]
Writes a 'speed-<label>' section to docs/results.md. Run once per device (e.g. --label cpu, --label gpu)."""
import argparse, os, platform, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core import config
from app.cv import pipeline
from scripts._md import upsert


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--device"); ap.add_argument("--model"); ap.add_argument("--imgsz", type=int)
    ap.add_argument("--stride", type=int); ap.add_argument("--label", default=None)
    ap.add_argument("--out", default="docs/results.md")
    a = ap.parse_args()
    cfg = config.load()
    for k in ("device", "model", "imgsz", "stride"):
        if getattr(a, k) is not None:
            setattr(cfg, k, getattr(a, k))
    label = a.label or cfg.device
    d = tempfile.mkdtemp()
    try:
        r = pipeline.run(a.video, d, cfg)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    p, n = r["processing"], r["frames_processed"]
    st = p["stage_s"]
    rows = "\n".join(f"| {k[:-2]} | {v:.2f} | {1000 * v / max(n, 1):.1f} |" for k, v in st.items())
    body = (f"### Speed ({label})\n`{os.path.basename(a.video)}` · {n} frames processed · model `{cfg.model}` · "
            f"imgsz {cfg.imgsz} · stride {cfg.stride} · device `{cfg.device}` · {platform.processor() or platform.machine()}\n\n"
            f"**End-to-end: {p['fps']} FPS ({p['duration_s']} s total)**\n\n"
            f"| stage | seconds | ms/frame |\n|---|---|---|\n{rows}")
    print(body)
    upsert(a.out, f"speed-{label}", body)


if __name__ == "__main__":
    main()
