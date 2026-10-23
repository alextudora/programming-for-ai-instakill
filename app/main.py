from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query

from app.db.database import init_db
from app.adapters.encoder import SemanticEncoder
from app.repositories.post_repository import PostRepository
from app.services.search_service import SearchService

search_service = None

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
