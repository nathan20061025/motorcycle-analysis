# Traffic project (ASSIGNMENT.md is actually a PDF; extract with pypdf)
## Working rules
- Terse chat; no code echo; targeted edits; re-read before editing if unsure.
- No features beyond spec. Max 3 questions, only if blocked.
- Never claim it works without running it; state what could not be tested (e.g. GPU).
- Never invent accuracy numbers; results only from scripts on real clips, else marked placeholders.
- Phased: after each phase run `pytest -q --tb=short`, fix, commit, reply <=5 lines, STOP until "continue".
## Stack
Py3.11 in Docker (local dev: `.venv` on 3.13), FastAPI+Uvicorn, SQLite, Ultralytics YOLO (COCO motorcycle/person) + ByteTrack/BoT-SORT, no training, static vanilla-JS UI, state in /data, offline at runtime.
## Layout
app/{main.py, api/, core/{config,models,db}.py, cv/{detector,tracker,track_stitcher,trajectory,geometry,rider_analysis,wrong_way,crosswalk,event_verifier,evidence,render,pipeline}.py, services/jobs.py, static/}
scripts/{evaluate_events,evaluate_tracking,benchmark_speed}.py · tests/ · docs/{results,limitations,demo_script}.md · Dockerfile compose.yaml compose.gpu.yaml README.md
Ground point = bbox bottom-center; decisions on trajectories over time, never single frames.
