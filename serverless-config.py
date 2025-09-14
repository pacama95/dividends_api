"""
Serverless-optimized configuration
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure minimal logging for serverless
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Environment detection
IS_SERVERLESS = os.getenv("IS_SERVERLESS", "false").lower() == "true"
IS_COLD_START = not hasattr(os, '_dividend_api_warmed')

@asynccontextmanager
async def serverless_lifespan(app: FastAPI):
    """Ultra-minimal lifespan for serverless cold start optimization"""
    if IS_COLD_START:
        logger.info("🚀 Cold start - minimal initialization")
        os._dividend_api_warmed = True
    else:
        logger.info("♻️ Warm start")
    
    yield
    
    logger.info("🛑 Shutdown")

def create_serverless_app():
    """Create FastAPI app optimized for serverless"""
    
    app = FastAPI(
        title="Dividend API",
        description="Serverless dividend data API",
        version="1.0.0",
        lifespan=serverless_lifespan,
        # Disable features not needed in serverless
        docs_url="/docs" if not IS_SERVERLESS else None,
        redoc_url="/redoc" if not IS_SERVERLESS else None,
    )
    
    # Minimal CORS for serverless
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    
    return app

# Memory optimization settings
MEMORY_OPTIMIZED_CACHE_SIZE = 50  # Smaller cache for serverless
SERVERLESS_TIMEOUT = 10  # Shorter timeout for serverless
