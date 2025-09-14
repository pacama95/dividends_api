"""
Lazy imports for cold start optimization
"""
import importlib
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)

# Cache for already imported modules
_import_cache: Dict[str, Any] = {}

def lazy_import(module_name: str, attribute: str = None):
    """Lazy import modules only when needed"""
    cache_key = f"{module_name}.{attribute}" if attribute else module_name
    
    if cache_key in _import_cache:
        return _import_cache[cache_key]
    
    try:
        module = importlib.import_module(module_name)
        result = getattr(module, attribute) if attribute else module
        _import_cache[cache_key] = result
        logger.debug(f"Lazy imported: {cache_key}")
        return result
    except ImportError as e:
        logger.error(f"Failed to import {cache_key}: {e}")
        raise

# Heavy imports that should be lazy-loaded
def get_yfinance():
    """Get yfinance only when needed (heavy import with pandas/numpy)"""
    return lazy_import('yfinance')

def get_pandas():
    """Get pandas only when needed"""
    return lazy_import('pandas')

def get_beautifulsoup():
    """Get BeautifulSoup only when needed"""
    return lazy_import('bs4', 'BeautifulSoup')

def get_aiohttp():
    """Get aiohttp only when needed"""
    return lazy_import('aiohttp')
