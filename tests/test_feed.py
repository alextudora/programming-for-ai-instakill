"""Tests for the ranking logic and GET /feed endpoint."""
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.domain.models import Post
from app.domain.ranking import FeedSignals, rank_feed

client = TestClient(app)


def test_rank_feed_determinism_and_sorting():
    """Test that rank_feed correctly sorts by score and applies deterministic tie-breaking."""
    now = datetime.now(timezone.utc)
    p1 = Post(id=1, user_id=2, content="old", created_at=now)
    p2 = Post(id=2, user_id=3, content="new", created_at=now)

    candidates = [p1, p2]
    signals = FeedSignals(followed_authors=set(), post_likes={}, max_likes=1)

    # Force scores to be equal to test post_id tie-breaker (smaller id first)
    ranked = rank_feed(candidates, signals, now, {"freshness": 1.0, "affinity": 1.0, "popularity": 1.0}, limit=2)

    assert len(ranked) == 2
    # Both have same score, so p1 (id=1) should come before p2 (id=2) due to tie-break rule
    assert ranked[0][1].id == 1


def test_get_feed_endpoint_success():
    """Test successful response of GET /feed for a seeded user."""
    response = client.get("/feed?user_id=1&limit=5&strategy=for_you")
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == 1
    assert data["strategy"] == "for_you"
    assert isinstance(data["results"], list)


def test_get_feed_endpoint_not_found():
    """Test 404 error when user does not exist."""
    response = client.get("/feed?user_id=99999&limit=5")
    assert response.status_code == 404