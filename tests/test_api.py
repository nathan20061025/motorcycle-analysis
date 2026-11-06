import csv, io, time
import pytest
from fastapi.testclient import TestClient
from tests.helpers import FakeTracker, make_video

ZONE = {"id": "z", "polygon": [[0, 0], [320, 0], [320, 240], [0, 240]], "direction_deg": 0}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("app.services.jobs.make_tracker", lambda cfg: FakeTracker())
    from app.main import app
    with TestClient(app) as c:
        yield c


def wait(c, job_id, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] in ("done", "error"):
            return j
        time.sleep(0.2)
    raise AssertionError("timeout")


def test_full_flow(client, tmp_path):
    assert client.get("/api/health").json()["status"] == "ok"
    vid = client.post("/api/videos", files={"file": ("a.mp4", open(make_video(tmp_path / "a.mp4"), "rb"))}).json()
    assert vid["width"] == 320 and vid["fps"] == 10
    assert client.get("/api/videos").json()[0]["id"] == vid["id"]
    assert client.get(f"/api/videos/{vid['id']}/frame").headers["content-type"] == "image/jpeg"

    r = client.get(f"/api/videos/{vid['id']}/config").json()
    assert r["config"]["zones"] == [] and "ww_min_opposed_s" in r["defaults"]
    assert client.put(f"/api/videos/{vid['id']}/config", json={"zones": [{**ZONE, "polygon": [[0, 0]]}]}).status_code == 422
    assert client.put(f"/api/videos/{vid['id']}/config", json={"thresholds": {"nope": 1}}).status_code == 422
    assert client.put(f"/api/videos/{vid['id']}/config", json={"zones": [ZONE]}).status_code == 200
    assert client.get(f"/api/videos/{vid['id']}/config").json()["config"]["zones"][0]["id"] == "z"

    jid = client.post(f"/api/videos/{vid['id']}/process").json()["job_id"]
    j = wait(client, jid)
    assert j["status"] == "done", j["error"]
    assert j["progress"] == 1 and j["processing"]["fps"] > 0

    ev = client.get(f"/api/jobs/{jid}/events").json()
    assert len(ev) == 1 and ev[0]["type"] == "wrong_way"
    assert client.get(f"/api/jobs/{jid}/tracks").json()["tracks"][0]["id"] == 7
    assert client.get(f"/api/jobs/{jid}/evidence/{ev[0]['evidence'][0]}").status_code == 200
    assert client.get(f"/api/jobs/{jid}/evidence/..%2Fx").status_code == 404

    full = client.get(f"/api/jobs/{jid}/video")
    assert full.status_code == 200 and len(full.content) > 100
    part = client.get(f"/api/jobs/{jid}/video", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206 and len(part.content) == 100

    assert client.patch(f"/api/events/{ev[0]['event_id']}/review", json={"review": "confirmed"}).json()["review"] == "confirmed"
    assert client.patch("/api/events/nope/review", json={"review": "confirmed"}).status_code == 404
    assert client.patch(f"/api/events/{ev[0]['event_id']}/review", json={"review": "bad"}).status_code == 422

    js = client.get(f"/api/jobs/{jid}/export?format=json").json()
    assert set(js) == {"video", "config", "processing", "tracks", "events"}
    assert js["events"][0]["review"] == "confirmed" and js["events"][0]["evidence"][0].startswith(f"jobs/{jid}/evidence/")
    assert {"model", "tracker", "device", "fps", "duration_s", "version"} <= set(js["processing"])
    rows = list(csv.DictReader(io.StringIO(client.get(f"/api/jobs/{jid}/export?format=csv").text)))
    assert rows[0]["type"] == "wrong_way" and rows[0]["review"] == "confirmed" and ";" in rows[0]["evidence"]

    assert client.delete(f"/api/videos/{vid['id']}").status_code == 200
    assert client.get(f"/api/jobs/{jid}").status_code == 404
    assert client.get(f"/api/videos/{vid['id']}").status_code == 404


def test_errors_and_bad_upload(client, tmp_path):
    assert client.post("/api/videos", files={"file": ("x.mp4", b"not a video")}).status_code == 400
    assert client.post("/api/videos/nope/process").status_code == 404
    assert client.get("/api/jobs/nope").status_code == 404

    vid = client.post("/api/videos", files={"file": ("a.mp4", open(make_video(tmp_path / "a.mp4", n=5), "rb"))}).json()

    class Boom:
        def update(self, f):
            raise RuntimeError("model exploded")
    import app.services.jobs as js
    js.make_tracker = lambda cfg: Boom()
    j = wait(client, client.post(f"/api/videos/{vid['id']}/process").json()["job_id"])
    assert j["status"] == "error" and "model exploded" in j["error"]
