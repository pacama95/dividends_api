from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime

from app.models.dividend import DividendCalendarResponse, ErrorResponse, BatchDividendRequest
from app.scrapers.scraper_manager import scraper_manager
from app.scrapers.base_scraper import ScraperError

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1", tags=["dividend"])


@router.get("/dividend/{symbol}", 
           response_model=DividendCalendarResponse,
           summary="Get dividend data for a stock symbol",
           description="Retrieve dividend calendar data for a specific stock symbol using multiple data sources with caching")
async def get_dividend_data(
    symbol: str,
    sources: Optional[List[str]] = Query(None, description="Preferred data sources (yahoo, marketwatch)"),
    use_cache: bool = Query(True, description="Whether to use cached data if available")
):
    """
    Get dividend calendar data for a stock symbol.
    
    This endpoint scrapes dividend information from multiple financial data sources
    with automatic fallback and caching capabilities.
    
    Args:
        symbol: Stock ticker symbol (e.g., AAPL, MSFT)
        sources: Optional list of preferred data sources
        use_cache: Whether to use cached data
        
    Returns:
        DividendCalendarResponse with dividend data and metadata
    """
    try:
        # Validate symbol
        if not symbol or len(symbol.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error="Invalid symbol",
                    error_code="INVALID_SYMBOL",
                    symbol=symbol,
                    timestamp=datetime.utcnow()
                ).model_dump()
            )
        
        # Validate sources if provided
        valid_sources = {'yahoo', 'marketwatch'}
        if sources:
            invalid_sources = set(sources) - valid_sources
            if invalid_sources:
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponse(
                        error=f"Invalid sources: {', '.join(invalid_sources)}. Valid sources: {', '.join(valid_sources)}",
                        error_code="INVALID_SOURCES",
                        symbol=symbol,
                        timestamp=datetime.utcnow()
                    ).model_dump()
                )
        
        # Temporarily disable cache if requested
        original_cache_setting = scraper_manager.use_cache
        if not use_cache:
            scraper_manager.use_cache = False
        
        try:
            # Get dividend data
            logger.info(f"API request for dividend data: {symbol}, sources: {sources}")
            result = await scraper_manager.get_dividend_data(symbol, sources)
            
            return result
            
        finally:
            # Restore cache setting
            scraper_manager.use_cache = original_cache_setting
            
    except HTTPException:
        raise
    except ScraperError as e:
        logger.error(f"Scraper error for {symbol}: {e}")
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=str(e),
                error_code="SCRAPER_ERROR",
                symbol=symbol,
                sources_attempted=sources or [],
                timestamp=datetime.utcnow()
            ).model_dump()
        )
    except Exception as e:
        logger.error(f"Unexpected error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Internal server error",
                error_code="INTERNAL_ERROR",
                symbol=symbol,
                timestamp=datetime.utcnow()
            ).model_dump()
        )


@router.post("/dividend/batch",
            response_model=Dict[str, DividendCalendarResponse],
            summary="Get dividend data for multiple symbols",
            description="Retrieve dividend calendar data for multiple stock symbols concurrently")
async def get_multiple_dividend_data(
    request: BatchDividendRequest
):
    """
    Get dividend calendar data for multiple stock symbols concurrently.
    
    Args:
        request: BatchDividendRequest with symbols and optional sources
        
    Returns:
        Dictionary mapping symbols to their dividend data
    """
    try:
        symbols = request.symbols
        sources = request.sources
        
        # Validate sources if provided
        valid_sources = {'yahoo', 'marketwatch'}
        if sources:
            invalid_sources = set(sources) - valid_sources
            if invalid_sources:
                raise HTTPException(
                    status_code=400,
                    detail=ErrorResponse(
                        error=f"Invalid sources: {', '.join(invalid_sources)}. Valid sources: {', '.join(valid_sources)}",
                        error_code="INVALID_SOURCES",
                        timestamp=datetime.utcnow()
                    ).model_dump()
                )
        
        logger.info(f"Batch API request for {len(symbols)} symbols")
        result = await scraper_manager.get_multiple_symbols(symbols, sources)
        
        # Ensure proper JSON encoding of the result
        return jsonable_encoder(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in batch request: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Internal server error",
                error_code="INTERNAL_ERROR",
                timestamp=datetime.utcnow()
            ).model_dump()
        )


@router.get("/stats",
           response_model=Dict[str, Any],
           summary="Get API and scraper statistics",
           description="Retrieve performance statistics and status information")
async def get_stats():
    """
    Get API and scraper performance statistics.
    
    Returns:
        Dictionary with scraper performance, cache stats, and system information
    """
    try:
        stats = scraper_manager.get_scraper_stats()
        
        # Add API-specific stats
        stats['api'] = {
            'timestamp': datetime.utcnow().isoformat(),
            'version': 'v1'
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Error retrieving statistics",
                error_code="STATS_ERROR",
                timestamp=datetime.utcnow()
            ).model_dump()
        )


@router.delete("/cache",
              summary="Clear all cached data",
              description="Clear all cached dividend data")
async def clear_cache():
    """
    Clear all cached dividend data.
    
    Returns:
        Number of items cleared from cache
    """
    try:
        cleared_count = scraper_manager.clear_cache()
        
        return {
            "message": f"Successfully cleared {cleared_count} items from cache",
            "cleared_count": cleared_count,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Error clearing cache",
                error_code="CACHE_ERROR",
                timestamp=datetime.utcnow()
            ).model_dump()
        )


@router.delete("/cache/{symbol}",
              summary="Clear cached data for a specific symbol",
              description="Invalidate cached dividend data for a specific stock symbol")
async def clear_symbol_cache(symbol: str):
    """
    Clear cached data for a specific stock symbol.
    
    Args:
        symbol: Stock ticker symbol
        
    Returns:
        Success message
    """
    try:
        if not symbol or len(symbol.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail=ErrorResponse(
                    error="Invalid symbol",
                    error_code="INVALID_SYMBOL",
                    symbol=symbol,
                    timestamp=datetime.utcnow()
                ).model_dump()
            )
        
        success = scraper_manager.invalidate_symbol_cache(symbol)
        
        return {
            "message": f"Cache invalidation for {symbol}: {'successful' if success else 'no data found'}",
            "symbol": symbol,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing cache for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Error clearing symbol cache",
                error_code="CACHE_ERROR",
                symbol=symbol,
                timestamp=datetime.utcnow()
            ).model_dump()
        )


@router.get("/health",
           summary="Health check endpoint",
           description="Check API health status")
async def health_check():
    """
    Health check endpoint to verify API is running.
    
    Returns:
        Health status information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "v1",
        "scrapers_available": list(scraper_manager.scrapers.keys()),
        "cache_enabled": scraper_manager.use_cache
    }
