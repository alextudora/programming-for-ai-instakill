import numpy as np

def cosine_similarity(query_vector: np.ndarray, corpus_vectors: np.ndarray) -> np.ndarray:
    """Return one cosine score for every row in corpus_vectors."""
    dot_product = np.dot(corpus_vectors, query_vector)

    query_norm = np.linalg.norm(query_vector)
    corpus_norms = np.linalg.norm(corpus_vectors, axis=1)

    if query_norm == 0:
        return np.zeros(len(corpus_vectors))

    denominator = query_norm * corpus_norms
    denominator[denominator == 0] = 1e-10

    return dot_product / denominator


def stable_top_k(scores: np.ndarray, post_ids: list[int], k: int) -> list[int]:
    """Return indices ordered by score descending, then post_id ascending."""

    items = list(zip(range(len(scores)), scores, post_ids))

    items.sort(key=lambda x: (-x[1], x[2]))

    return [item[0] for item in items[:k]]