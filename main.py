import os
import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from datetime import datetime

from app.api.routes import router as api_router
from app.utils.logging_config import setup_logging, RequestLogger
from app.utils.error_handlers import setup_exception_handlers


# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_file = os.getenv("LOG_FILE", None)
setup_logging(log_level=log_level, log_file=log_file)

logger = logging.getLogger('app.main')


class CustomJSONResponse(JSONResponse):
    """Custom JSON response that handles datetime serialization"""
    
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            default=self._json_serializer
        ).encode("utf-8")
    
    @staticmethod
    def _json_serializer(obj):
        """Custom JSON serializer for datetime objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("🚀 Starting Dividend Calendar API")
    logger.info(f"Log level: {log_level}")
    logger.info(f"Log file: {log_file or 'Console only'}")
    
    # Initialize any startup tasks here
    try:
        # Test scraper manager
        from app.scrapers.scraper_manager import scraper_manager
        logger.info(f"Initialized scraper manager with {len(scraper_manager.scrapers)} scrapers")
        logger.info(f"Available scrapers: {list(scraper_manager.scrapers.keys())}")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Dividend Calendar API")


# Create FastAPI application
app = FastAPI(
    title="Dividend Calendar API",
    default_response_class=CustomJSONResponse,
    description="""
    A FastAPI service for retrieving dividend calendar data from multiple financial data sources.
    
    ## Features
    
    * **Multiple Data Sources**: Scrapes data from Yahoo Finance, MarketWatch, and Investing.com
    * **Automatic Fallback**: If one source fails, automatically tries others
    * **Intelligent Caching**: Caches results with configurable TTL to reduce scraping load
    * **Batch Processing**: Support for querying multiple symbols concurrently
    * **Rate Limiting**: Built-in rate limiting to respect source websites
    * **Comprehensive Logging**: Detailed logging and error tracking
    * **Performance Monitoring**: Built-in statistics and health monitoring
    
    ## Usage
    
    * Get dividend data for a single symbol: `GET /api/v1/dividend/{symbol}`
    * Get dividend data for multiple symbols: `POST /api/v1/dividend/batch`
    * Check API health: `GET /api/v1/health`
    * View performance statistics: `GET /api/v1/stats`
    * Clear cache: `DELETE /api/v1/cache`
    
    ## Data Sources
    
    The API automatically tries multiple sources in order of reliability:
    1. **Yahoo Finance** - Primary source with comprehensive data
    2. **MarketWatch** - Backup source with good coverage
    3. **Investing.com** - Additional source for broader coverage
    
    ## Caching
    
    Results are cached for 1 hour by default to improve performance and reduce load on source websites.
    Cache can be disabled per request or cleared via API endpoints.
    """,
    version="1.0.0",
    contact={
        "name": "Dividend Calendar API",
        "url": "https://github.com/yourusername/dividend-api",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    lifespan=lifespan
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log HTTP requests"""
    request_logger = RequestLogger()
    return await request_logger(request, call_next)

# Set up exception handlers
setup_exception_handlers(app)

# Include API routes
app.include_router(api_router)

# Root endpoint
@app.get("/", 
         summary="API Root",
         description="Basic API information and health check")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Dividend Calendar API",
        "version": "1.0.0",
        "description": "FastAPI service for retrieving dividend calendar data",
        "timestamp": datetime.utcnow().isoformat(),
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "health_url": "/api/v1/health",
        "stats_url": "/api/v1/stats"
    }


# Additional middleware for security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to responses"""
    response = await call_next(request)
    
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response


if __name__ == "__main__":
    import uvicorn
    
    # Configuration from environment variables
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    workers = int(os.getenv("WORKERS", "1"))
    
    logger.info(f"Starting server on {host}:{port}")
    logger.info(f"Reload: {reload}, Workers: {workers}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,  # Use 1 worker in reload mode
        log_level=log_level.lower(),
        access_log=True
    )
