import json
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core import db

router = APIRouter(prefix="/api/events", tags=["events"])


class ReviewIn(BaseModel):
    review: Literal["pending", "confirmed", "rejected"]


@router.patch("/{event_id}/review")
def review(event_id: str, body: ReviewIn):
    r = db.one("SELECT json FROM events WHERE event_id=?", (event_id,))
    if not r:
        raise HTTPException(404, "event not found")
    e = json.loads(r["json"]); e["review"] = body.review
    db.execute("UPDATE events SET review=?, json=? WHERE event_id=?", (body.review, json.dumps(e), event_id))
    return e
