# Known limitations

- **Night / rain / glare:** pretrained COCO YOLO degrades sharply; missed and flickering detections break tracks and
  suppress events. No low-light handling.
- **Camera angle:** ground point = bbox bottom-center assumes a fairly elevated, oblique view. Near-overhead or very low
  views make the ground point unreliable.
- **Heavy occlusion / crowds:** long occlusions (> 2 s) are not bridged; identity swaps between overlapping bikes can
  still happen. Stitching is conservative, so fragments remain separate tracks (fewer wrong merges, more split tracks).
- **Small / distant bikes:** below roughly 20-30 px height, detection and heading estimates are noisy.
- **Riding vs walking is heuristic:** based on YOLO `person` boxes overlapping/beside the bike plus speed. Pillion
  riders, pedestrians next to a passing bike, and missed person detections cause `unknown` or wrong states.
- **Pixel-space bias without homography:** speeds/displacements are normalized by bbox height, so far bikes look slower
  and near bikes faster; thresholds are not metric. Supplying a 4-point homography fixes this only for a flat road.
- **No fine-tuning:** pretrained weights only (`motorcycle` also fires on bicycles/scooters sometimes). A hook exists
  (`TRAFFIC_MODEL`) for fine-tuned weights with COCO class ids.
- **Lane ambiguity:** tracks in overlapping zones, or mostly outside zones, are reported as insufficient evidence or
  ignored, never as violations. Zones are straight-arrow permitted directions; curved lanes need several zones.
- **Config quality:** results depend entirely on correctly drawn zones/arrows; there is no auto-calibration.
- **Validation status:** the logic is unit-tested on synthetic trajectories. It has not been measured on real CCTV
  footage in this repository (see `docs/results.md`).
