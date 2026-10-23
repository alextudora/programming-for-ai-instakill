# API Contract: Create Post

## Endpoint
`POST /api/posts`

## Description
Creates a new post authored by an existing user. This endpoint coordinates with the `PostService` boundary to validate business rules before interacting with the persistence layer.

## Request

**Headers:**
- `Content-Type: application/json`

**Body:**
```json
{
  "user_id": 123,
  "content": "This is my first post on InstaKill!"
}
```

## Successful Response

**Status Code:** `201 Created`

**Body:**
```json
{
  "id": 456,
  "user_id": 123,
  "content": "This is my first post on InstaKill!",
  "created_at": "2026-10-19T20:00:00Z"
}
```

## Expected Validation / Error Cases

- **400 Bad Request:**
  - If the `content` string is empty, missing, or consists only of whitespace.
  - If the `content` string exceeds the maximum allowed length of 500 characters.
- **404 Not Found:**
  - If the provided `user_id` does not correspond to an existing user in the database.
- **422 Unprocessable Entity:**
  - If the payload schema is invalid (e.g., `user_id` is an object/string instead of an integer, or required fields are missing).

# API Contract: Search Posts

## Endpoint
`GET /search`

## Description
Performs a semantic search over the existing posts using a pretrained embedding model and pure NumPy cosine similarity. Returns up to `limit` results ordered by similarity score (descending) and post ID (ascending) as a deterministic tie-breaker.

## Request

**Query Parameters:**
- `q` (string): Required. The semantic query to search for.
- `limit` (integer): Required. The maximum number of results to return.

## Successful Response

**Status Code:** `200 OK`

**Body:**
```json
{
  "query": "cheap dinner",
  "results": [
    {
      "post_id": 6,
      "user_id": 5,
      "content": "red-team week is going to be brutal, good luck everyone",
      "score": 0.10695818811655045
    }
  ]
}
```
## Expected Validation / Error Cases

- **400 Bad Request:**
  - If the `q` query parameter is missing or empty.
- **422 Unprocessable Entity:**
  - If required parameters (q, limit) are missing.
  - If limit is out of the allowed 1-20 range.