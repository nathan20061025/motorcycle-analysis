# ASSIGNMENT.md deliverable checklist

Legend: ✅ implemented + tested here · 🟡 implemented, partially/indirectly tested · ❌ not verified in this environment

## Problems
| # | Item | Files | Evidence / status |
|---|---|---|---|
| 1 | Detection + tracking, occlusion/ID changes | `cv/detector.py`, `tracker.py`, `track_stitcher.py` | 🟡 Stitcher ✅ (8 synthetic tests). YOLO/ByteTrack wrapper **never run** (ultralytics/weights not installed locally); tested only via a mocked detector. |
| 2 | Trajectory + permitted direction (perspective, lanes, turns) | `trajectory.py`, `geometry.py`, `models.py` | ✅ synthetic tests (homography round-trip, overlapping zones, turns). Not validated on real perspective. |
| 3 | Wrong-way | `wrong_way.py` | ✅ clear / turn / brief / stationary / borderline / ambiguous tests. |
| 4 | Crosswalk riding, riding vs walking | `crosswalk.py`, `rider_analysis.py` | ✅ pass-through / stopped / bbox-only / walking / back-out tests; rider heuristic only on synthetic boxes. |
| 5 | Event verification, dedupe, insufficient evidence | `event_verifier.py` | ✅ dedupe, confidence range, schema round-trip. |
| 6 | Robustness + explanation | `evidence.py`, `render.py`, `pipeline.py` | 🟡 evidence JPEGs + annotated MP4 generated from synthetic video; empty/short/60-track inputs don't crash. Real crowded scenes untested. |

## Deliverables
| # | Deliverable | Files | Status |
|---|---|---|---|
| 1 | Working AI application | `app/` | 🟡 Pipeline + API tested with mocked detector; **real YOLO inference not run**. |
| 2 | Functional web UI | `app/static/` | 🟡 Verified in headless Edge on seeded data: lists, playback overlay, event list, evidence review/confirm, crosswalk drawing + save, no JS errors. **Not exercised:** vertex dragging, zone arrow/tolerance, homography clicks, undo, upload progress, live job progress, frame-step, export buttons. |
| 3 | Dockerfile + compose, UI at :8080, GPU docs | `Dockerfile`, `compose.yaml`, `compose.gpu.yaml`, README | ❌ **UNVERIFIED — Docker is not installed on the authoring machine; image never built, `docker compose up --build` never run, pinned requirements never installed on Python 3.11, torch/cu121 pins unchecked, GPU untested.** |
| 4 | JSON/CSV export | `services/jobs.py`, `api/jobs.py` | ✅ API test checks schema, review status, evidence paths, CSV columns. |
| 5 | Git repo, README, tests, explanation, limitations | repo, `README.md`, `tests/`, `docs/limitations.md` | ✅ 42 pytest tests (see final run). |
| 6 | Demo + results (accuracy, speed, failed cases) | `docs/demo_script.md`, `scripts/*`, `docs/results.md` | 🟡 Shot list + scripts + metric unit tests done. **No real clips were run: no accuracy, tracking, or speed numbers exist (placeholders marked NOT RUN). The video itself is not recorded.** |

## Other untested items
- H.264 re-encode via ffmpeg (not installed locally; code falls back to a plain copy).
- BoT-SORT tracker option (selectable, never run). `stride > 1` end to end.
- Thresholds are untuned defaults.
