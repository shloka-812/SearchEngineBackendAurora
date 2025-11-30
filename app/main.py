import asyncio
import httpx
import re
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import List, Optional


UPSTREAM_API_URL = "https://november7-730026606190.europe-west1.run.app/messages/" 
UPSTREAM_PAGE_LIMIT = 100
MAX_RETRIES = 5 
INITIAL_DELAY_SECONDS = 0.5

# Global variable to hold the cached messages
MESSAGES_CACHE: List[dict] = []

class Message(BaseModel):
    """Model for single message record."""
    id: str
    user_id: str
    user_name: str
    timestamp: str
    message: str

class SearchResult(BaseModel):
    """Model for the paginated search result response."""
    total_matches: int = Field(..., description="Total number of records matching the query across all pages")
    page_number: int = Field(..., description="The current page number")
    page_limit: int = Field(..., description="The maximum number of records per page")
    items: List[Message] = Field(..., description="The list of messages for the current page.")
    # cached_timestamp: Optional[str] = Field(..., description="Timestamp when the data was last loaded from the upstream API.")

#  Data Loading Logic

app = FastAPI(
    title="Cached Search Engine API Service",
    description="A Python API service that searches data from an external API",
    version="1.0.0"
)

async def fetch_all_messages(client: httpx.AsyncClient) -> List[dict]:
    """
    Fetches all messages from the upstream API, using sequential fetching and
    retries to handle rate limits and transient errors.
    """

    print("]Starting initial data load.")
    all_data = []
    skip = 0
    total = None
    
    # 1. Fetch total count from the first page
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.get(UPSTREAM_API_URL, params={"skip": 0, "limit": UPSTREAM_PAGE_LIMIT})
            response.raise_for_status()
            data = response.json()
            total = data.get("total", 0)
            
            if total == 0:
                print("No data found in the upstream API.")
                return []
                
            all_data.extend(data.get("items", []))
            skip += UPSTREAM_PAGE_LIMIT
            print(f"Total messages to fetch: {total}. Fetched 0-{skip}.")
            break # Success
            
        except httpx.HTTPStatusError as e:
            print(f" Retrying in {INITIAL_DELAY_SECONDS * (2 ** attempt):.1f}s...")
            await asyncio.sleep(INITIAL_DELAY_SECONDS * (2 ** attempt))
        except Exception as e:
            print(f"Initial fetch unexpected error on attempt {attempt + 1}: {e}. Retrying...")
            await asyncio.sleep(INITIAL_DELAY_SECONDS * (2 ** attempt))
    else:
        # This block executes if the loop completes without a 'break' ->  all retries failed
        raise ConnectionError("CRITICAL: Failed to get total count or initial data after all retries.")


    # 2. Fetch remaining pages SEQUENTIALLY with delay and retries
    if total and total > UPSTREAM_PAGE_LIMIT:
        print(f"Starting sequential fetch of remaining pages")
        
        while skip < total:
            # base delay to avoid simple rate limiting
            await asyncio.sleep(INITIAL_DELAY_SECONDS) 

            # Retry loop for the current page
            for attempt in range(MAX_RETRIES):
                try:
                    response = await client.get(
                        UPSTREAM_API_URL, 
                        params={"skip": skip, "limit": UPSTREAM_PAGE_LIMIT}
                    )
                    response.raise_for_status()
                    data = response.json()
                    all_data.extend(data.get("items", []))
                    
                    break #success

                except Exception as e:
                    delay = INITIAL_DELAY_SECONDS * (2 ** attempt)
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(delay)
                    else:
                        # Log final failure
                        print(f"CRITICAL Failure: to fetch data at skip={skip} after {MAX_RETRIES} attempts. Error: {e}")
                        
            skip += UPSTREAM_PAGE_LIMIT
            
    # Final check and update
    fetched_count = len(all_data)
    if fetched_count != total:
        print(f"WARNING: Fetched {fetched_count} records, expected {total}. Search results will be incomplete.")
        
    
    print(f"Data load complete. Cached {fetched_count} messages. ---")
    return all_data

@app.on_event("startup")
async def startup_event():
    """Load data into cache when the FastAPI application starts."""
    global MESSAGES_CACHE
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            MESSAGES_CACHE = await fetch_all_messages(client)
        except ConnectionError as e:
            print(f"Failed to load initial data in startup. error : {e}")
        except Exception as e:
             print(f"UNEXPECTED ERROR during startup: {e}")


# API Endpoint 

@app.get("/search", response_model=SearchResult)
async def search_messages(
    query: str = Query(..., min_length=1, description="The search query to match against message content and user name"),
    page: int = Query(1, ge=1, description="The page number to retrieve"),
    limit: int = Query(10, ge=1, le=100, description="The number of records per page")
):
    """
    Performs an in-memory search against the cached data,
    and returns a paginated list of matching records.
    """
    if not MESSAGES_CACHE:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Search service is initializing or failed to load data.")
        
    start_time = asyncio.get_event_loop().time()
    
    
    normalized_query = query.lower()
    
    def is_match(msg: dict) -> bool:
        message_content = msg.get("message", "").lower()
        user_name = msg.get("user_name", "").lower()
        
        return normalized_query in message_content or normalized_query in user_name

    matching_messages = [msg for msg in MESSAGES_CACHE if is_match(msg)]
    
    total_matches = len(matching_messages)
    
    start_index = (page - 1) * limit
    end_index = start_index + limit
    
    paginated_results = matching_messages[start_index:end_index]
    
    end_time = asyncio.get_event_loop().time()
    latency_ms = (end_time - start_time) * 1000
    
    if latency_ms > 100:
        print(f"WARNING: Latency exceeded 100ms: {latency_ms:.2f} ms")


    #Return response
    return SearchResult(
        total_matches=total_matches,
        page_number=page,
        page_limit=limit,
        items=paginated_results
    )