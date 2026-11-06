import sqlite3
from contextlib import closing
from app.core.config import data_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos(id TEXT PRIMARY KEY, filename TEXT, path TEXT, fps REAL, width INT, height INT,
  frames INT, duration_s REAL, created REAL);
CREATE TABLE IF NOT EXISTS configs(video_id TEXT PRIMARY KEY, json TEXT);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, video_id TEXT, status TEXT, progress REAL DEFAULT 0, eta_s REAL,
  fps REAL, stage TEXT, error TEXT, created REAL, started REAL, finished REAL, processing TEXT);
CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, job_id TEXT, type TEXT, status TEXT, review TEXT, json TEXT);
"""


def _c():
    p = data_dir() / "traffic.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p, timeout=30)
    c.row_factory = sqlite3.Row
    return c


def init():
    with closing(_c()) as c:
        c.executescript(SCHEMA)
        c.commit()


def query(sql, args=()):
    with closing(_c()) as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def one(sql, args=()):
    r = query(sql, args)
    return r[0] if r else None


def execute(sql, args=()):
    with closing(_c()) as c:
        c.execute(sql, args)
        c.commit()
