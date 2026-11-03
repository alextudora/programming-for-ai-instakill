import sqlite3
from fastapi import APIRouter, HTTPException
from typing import List

from app.domain.models import Like
from app.db.database import get_connection

router = APIRouter(prefix="/likes", tags=["Likes"])

@router.post("/", response_model=Like, status_code=201)
def like_post(like: Like):
    """Create a new like[cite: 1]."""
    with get_connection() as conn:
        try:
            # Escape the "like" table name as it is a reserved SQL keyword[cite: 6]
            cursor = conn.execute(
                "INSERT INTO \"like\" (user_id, post_id) VALUES (?, ?) RETURNING user_id, post_id, created_at",
                (like.user_id, like.post_id)
            )
            row = cursor.fetchone()
            conn.commit()
            return dict(row)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Like already exists or user/post not found")

@router.delete("/", status_code=204)
def unlike_post(user_id: int, post_id: int):
    """Delete a like[cite: 1]."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM \"like\" WHERE user_id = ? AND post_id = ?",
            (user_id, post_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Like not found")
        conn.commit()