from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from app.db.database import init_db
from app.adapters.encoder import SemanticEncoder
from app.repositories.post_repository import PostRepository
from app.services.search_service import SearchService
from app.services.post_service import PostService

search_service = None
post_service = PostService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    global search_service
    encoder = SemanticEncoder()
    repository = PostRepository()
    search_service = SearchService(encoder, repository)
    search_service.build_index()

    yield


app = FastAPI(title="InstaKill", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

@app.get("/search")
def search_posts(
        q: str = Query(..., min_length=1, description="Non-empty query string"),
        limit: int = Query(..., ge=1, le=20, description="Limit between 1 and 20)")
):
    """
        GET /search?q=<non-empty query>&limit=<1..20>
        Returns the original query and a list of up to `limit` results.
        """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty or just whitespace.")

    results = search_service.search(q.strip(), limit)

    return {
        "query": q,
        "results": results
    }

@app.get("/feed")
def get_user_feed(
        user_id: int = Query(..., description="The ID of the user requesting the feed"),
        limit: int = Query(20, ge=1, le=50, description="Maximum number of posts to return (1..50)"),
        strategy: str = Query("for_you", description="Ranking strategy: for_you or chronological")
):
    """
        GET /feed?user_id=<int>&limit=<1..50>&strategy=for_you|chronological
        Returns the user's customized feed based on the selected ranking strategy.
    """
    # Validate strategy parameter contract
    if strategy not in ["for_you", "chronological"]:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid strategy '{strategy}'. Must be 'for_you' or 'chronological'."
        )

    try:
        # Delegate business logic and ranking coordination to the PostService
        feed_posts = post_service.get_feed(user_id=user_id, limit=limit, strategy=strategy)
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=422, detail=error_msg)

    return {
        "user_id": user_id,
        "strategy": strategy,
        "results": feed_posts
    }