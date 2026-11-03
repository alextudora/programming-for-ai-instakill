import sys
import zipfile
import csv
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Add the root directory to sys.path to import app.db.database
sys.path.append(str(Path(__file__).resolve().parent.parent))
from app.db.database import get_connection


def seed_db(zip_path: str):
    events = []
    movies = {}

    # 1. Read data directly from the archive without extracting to disk
    with zipfile.ZipFile(zip_path) as archive:
        ratings_name = next(f for f in archive.namelist() if f.endswith('ratings.csv'))
        movies_name = next(f for f in archive.namelist() if f.endswith('movies.csv'))

        with archive.open(ratings_name) as f:
            reader = csv.DictReader(f.read().decode('utf-8').splitlines())
            for r in reader:
                events.append({
                    "user_id": int(r["userId"]),
                    "movie_id": int(r["movieId"]),
                    "ts": int(r["timestamp"]),
                    "rating": float(r["rating"])
                })

        with archive.open(movies_name) as f:
            reader = csv.DictReader(f.read().decode('utf-8').splitlines())
            for r in reader:
                movies[int(r["movieId"])] = r["title"]

    # 2. Deterministic bounding: ~200 users, ~2000 posts
    valid_users = sorted(list({e["user_id"] for e in events}))[:200]
    valid_movies = sorted(list(movies.keys()))[:2000]

    user_set = set(valid_users)
    movie_set = set(valid_movies)

    # 3. Calculate post creation time (the first timestamp the movie appeared)
    first_seen = {}
    for e in events:
        mid = e["movie_id"]
        if mid in movie_set:
            first_seen[mid] = min(e["ts"], first_seen.get(mid, e["ts"]))

    # 4. Transform: Rating >= 4 becomes a Like
    likes = [e for e in events if e["user_id"] in user_set and e["movie_id"] in movie_set and e["rating"] >= 4.0]

    with get_connection() as conn:
        # Idempotent: clear old data before running
        conn.executescript("DELETE FROM \"like\"; DELETE FROM follow; DELETE FROM post; DELETE FROM user;")

        for uid in valid_users:
            conn.execute("INSERT INTO user (id, username) VALUES (?, ?)", (uid, f"user_{uid}"))

        for mid in valid_movies:
            ts = first_seen.get(mid, 0)
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat() if ts else datetime.now(
                timezone.utc).isoformat()
            # Posts are attributed to the first user as a mock system
            conn.execute(
                "INSERT INTO post (id, user_id, content, created_at) VALUES (?, ?, ?, ?)",
                (mid, valid_users[0], movies[mid], dt)
            )

        for like in likes:
            dt = datetime.fromtimestamp(like["ts"], tz=timezone.utc).isoformat()
            try:
                conn.execute(
                    "INSERT INTO \"like\" (user_id, post_id, created_at) VALUES (?, ?, ?)",
                    (like["user_id"], like["movie_id"], dt)
                )
            except sqlite3.IntegrityError:
                pass

        # Simple and deterministic rule for follows: each user follows the previous one
        for i in range(1, len(valid_users)):
            conn.execute(
                "INSERT INTO follow (follower_id, followee_id) VALUES (?, ?)",
                (valid_users[i], valid_users[i - 1])
            )

        conn.commit()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/seed_movielens.py <path_to_zip>")
        sys.exit(1)
    seed_db(sys.argv[1])