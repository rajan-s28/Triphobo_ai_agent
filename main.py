import os
import json
import aiohttp
import logging
import re
from typing import List, Dict
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("vapi-app")

VAPI_PRIVATE_KEY = os.getenv("VAPI_PRIVATE_KEY", "")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID", "")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")
VAPI_BASE_URL = "https://api.vapi.ai"
UNSPLASH_BASE_URL = "https://api.unsplash.com"

if not VAPI_PRIVATE_KEY:
    logger.error("VAPI_PRIVATE_KEY is not set in environment variables")
if not VAPI_ASSISTANT_ID:
    logger.error("VAPI_ASSISTANT_ID is not set in environment variables")
if not UNSPLASH_ACCESS_KEY:
    logger.error("UNSPLASH_ACCESS_KEY is not set in environment variables")

app = FastAPI(
    title="Vapi Voice Assistant",
    description="Real-time voice assistant using Vapi WebSocket API with Unsplash integration",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Common destination keywords and their variations
DESTINATION_KEYWORDS = {
    'cities': [
        'paris', 'london', 'new york', 'tokyo', 'rome', 'barcelona', 'amsterdam',
        'berlin', 'prague', 'vienna', 'budapest', 'dubai', 'singapore', 'hong kong',
        'sydney', 'melbourne', 'san francisco', 'los angeles', 'chicago', 'miami',
        'madrid', 'lisbon', 'stockholm', 'copenhagen', 'oslo', 'helsinki', 'zurich',
        'geneva', 'milan', 'florence', 'venice', 'naples', 'athens', 'istanbul',
        'cairo', 'marrakech', 'casablanca', 'cape town', 'johannesburg', 'mumbai',
        'delhi', 'bangalore', 'bangkok', 'phuket', 'bali', 'jakarta', 'manila',
        'seoul', 'busan', 'beijing', 'shanghai', 'guangzhou', 'taipei', 'kyoto',
        'osaka', 'hiroshima', 'sapporo',
        # ADD THESE MISSING CITIES:
        'moscow', 'st petersburg', 'novosibirsk', 'yekaterinburg', 'sochi', 'kazan',
        'goa', 'kochi', 'jaipur', 'agra', 'varanasi', 'udaipur', 'jodhpur',
        'rishikesh', 'manali', 'shimla', 'darjeeling', 'gangtok', 'shillong',
        'hyderabad', 'pune', 'ahmedabad', 'kolkata', 'chandigarh', 'lucknow',
        # Add more cities as needed
    ],
    'countries': [
        'france', 'italy', 'spain', 'greece', 'turkey', 'egypt', 'morocco',
        'south africa', 'kenya', 'tanzania', 'india', 'thailand', 'vietnam',
        'cambodia', 'laos', 'myanmar', 'indonesia', 'malaysia', 'philippines',
        'singapore', 'japan', 'south korea', 'china', 'taiwan', 'australia',
        'new zealand', 'brazil', 'argentina', 'chile', 'peru', 'colombia',
        'mexico', 'costa rica', 'panama', 'canada', 'united states', 'usa',
        'united kingdom', 'uk', 'germany', 'netherlands', 'belgium', 'austria',
        'switzerland', 'sweden', 'norway', 'denmark', 'finland', 'iceland',
        'portugal', 'czech republic', 'hungary', 'poland', 'croatia', 'slovenia',
        # ADD THESE:
        'russia', 'ukraine', 'belarus', 'estonia', 'latvia', 'lithuania', 'indonesia'
    ],
    'landmarks': [
        'eiffel tower', 'statue of liberty', 'big ben', 'colosseum', 'acropolis',
        'taj mahal', 'great wall', 'machu picchu', 'christ the redeemer',
        'petra', 'angkor wat', 'borobudur', 'chichen itza', 'neuschwanstein',
        'mount rushmore', 'golden gate bridge', 'sydney opera house',
        'burj khalifa', 'sagrada familia', 'louvre', 'vatican', 'buckingham palace'
    ],
    'regions': [
        'tuscany', 'provence', 'bavaria', 'andalusia', 'catalonia', 'patagonia',
        'amazonia', 'sahara', 'sahel', 'maghreb', 'scandinavia', 'balkans',
        'caucasus', 'siberia', 'himalayas', 'alps', 'andes', 'rockies',
        'caribbean', 'mediterranean', 'baltic', 'adriatic', 'aegean'
    ]
}

def extract_destinations(text: str) -> List[str]:
    """Extract potential destination names from text using keyword matching."""
    text_lower = text.lower()
    found_destinations = []

    # Check all categories of destinations
    for category, destinations in DESTINATION_KEYWORDS.items():
        for destination in destinations:
            # Use word boundary regex to avoid partial matches
            pattern = r'\b' + re.escape(destination) + r'\b'
            if re.search(pattern, text_lower):
                found_destinations.append(destination.title())

    # Remove duplicates while preserving order
    seen = set()
    unique_destinations = []
    for dest in found_destinations:
        if dest.lower() not in seen:
            seen.add(dest.lower())
            unique_destinations.append(dest)

    return unique_destinations

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "vapi_configured": bool(VAPI_PRIVATE_KEY and VAPI_ASSISTANT_ID),
        "unsplash_configured": bool(UNSPLASH_ACCESS_KEY)
    }

@app.get("/make_call")
async def make_call():
    if not VAPI_PRIVATE_KEY or not VAPI_ASSISTANT_ID:
        logger.error("Missing Vapi configuration")
        raise HTTPException(
            status_code=500,
            detail="Vapi configuration is incomplete. Check VAPI_PRIVATE_KEY and VAPI_ASSISTANT_ID."
        )

    call_payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "transport": {
            "provider": "vapi.websocket",
            "audioFormat": {
                "format": "pcm_s16le",
                "container": "raw",
                "sampleRate": 16000
            }
        }
    }

    headers = {
        "Authorization": f"Bearer {VAPI_PRIVATE_KEY}",
        "Content-Type": "application/json"
    }

    try:
        logger.info("Creating new Vapi call...")
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{VAPI_BASE_URL}/call",
                headers=headers,
                json=call_payload
            ) as response:
                logger.info(f"Vapi API response status: {response.status}")
                if response.status not in [200, 201]:
                    error_text = await response.text()
                    logger.error(f"Vapi API error: {response.status} - {error_text}")
                    raise HTTPException(
                        status_code=response.status,
                        detail=f"Vapi API error: {error_text}"
                    )

                result = await response.json()

                if "transport" not in result or "websocketCallUrl" not in result["transport"]:
                    logger.error("Invalid response from Vapi API - missing websocketCallUrl")
                    raise HTTPException(
                        status_code=500,
                        detail="Invalid response from Vapi API"
                    )

                websocket_url = result["transport"]["websocketCallUrl"]
                call_id = result.get("id", "unknown")

                logger.info(f"Call created successfully. ID: {call_id}")
                logger.info(f"WebSocket URL: {websocket_url}")

                return {
                    "url": websocket_url,
                    "callId": call_id,
                    "status": "created"
                }

    except aiohttp.ClientError as e:
        logger.error(f"Network error when calling Vapi API: {e}")
        raise HTTPException(
            status_code=503,
            detail="Network error connecting to Vapi API"
        )
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response from Vapi API: {e}")
        raise HTTPException(
            status_code=502,
            detail="Invalid response from Vapi API"
        )
    except Exception as e:
        logger.error(f"Unexpected error in make_call: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@app.post("/extract-destinations")
async def extract_destinations_endpoint(request: Request):
    """Extract destinations from provided text."""
    try:
        data = await request.json()
        text = data.get("text", "")

        if not text:
            return {"destinations": []}

        destinations = extract_destinations(text)
        logger.info(f"Extracted destinations from text: {destinations}")

        return {"destinations": destinations}

    except Exception as e:
        logger.error(f"Error extracting destinations: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract destinations")

@app.get("/destination-photos/{destination}")
async def get_destination_photos(destination: str, count: int = 6):
    """Get photos for a specific destination from Unsplash."""
    if not UNSPLASH_ACCESS_KEY:
        raise HTTPException(
            status_code=503,
            detail="Unsplash API key not configured"
        )

    try:
        headers = {
            "Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}",
            "Accept-Version": "v1"
        }

        # Create search query - add travel-related terms for better results
        search_query = f"{destination} travel destination landmark"

        params = {
            "query": search_query,
            "per_page": min(count, 30),  # Unsplash max is 30
            "orientation": "landscape",
            "content_filter": "high",
            "order_by": "relevant"
        }

        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{UNSPLASH_BASE_URL}/search/photos",
                headers=headers,
                params=params
            ) as response:

                if response.status != 200:
                    logger.error(f"Unsplash API error: {response.status}")
                    raise HTTPException(
                        status_code=response.status,
                        detail="Failed to fetch photos from Unsplash"
                    )

                data = await response.json()
                photos = []

                for photo in data.get("results", []):
                    photos.append({
                        "id": photo["id"],
                        "url": photo["urls"]["regular"],
                        "thumb": photo["urls"]["small"],
                        "alt": photo.get("alt_description") or f"{destination} travel photo",
                        "photographer": photo["user"]["name"],
                        "photographer_url": photo["user"]["links"]["html"],
                        "download_location": photo["links"]["download_location"]
                    })

                logger.info(f"Retrieved {len(photos)} photos for destination: {destination}")

                return {
                    "destination": destination,
                    "photos": photos,
                    "total": len(photos)
                }

    except aiohttp.ClientError as e:
        logger.error(f"Network error when calling Unsplash API: {e}")
        raise HTTPException(
            status_code=503,
            detail="Network error connecting to Unsplash API"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_destination_photos: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

@app.get("/config")
async def get_config():
    return {
        "hasPrivateKey": bool(VAPI_PRIVATE_KEY),
        "hasAssistantId": bool(VAPI_ASSISTANT_ID),
        "hasUnsplashKey": bool(UNSPLASH_ACCESS_KEY),
        "baseUrl": VAPI_BASE_URL
    }

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP error on {request.url}: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )

if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    logger.info("Starting Vapi Voice Assistant server...")
    logger.info(f"Server will be available at: http://127.0.0.1:8080")
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
        log_level="info"
    )