import sqlite3
from fastapi import APIRouter, HTTPException
from typing import List

from app.domain.models import Follow
from app.db.database import get_connection

router = APIRouter(prefix="/follows", tags=["Follows"])

@router.post("/", response_model=Follow, status_code=201)
def follow_user(follow: Follow):
    """Create a new follow relationship."""
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO follow (follower_id, followee_id) VALUES (?, ?) RETURNING follower_id, followee_id, created_at",
                (follow.follower_id, follow.followee_id)
            )
            row = cursor.fetchone()
            conn.commit()
            return dict(row)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Follow relationship already exists or user/followee not found")

@router.delete("/", status_code=204)
def unfollow_user(follower_id: int, followee_id: int):
    """Delete a follow relationship."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM follow WHERE follower_id = ? AND followee_id = ?",
            (follower_id, followee_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Follow relationship not found")
        conn.commit()

@router.get("/{user_id}/followers", response_model=List[Follow])
def get_followers(user_id: int):
    """List followers of a specific user[cite: 1]."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT follower_id, followee_id, created_at FROM follow WHERE followee_id = ?",
            (user_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

@router.get("/{user_id}/following", response_model=List[Follow])
def get_following(user_id: int):
    """List users that a specific user is following[cite: 1]."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT follower_id, followee_id, created_at FROM follow WHERE follower_id = ?",
            (user_id,)
        )
        return [dict(row) for row in cursor.fetchall()]