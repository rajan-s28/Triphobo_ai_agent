import os
import json
import aiohttp
import logging
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
VAPI_BASE_URL = "https://api.vapi.ai"

if not VAPI_PRIVATE_KEY:
    logger.error("VAPI_PRIVATE_KEY is not set in environment variables")
if not VAPI_ASSISTANT_ID:
    logger.error("VAPI_ASSISTANT_ID is not set in environment variables")

app = FastAPI(
    title="Vapi Voice Assistant",
    description="Real-time voice assistant using Vapi WebSocket API",
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

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "vapi_configured": bool(VAPI_PRIVATE_KEY and VAPI_ASSISTANT_ID)
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

@app.get("/config")
async def get_config():
    return {
        "hasPrivateKey": bool(VAPI_PRIVATE_KEY),
        "hasAssistantId": bool(VAPI_ASSISTANT_ID),
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