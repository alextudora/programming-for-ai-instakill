import sqlite3
from app.domain.models import Post


class PostRepository:
    """
    Repository boundary for reading Post data from SQLite.
    Isolates database queries from the business/search logic.
    """

    def __init__(self, db_path: str = "instakill.db"):
        self.db_path = db_path

    def get_all_posts(self) -> list[Post]:
        """
        Reads all seeded posts from the database and returns them as Pydantic Domain Models.
        """
        posts = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT id, user_id, content, created_at FROM post")
            rows = cursor.fetchall()

            for row in rows:
                posts.append(Post(**dict(row)))

        return posts