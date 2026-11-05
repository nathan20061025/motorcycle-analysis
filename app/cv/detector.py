"""YOLO wrapper. COCO ids: person=0, motorcycle=3.
Fine-tuned weights hook: set TRAFFIC_MODEL=/path/best.pt (keep class ids, or edit CLASSES)."""

CLASSES = {0: "person", 3: "motorcycle"}


def load_model(weights: str):
    from ultralytics import YOLO
    return YOLO(weights)
