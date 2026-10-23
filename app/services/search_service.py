import numpy as np
from app.adapters.encoder import SemanticEncoder
from app.repositories.post_repository import PostRepository
from app.domain.retrieval import cosine_similarity, stable_top_k


class SearchService:
    """
    Coordinates semantic search operations.
    Maintains an in-memory index of post embeddings for fast retrieval.
    """

    def __init__(self, encoder: SemanticEncoder, repository: PostRepository):
        self.encoder = encoder
        self.repository = repository

        self.posts = []
        self.corpus_embeddings = None

    def build_index(self):
        """Fetches posts from DB and computes embeddings to store in memory at startup."""
        self.posts = self.repository.get_all_posts()

        if not self.posts:
            self.corpus_embeddings = np.array([])
            return

        texts = [post.content for post in self.posts]
        self.corpus_embeddings = self.encoder.encode(texts)

    def search(self, query: str, limit: int) -> list[dict]:
        """Runs the search query against the in-memory index using pure retrieval logic."""
        if not self.posts or self.corpus_embeddings is None or len(self.corpus_embeddings) == 0:
            return []

        query_embedding = self.encoder.encode([query])[0]

        scores = cosine_similarity(query_embedding, self.corpus_embeddings)
        post_ids = [post.id for post in self.posts]

        top_k_indices = stable_top_k(scores, post_ids, limit)

        results = []
        for idx in top_k_indices:
            post = self.posts[idx]
            results.append({
                "post_id": post.id,
                "user_id": post.user_id,
                "content": post.content,
                "score": float(scores[idx])
            })

        return results