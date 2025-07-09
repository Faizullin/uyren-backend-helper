from fastapi import APIRouter
from datetime import datetime
from ..schemas import HealthResponse

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        service="Code Execution Service",
        version="1.0.0"
    )


@router.get("/ready", response_model=HealthResponse)
async def readiness_check():
    """Readiness check endpoint"""
    # Check Redis connection
    try:
        from ..database import redis_manager
        redis_client = await redis_manager.get_redis()
        await redis_client.ping()
        
        return HealthResponse(
            status="ready",
            timestamp=datetime.utcnow().isoformat(),
            service="Code Execution Service",
            version="1.0.0"
        )
    except Exception as e:        return HealthResponse(
            status=f"not ready: {str(e)}",
            timestamp=datetime.utcnow().isoformat(),
            service="Code Execution Service",
            version="1.0.0"
        )
