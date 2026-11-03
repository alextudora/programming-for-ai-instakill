from fastapi import APIRouter, HTTPException
from typing import List

from app.domain.models import Post
from app.db.database import get_connection

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.post("/", response_model=Post, status_code=201)
def create_post(post: Post):
    """Create a new post[cite: 1]."""
    with get_connection() as conn:
        # Validate if user exists before creating a post
        user_check = conn.execute("SELECT id FROM user WHERE id = ?", (post.user_id,)).fetchone()
        if not user_check:
            raise HTTPException(status_code=404, detail="User not found")

        cursor = conn.execute(
            "INSERT INTO post (user_id, content) VALUES (?, ?) RETURNING id, user_id, content, created_at",
            (post.user_id, post.content)
        )
        row = cursor.fetchone()
        conn.commit()
        return dict(row)


@router.get("/", response_model=List[Post])
def list_posts():
    """List all posts[cite: 1]."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT id, user_id, content, created_at FROM post")
        return [dict(row) for row in cursor.fetchall()]


@router.get("/{post_id}", response_model=Post)
def get_post(post_id: int):
    """Retrieve a specific post by ID[cite: 1]."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT id, user_id, content, created_at FROM post WHERE id = ?", (post_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
        return dict(row)


@router.patch("/{post_id}", response_model=Post)
def update_post(post_id: int, content: str):
    """Update a post's content[cite: 1]."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE post SET content = ? WHERE id = ? RETURNING id, user_id, content, created_at",
            (content, post_id)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
        conn.commit()
        return dict(row)


@router.delete("/{post_id}", status_code=204)
def delete_post(post_id: int):
    """Delete a post by ID[cite: 1]."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM post WHERE id = ?", (post_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Post not found")
        conn.commit()