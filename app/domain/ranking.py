"""Pure ranking algorithms for the InstaKill feed. No I/O, no DB, no clock calls."""
import heapq
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Tuple

from app.domain.models import Post

HALF_LIFE_SECONDS = 3 * 86400  # 3 days in seconds


@dataclass(frozen=True)
class FeedSignals:
    """Retains all pre-calculated signals necessary to evaluate a candidate."""
    followed_authors: set[int]
    post_likes: dict[int, int]
    max_likes: int


def freshness(post: Post, now: datetime) -> float:
    """1.0 for a new post, decreases to 0.5 after HALF_LIFE_SECONDS."""
    age_seconds = (now - post.created_at).total_seconds()
    age_seconds = max(0, age_seconds)  # Prevent negative values if there are clock sync issues
    return 0.5 ** (age_seconds / HALF_LIFE_SECONDS)


def affinity(post: Post, signals: FeedSignals) -> float:
    """1.0 if the user follows the author of the post, otherwise 0.0."""
    if post.user_id in signals.followed_authors:
        return 1.0
    return 0.0


def popularity(post: Post, signals: FeedSignals) -> float:
    """ Number of likes for the post, normalized by the maximum number of likes in the system."""
    if signals.max_likes == 0:
        return 0.0
    likes = signals.post_likes.get(post.id, 0)
    return likes / signals.max_likes


def score_post(post: Post, signals: FeedSignals, now: datetime, weights: Dict[str, float]) -> float:
    """Calculates the final score using the configured weights."""
    f = freshness(post, now)
    a = affinity(post, signals)
    p = popularity(post, signals)

    # We use ".get" for flexibility, but explicit values should be passed
    return (
            weights.get("freshness", 1.0) * f +
            weights.get("affinity", 1.0) * a +
            weights.get("popularity", 1.0) * p
    )


def rank_feed(
        candidates: List[Post],
        signals: FeedSignals,
        now: datetime,
        weights: Dict[str, float],
        limit: int
) -> List[Tuple[float, Post]]:
    """
    Selects the top-k posts based on their score, evaluating the candidates in a single pass.
    In case of a tie in score, the tie-breaker is the post_id in ascending order.
    """
    scored = []
    for post in candidates:
        score = score_post(post, signals, now, weights)
        scored.append((score, post))

    # heapq.nsmallest  search for the smallest values. We use -score to bring
    # the highest scores to the front. In case of a tie, the post.id with the lowest value has priority.
    best = heapq.nsmallest(limit, scored, key=lambda pair: (-pair[0], pair[1].id))
    return best