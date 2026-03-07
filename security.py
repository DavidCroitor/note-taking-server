import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="x-API-Key")
def verify_api_key(api_key: str = Security(api_key_header)):
    expected_key = os.getenv('MY_SECRET_KEY_API_KEY')
    if not expected_key or api_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid API Key")