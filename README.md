# Motorcycle Detection, Tracking & Unsafe-Movement Analysis

Standalone web app that analyzes traffic-intersection CCTV video: detects and tracks motorcycles (pretrained YOLO +
ByteTrack), repairs broken tracks, and flags **suspected wrong-way travel** and **riding through pedestrian
crosswalks** from trajectories over time (never single frames). Every event carries timestamps, the stable and raw
track IDs, a confidence, human-readable reasons, evidence frames with trajectories, and a review state.
Unclear cases are reported as `insufficient_evidence` instead of being forced into a classification.

> **Status:** logic is covered by unit/integration tests on synthetic data. It has **not** been measured on real
> footage and the Docker image has **not** been built in the authoring environment (see [Results](#results) and
> [docs/checklist.md](docs/checklist.md)).

## Architecture

```
 Browser (static HTML + vanilla JS + canvas)
   upload · config canvas · playback overlay · events · evidence review · export
        │  REST (/api/...)
 FastAPI (app/main.py, app/api/*)            SQLite + files in /data
        │                                      videos/<id>/  jobs/<id>/{annotated.mp4,clean.mp4,
 Job runner (app/services/jobs.py)             tracks.json,frames.json,events.json,evidence/}
   one heavy job at a time, others queue
        │
 Pipeline (app/cv/pipeline.py)
   decode ─▶ YOLO detect + ByteTrack (detector.py, tracker.py)   motorcycle + person
          ─▶ track_stitcher.py   interpolate gaps <=10 frames, Hungarian ID merging
          ─▶ trajectory.py / geometry.py   smoothing, velocity, heading, homography
          ─▶ wrong_way.py · crosswalk.py (+ rider_analysis.py)   candidates
          ─▶ event_verifier.py   dedupe, confidence, insufficient-evidence
          ─▶ evidence.py · render.py   JPEGs + annotated H.264 MP4
```

## Quick start

```bash
docker compose up --build        # then open http://localhost:8080
```
CPU by default; weights (`yolov8s.pt`) are downloaded at image build time, runtime is offline. State persists in the
`traffic-data` volume (`/data`). For a faster CPU demo build with `--build-arg MODEL=yolov8n.pt` (or edit `compose.yaml`).

### Local development (no Docker)
```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt                  # Python 3.11 recommended; needs ffmpeg on PATH for H.264
DATA_DIR=./data TRAFFIC_MODEL=yolov8n.pt uvicorn app.main:app --port 8080
```

## GPU (optional)
Requires an NVIDIA GPU + driver and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/).
```bash
docker compose -f compose.yaml -f compose.gpu.yaml up --build
```
This builds with CUDA torch wheels (`TORCH_INDEX`, default cu121), reserves the GPU and sets `TRAFFIC_DEVICE=cuda`.
*The GPU path has not been tested.*

## Using the UI
1. **Upload** a video (progress bar); pick it in the list.
2. **Configure** on the first frame: tool *Crosswalk* (click corners, *Finish polygon*); tool *Direction zone* (corners,
   *Finish*, then click arrow start and end = permitted direction); adjust tolerance (default 60°) / two-way in the side
   panel; optional *Homography* (click 4 ground corners TL,TR,BR,BL of a rectangle and enter its real size);
   optional default direction; thresholds (blank = default, hover for tooltips). *Select/edit* lets you drag vertices;
   *Undo* and *Delete selected* are available. **Save config**.
3. **Save & process**: live progress, ETA and FPS; errors are shown explicitly.
4. **Results**: annotated playback (boxes, IDs, trajectories, zones with toggles; frame stepping; seek). Tick
   *Burned-in annotated video* to view the server-rendered MP4 instead of the canvas overlay.
5. **Events**: filter by type/status/review/confidence; click to seek and highlight the track. The panel shows evidence
   frames (click to enlarge), reasons, metrics, rider state, merged/raw IDs, and **Confirm / Reject** (saved to DB,
   included in export).
6. **Export JSON / CSV** from the Results tab.

## Tests and evaluation
```bash
pip install -r requirements.txt && pytest -q          # no video or GPU needed
python -m scripts.evaluate_events   --pred export.json --gt gt.csv        # P/R/F1 -> docs/results.md
python -m scripts.evaluate_tracking --tracks data/jobs/<id>/tracks.json --expected N [--gt gt_tracks.csv]
python -m scripts.benchmark_speed   clip.mp4 --device cpu --label cpu     # FPS + per-stage timing
```
Ground-truth CSV format: [docs/ground_truth.md](docs/ground_truth.md). Demo shot list: [docs/demo_script.md](docs/demo_script.md).

## Threshold reference
All live in `app/core/config.py`; override globally with env `TRAFFIC_<NAME>` (e.g. `TRAFFIC_CONF=0.3`) or per video in the UI.
Distances/speeds are in bbox-heights (pixel mode) or metres (with homography).

| Name | Default | Meaning |
|---|---|---|
| model / tracker / device | yolov8s.pt / bytetrack / cpu | weights path, `bytetrack`\|`botsort`, `cpu`\|`cuda` |
| conf | 0.25 | detection confidence |
| imgsz | 960 | YOLO inference size |
| stride | 1 | process every Nth frame (timestamps still use real frame index / FPS) |
| max_interp_gap | 10 | interpolate gaps up to this many frames |
| merge_max_gap_s | 2.0 | max time gap when merging track fragments |
| merge_dist_scale | 1.5 | allowed distance error vs prediction, in bbox heights |
| merge_size_ratio | 1.6 | max bbox-height ratio between fragments |
| merge_heading_deg | 60 | max heading difference between fragments |
| min_track_s | 0.5 | shorter tracks are "low-confidence", excluded from events |
| vel_window_s / smooth_window | 1.0 / 9 | velocity window; Savitzky-Golay window (frames) |
| tolerance_deg | 60 | default zone angular tolerance |
| ww_min_opposed_s | 1.5 | sustained opposed heading required |
| ww_borderline_s | 0.8 | opposed between this and the above → `insufficient_evidence` |
| ww_min_disp | 1.0 | net displacement against the permitted direction |
| ww_turn_deg | 45 | heading rotation above this = a turn (not flagged) |
| ww_min_in_zone | 0.6 | min fraction of the track inside the zone |
| stationary_speed | 0.3 | below this speed/s a bike is "stopped" |
| min_quality | 0.5 | min track quality (confidence × coverage) |
| cw_min_frames | 5 | frames the ground point must be inside the crosswalk |
| cw_min_extent_frac | 0.5 | displacement through the crosswalk / its extent (if not edge-to-edge) |
| cw_walk_speed | 1.5 | at/below this speed = walking pace |
| event_merge_s | 2.0 | merge events on the same track closer than this |

## Event logic in plain language
- **Position** is the bbox bottom-center (ground contact point), smoothed over time.
- **Wrong way**: inside a permitted-direction zone, the bike's heading must be opposed (more than 180° − tolerance
  away from the arrow) *continuously* for ≥ 1.5 s, and it must have actually moved against that direction by a minimum
  distance, with a decent track.
- **Turns** are not wrong-way: if the heading rotates gradually by > 45° the path is a turn.
- **Short deviations** (< 0.8 s opposed) are ignored; 0.8-1.5 s, tiny displacement, very short or low-quality tracks, or
  overlapping zones become `insufficient_evidence` with the reasons listed.
- **Stopped bikes** (speed below the stopped threshold) can never be wrong-way or crosswalk violations.
- **Tracks mostly outside zones / two-way zones** are not judged.
- **Crosswalk riding**: a bounding-box overlap is *not* enough. The ground point must be inside ≥ 5 frames, the path must
  pass through (enter and leave through different edges, or travel ≥ half the crosswalk extent), and speed must exceed
  the stopped threshold. A bike that stops, waits, or enters and backs out is not flagged.
- **Walking vs riding**: YOLO `person` boxes are associated to the bike. Person on top + normal speed → `riding`;
  person beside + walking pace → `walking` (not a violation); otherwise `unknown`. A slow bike with unclear rider is
  `insufficient_evidence`. This is a heuristic.
- **Broken tracks** are repaired: gaps ≤ 10 frames are interpolated; a track that ended is merged into a new one only if
  it starts within 2 s, near the predicted position, with similar size and heading, and never overlaps in time
  (Hungarian assignment resolves conflicts). `stable_id → raw IDs` is kept.
- **Dedupe**: one event per continuous violation; events on the same stable track and type within 2 s are merged.

## Export schema
`GET /api/jobs/{id}/export?format=json`
```json
{"video": {"id","filename","fps","width","height","frames","duration_s"},
 "config": {"zones","crosswalks","homography_points","ground_size","default_direction","thresholds"},
 "processing": {"model","tracker","device","fps","duration_s","version","stage_s"},
 "tracks": [{"id","raw_ids","low_confidence","quality","start_frame","end_frame"}],
 "events": [{"event_id","type","status","track_id","raw_track_ids","start_frame","end_frame","start_time_s",
             "end_time_s","confidence","reasons","rider_state","zone_id","crosswalk_id",
             "metrics":{"angles","duration_s","displacement","speed"},"evidence":["jobs/<job>/evidence/<file>.jpg"],
             "review":"pending|confirmed|rejected"}]}
```
CSV (`format=csv`): one row per event: `event_id,type,status,track_id,raw_track_ids(;),start_frame,end_frame,start_time_s,
end_time_s,confidence,reasons( | ),rider_state,review,evidence(;)`. Other API routes: see `app/api/`.

## Sample data
No clips are bundled. Use your own fixed-camera intersection footage (MP4/H.264 recommended, ≥ 720p, 10-30 fps, camera
elevated enough to see the road plane). Public sources: traffic-camera datasets such as UA-DETRAC or MIO-TCD, or your own
recordings (check licenses/privacy). Include some night/rain/crowded clips to document failure cases.

## Results
No numbers have been measured yet; see [docs/results.md](docs/results.md), which `scripts/` fill in from real clips.

| Metric | Value |
|---|---|
| Event precision / recall / F1 | _not run_ |
| ID switches / fragmentation | _not run_ |
| FPS CPU / GPU | _not run_ |

## Known limitations
Night/rain; camera angle; heavy occlusion; small distant bikes; heuristic walking-vs-riding detection; pixel-space bias
without homography; no fine-tuning (pretrained COCO only); lane ambiguity. Details: [docs/limitations.md](docs/limitations.md).

## Future work
Fine-tune on local motorcycle data; learned appearance re-ID for long occlusions; pose-based rider/walker classification;
automatic lane/zone calibration; night/rain augmentation; multi-camera support; richer review workflow.

## Fine-tuned weights hook
Mount weights and set `TRAFFIC_MODEL=/path/best.pt` (class ids person=0, motorcycle=3, or edit `app/cv/detector.py`).
