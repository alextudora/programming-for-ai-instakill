"""Seeds the InstaKill database with a handful of synthetic users and posts."""
from app.db.database import get_connection, init_db

USERS = ["alice", "bob", "carol", "dave", "erin"]
POSTS = [
    (1, "hello world, this is my first post"),
    (1, "does anyone else think the feed is chronological only? boring"),
    (2, "just shipped a cosine similarity search, feels great"),
    (3, "spam spam spam buy now click here"),
    (4, "benchmarking my ranker against popularity baseline today"),
    (5, "red-team week is going to be brutal, good luck everyone"),
]
FOLLOWS = [
    (1, 2), (1, 3),  # alice follows bob & carol
    (2, 1), (2, 5),  # bob follows alice & erin
    (3, 5),          # carol follows erin
    (4, 1),          # dave follows alice
]
LIKES = [
    (1, 3), (1, 6),          # alice likes bob's and erin's posts
    (2, 1), (2, 2), (2, 5),  # bob likes alice's and dave's posts
    (3, 3), (3, 6),          # carol likes bob's and erin's posts
    (4, 1), (4, 3), (4, 5),  # dave likes alice's, bob's, and dave's posts
    (5, 3), (5, 5),          # erin likes bob's and dave's posts
]

def seed() -> None:
    init_db()
    with get_connection() as conn:
        for username in USERS:
            conn.execute(
                "INSERT OR IGNORE INTO user (username) VALUES (?)", (username,)
            )
        for user_id, content in POSTS:
            conn.execute(
                "INSERT INTO post (user_id, content) VALUES (?, ?)", (user_id, content)
            )
        for follower_id, followee_id in FOLLOWS:
            conn.execute(
                "INSERT OR IGNORE INTO follow (follower_id, followee_id) VALUES (?, ?)",(follower_id, followee_id)
            )
        for user_id, post_id in LIKES:
            conn.execute(
                "INSERT OR IGNORE INTO \"like\" (user_id, post_id) VALUES (?, ?)", (user_id, post_id)
            )
        conn.commit()
    print(f"Seeded {len(USERS)} users, {len(POSTS)} posts, {len(FOLLOWS)} follows, and {len(LIKES)} likes.")

if __name__ == "__main__":
    seed()
