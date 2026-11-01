from datetime import datetime, timezone
from typing import List, Dict, Any
from app.domain.models import Post
from app.domain.ranking import FeedSignals, rank_feed
from app.db.database import get_connection


class PostService:
    """
    Application service that coordinates business logic for Posts.
    Currently, it handles the boundary logic without directly persisting to SQLite or handling HTTP.
    """
    # Tuned weights discovered in Lab 4 for the ranking algorithm
    FEED_WEIGHTS = {
        "freshness": 1.5,
        "affinity": 1.1,
        "popularity": 2.5
    }
    def create_post(self, user_id: int, content: str) -> Post:
        """
        Public operation to create a new post.
        Validates business rules and returns a populated domain model.
        """
        # Business validations
        if not content or not content.strip():
            raise ValueError("Post content cannot be empty or just whitespace.")

        if len(content) > 500:
            raise ValueError("Post content exceeds the maximum allowed length of 500 characters.")

        if user_id <= 0:
            raise ValueError("Invalid user ID.")

        # Instantiate the domain model (id is None initially, as DB assignment is simulated/future)
        new_post = Post(
            user_id=user_id,
            content=content.strip(),
            created_at=datetime.now(timezone.utc)
        )

        # In future weeks, a call to a repository would happen here:
        # self.post_repository.save(new_post)

        return new_post

    def get_feed(self, user_id: int, limit: int = 20, strategy: str = "for_you") -> List[Dict[str, Any]]:
        """
        Generates a feed of posts for the given user, avoiding their own posts and already liked posts.
        Orchestrates DB reads and delegates the pure ranking math to the domain function.
        """
        # Fix the present moment once per request
        now = datetime.now(timezone.utc)

        with get_connection() as conn:
            # 1. Validate user existence (to return 404 later if missing)
            user_row = conn.execute("SELECT id FROM user WHERE id = ?", (user_id,)).fetchone()
            if not user_row:
                raise ValueError(f"User {user_id} not found")

            # 2. Fetch candidates: Exclude user's own posts and posts they already liked
            query_candidates = """
                               SELECT id, user_id, content, created_at
                               FROM post
                               WHERE user_id != ? AND id NOT IN (
                    SELECT post_id FROM "like" WHERE user_id = ?
                ) \
                               """
            candidates_rows = conn.execute(query_candidates, (user_id, user_id)).fetchall()

            candidates = []
            for row in candidates_rows:
                # SQLite returns strings for timestamps. Convert them to timezone-aware UTC datetimes.
                dt_str = row["created_at"].replace("Z", "").replace("T", " ")
                dt_obj = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)

                candidates.append(Post(
                    id=row["id"],
                    user_id=row["user_id"],
                    content=row["content"],
                    created_at=dt_obj
                ))

            # 3. Handle chronological baseline strategy
            if strategy == "chronological":
                candidates.sort(key=lambda p: (-p.created_at.timestamp(), p.id))

                results = []
                for p in candidates[:limit]:
                    results.append({
                        "post_id": p.id,
                        "user_id": p.user_id,
                        "content": p.content,
                        "created_at": p.created_at.isoformat().replace("+00:00", "Z")
                    })
                return results

            # 4. Handle for_you strategy (AI-driven ranking)
            elif strategy == "for_you":
                # Fetch followed authors for the Affinity signal
                follows_rows = conn.execute("SELECT followee_id FROM follow WHERE follower_id = ?",
                                            (user_id,)).fetchall()
                followed_authors = {r["followee_id"] for r in follows_rows}

                # Fetch likes count per post for the Popularity signal
                likes_rows = conn.execute("SELECT post_id, COUNT(*) as cnt FROM \"like\" GROUP BY post_id").fetchall()
                post_likes = {r["post_id"]: r["cnt"] for r in likes_rows}
                max_likes = max(post_likes.values()) if post_likes else 0

                # Assemble signals state (like build_signals in the notebook)
                signals = FeedSignals(
                    followed_authors=followed_authors,
                    post_likes=post_likes,
                    max_likes=max_likes
                )

                # Execute pure ranking function
                ranked_pairs = rank_feed(candidates, signals, now, self.FEED_WEIGHTS, limit)

                # Format results according to the API contract
                results = []
                for score, p in ranked_pairs:
                    results.append({
                        "post_id": p.id,
                        "user_id": p.user_id,
                        "content": p.content,
                        "created_at": p.created_at.isoformat().replace("+00:00", "Z"),
                        "score": score
                    })
                return results

            else:
                # Triggers a 422 Unprocessable Entity in the API layer
                raise ValueError(f"Unknown strategy: {strategy}")