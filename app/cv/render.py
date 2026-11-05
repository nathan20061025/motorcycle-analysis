import shutil, subprocess
import cv2

COL = {"motorcycle": (0, 200, 255), "person": (200, 200, 0)}


def draw_dets(img, dets, trails=None):
    for d in dets:
        c = COL.get(d.cls, (255, 255, 255))
        cv2.rectangle(img, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)), c, 2)
        if d.cls == "motorcycle":
            cv2.putText(img, f"#{d.track_id}", (int(d.x1), max(int(d.y1) - 4, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)
    for pts in (trails or {}).values():
        for a, b in zip(pts, pts[1:]):
            cv2.line(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (0, 255, 0), 2)
    return img


def to_h264(src, dst):
    """Re-encode to browser-playable H.264 via ffmpeg; plain copy if ffmpeg is missing."""
    if shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", dst], check=True)
    else:
        shutil.copy(src, dst)
