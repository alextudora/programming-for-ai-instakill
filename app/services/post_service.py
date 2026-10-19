from datetime import datetime, timezone
from app.domain.models import Post


class PostService:
    """
    Application service that coordinates business logic for Posts.
    Currently, it handles the boundary logic without directly persisting to SQLite or handling HTTP.
    """

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