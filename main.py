import os

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request

from slowapi import _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from security import verify_api_key
from routers import folders, notes

import logging

load_dotenv()

LOG_LEVEL = logging.DEBUG if os.getenv('ENVIRONMENT') == 'development' else logging.INFO
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = FastAPI(
    dependencies=[Depends(verify_api_key)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None)

app.state.limiter = notes.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/healthz", dependencies=[])
async def health_check():
    return {"status": "ok"}

app.include_router(folders.router)
app.include_router(notes.router)

