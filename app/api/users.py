import sqlite3
from fastapi import APIRouter, HTTPException
from typing import List

from app.domain.models import User
from app.db.database import get_connection

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/", response_model=User, status_code=201)
def create_user(user: User):
    """Create a new user[cite: 1]."""
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO user (username) VALUES (?) RETURNING id, username, created_at",
                (user.username,)
            )
            row = cursor.fetchone()
            conn.commit()
            return dict(row)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Username already exists")

@router.get("/", response_model=List[User])
def list_users():
    """List all users[cite: 1]."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT id, username, created_at FROM user")
        return [dict(row) for row in cursor.fetchall()]

@router.get("/{user_id}", response_model=User)
def get_user(user_id: int):
    """Retrieve a specific user by ID[cite: 1]."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT id, username, created_at FROM user WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return dict(row)

@router.patch("/{user_id}", response_model=User)
def update_user(user_id: int, username: str):
    """Update a user's username[cite: 1]."""
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "UPDATE user SET username = ? WHERE id = ? RETURNING id, username, created_at",
                (username, user_id)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            conn.commit()
            return dict(row)
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Username already exists")

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int):
    """Delete a user by ID[cite: 1]."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM user WHERE id = ?", (user_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        conn.commit()