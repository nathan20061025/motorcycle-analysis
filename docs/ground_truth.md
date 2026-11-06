# Ground-truth formats

## Events (`scripts/evaluate_events.py`)
CSV with header `video,type,start_s,end_s,track_hint`:

```
video,type,start_s,end_s,track_hint
clip1.mp4,wrong_way,12.4,16.0,bike in left lane
clip1.mp4,crosswalk_riding,31.0,33.2,red helmet
```
- `video`: file name as uploaded (matched by basename).
- `type`: `wrong_way` or `crosswalk_riding`.
- `start_s`/`end_s`: seconds. A prediction matches if same type and interval IoU >= 0.3 (or both ends within `--tol`).
- `track_hint`: free text for the human annotator; not used in scoring.
- Annotate only true violations. Predictions of status `insufficient_evidence` are not counted unless `--include-insufficient`.

## Tracks (`scripts/evaluate_tracking.py --gt`, optional)
CSV with header `frame,id,x1,y1,x2,y2` (one row per motorcycle per frame, pixel coords, frame index at source fps).
