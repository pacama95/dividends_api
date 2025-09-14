import logging
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from datetime import datetime
from typing import Dict, Any

from app.models.dividend import ErrorResponse

logger = logging.getLogger('app.errors')


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions"""
    logger.warning(
        f"HTTP Exception - Path: {request.url.path} - "
        f"Status: {exc.status_code} - "
        f"Detail: {exc.detail}"
    )
    
    # If detail is already an ErrorResponse dict, use it
    if isinstance(exc.detail, dict) and 'error_code' in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    # Create standardized error response
    error_response = ErrorResponse(
        error=str(exc.detail),
        error_code="HTTP_ERROR",
        timestamp=datetime.utcnow()
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump()
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle validation errors"""
    logger.warning(
        f"Validation Error - Path: {request.url.path} - "
        f"Errors: {exc.errors()}"
    )
    
    # Format validation errors
    error_details = []
    for error in exc.errors():
        field = " -> ".join([str(loc) for loc in error['loc']])
        error_details.append(f"{field}: {error['msg']}")
    
    error_response = ErrorResponse(
        error=f"Validation failed: {'; '.join(error_details)}",
        error_code="VALIDATION_ERROR",
        timestamp=datetime.utcnow()
    )
    
    return JSONResponse(
        status_code=422,
        content=error_response.model_dump()
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions"""
    logger.error(
        f"Unexpected Error - Path: {request.url.path} - "
        f"Type: {type(exc).__name__} - "
        f"Message: {str(exc)}",
        exc_info=True
    )
    
    error_response = ErrorResponse(
        error="Internal server error",
        error_code="INTERNAL_ERROR",
        timestamp=datetime.utcnow()
    )
    
    return JSONResponse(
        status_code=500,
        content=error_response.model_dump()
    )


def setup_exception_handlers(app):
    """Set up exception handlers for the FastAPI app"""
    
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    
    logger.info("Exception handlers configured")


class ErrorTracker:
    """Track error statistics"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.recent_errors: list = []
        self.max_recent_errors = 100
    
    def record_error(self, error_code: str, error_message: str, context: Dict[str, Any] = None):
        """Record an error occurrence"""
        
        # Update error counts
        self.error_counts[error_code] = self.error_counts.get(error_code, 0) + 1
        
        # Add to recent errors
        error_record = {
            'timestamp': datetime.utcnow().isoformat(),
            'error_code': error_code,
            'error_message': error_message,
            'context': context or {}
        }
        
        self.recent_errors.append(error_record)
        
        # Limit recent errors list size
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors = self.recent_errors[-self.max_recent_errors:]
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        total_errors = sum(self.error_counts.values())
        
        return {
            'total_errors': total_errors,
            'error_counts_by_type': self.error_counts,
            'recent_errors_count': len(self.recent_errors),
            'recent_errors': self.recent_errors[-10:] if self.recent_errors else []  # Last 10 errors
        }


# Global error tracker instance
error_tracker = ErrorTracker()
