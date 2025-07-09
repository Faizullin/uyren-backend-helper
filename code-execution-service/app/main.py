from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.openapi.utils import get_openapi
from .config import settings
from .database import redis_manager
from .routes import code_execution, health, content_ml_helper


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Redis connection
    try:
        await redis_manager.get_redis()
        print("Redis connection established")
    except Exception as e:
        print(f"Redis connection failed: {e}")
    
    yield
    
    # Cleanup
    try:
        await redis_manager.close()
        print("Redis connection closed")
    except Exception as e:
        print(f"Redis cleanup error: {e}")


app = FastAPI(
    title="Code Execution Service",
    description="Stateless microservice for code execution with Firebase authentication",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,  # Disable redoc in production
    openapi_url="/openapi.json" if settings.debug else None,  # Disable OpenAPI schema in production
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(code_execution.router, prefix="/api/v1/executions", tags=["code-execution"])
app.include_router(content_ml_helper.router, prefix="/api/v1/content_ml_helper", tags=["content-ml-helper"])
