import logging
import asyncio
from typing import List, Optional, Dict, Type, Any
from datetime import datetime
from app.scrapers.base_scraper import BaseScraper, ScraperError, DataNotFoundError, RateLimitError
from app.scrapers.yahoo_scraper import YahooFinanceScraper
from app.scrapers.marketwatch_scraper import MarketWatchScraper
from app.models.dividend import DividendCalendarResponse
from app.cache.cache_manager import cache_manager

logger = logging.getLogger(__name__)


class ScraperManager:
    """Manages multiple scrapers with fallback logic and caching"""
    
    def __init__(self, use_cache: bool = True, cache_ttl: int = 3600):
        """
        Initialize scraper manager with lazy loading for cold start optimization
        
        Args:
            use_cache: Whether to use caching
            cache_ttl: Cache TTL in seconds
        """
        self.use_cache = use_cache
        self.cache_ttl = cache_ttl
        
        # Lazy initialization - don't create scrapers until needed
        self._scrapers = None
        self._scraper_stats = None
        
        # Default priority order (most reliable first)
        self.default_priority = ['yahoo', 'marketwatch']
        
        logger.info("ScraperManager initialized with lazy loading")
    
    @property
    def scrapers(self):
        """Lazy initialize scrapers on first access"""
        if self._scrapers is None:
            logger.info("Initializing scrapers on first use...")
            self._scrapers = {
                'yahoo': YahooFinanceScraper(),
                'marketwatch': MarketWatchScraper()
            }
            logger.info(f"Initialized {len(self._scrapers)} scrapers")
        return self._scrapers
    
    @property
    def scraper_stats(self):
        """Lazy initialize scraper stats"""
        if self._scraper_stats is None:
            self._scraper_stats = {
                name: {'success_count': 0, 'error_count': 0, 'last_success': None, 'last_error': None}
                for name in ['yahoo', 'marketwatch']
            }
        return self._scraper_stats
    
    async def get_dividend_data(self, 
                               symbol: str, 
                               preferred_sources: Optional[List[str]] = None,
                               max_concurrent: int = 2) -> DividendCalendarResponse:
        """
        Get dividend data for a symbol using multiple sources with fallback
        
        Args:
            symbol: Stock ticker symbol
            preferred_sources: List of preferred scraper sources (defaults to all)
            max_concurrent: Maximum number of concurrent scraper attempts
            
        Returns:
            DividendCalendarResponse with combined data from sources
        """
        symbol = symbol.upper().strip()
        logger.info(f"Getting dividend data for {symbol}")
        
        # Check cache first
        if self.use_cache:
            cached_data = cache_manager.get(symbol)
            if cached_data:
                logger.info(f"Returning cached data for {symbol}")
                return cached_data
        
        # Determine which sources to use
        sources_to_try = preferred_sources or self.default_priority
        sources_to_try = [src for src in sources_to_try if src in self.scrapers]
        
        if not sources_to_try:
            raise ScraperError("No valid scrapers specified")
        
        # Try sources with different strategies
        result = None
        sources_attempted = []
        
        # Strategy 1: Try sequential fallback (most reliable approach)
        result = await self._try_sequential_scraping(symbol, sources_to_try, sources_attempted)
        
        # Strategy 2: If sequential failed, try concurrent scraping for speed
        if not result or result.total_count == 0:
            logger.info(f"Sequential scraping failed for {symbol}, trying concurrent approach")
            result = await self._try_concurrent_scraping(symbol, sources_to_try, sources_attempted, max_concurrent)
        
        # Enhance result with metadata
        if result:
            result.sources_attempted = list(set(sources_attempted))
            
            # Cache the result if we got valid data
            if result.total_count > 0 and self.use_cache:
                cache_manager.set(symbol, result, ttl=self.cache_ttl)
                logger.info(f"Cached dividend data for {symbol}")
        else:
            # Return empty response if all sources failed
            result = DividendCalendarResponse(
                symbol=symbol,
                dividends=[],
                total_count=0,
                sources_attempted=sources_attempted,
                successful_source=None
            )
        
        return result
    
    async def _try_sequential_scraping(self, 
                                     symbol: str, 
                                     sources: List[str], 
                                     sources_attempted: List[str]) -> Optional[DividendCalendarResponse]:
        """Try scrapers sequentially until one succeeds"""
        
        for source_name in sources:
            if source_name not in self.scrapers:
                continue
                
            scraper = self.scrapers[source_name]
            sources_attempted.append(source_name)
            
            try:
                logger.info(f"Trying {source_name} for {symbol}")
                result = await scraper.scrape_dividend_data(symbol)
                
                if result and result.total_count > 0:
                    logger.info(f"Successfully scraped {result.total_count} records from {source_name}")
                    result.successful_source = source_name
                    self._update_scraper_stats(source_name, success=True)
                    return result
                else:
                    logger.warning(f"No data found using {source_name} for {symbol}")
                    
            except RateLimitError as e:
                logger.warning(f"Rate limit hit for {source_name}: {e}")
                self._update_scraper_stats(source_name, success=False, error=str(e))
                # Wait a bit before trying next source
                await asyncio.sleep(2)
                
            except ScraperError as e:
                logger.warning(f"Scraping failed for {source_name}: {e}")
                self._update_scraper_stats(source_name, success=False, error=str(e))
                
            except Exception as e:
                logger.error(f"Unexpected error with {source_name}: {e}")
                self._update_scraper_stats(source_name, success=False, error=str(e))
        
        return None
    
    async def _try_concurrent_scraping(self, 
                                     symbol: str, 
                                     sources: List[str], 
                                     sources_attempted: List[str],
                                     max_concurrent: int) -> Optional[DividendCalendarResponse]:
        """Try multiple scrapers concurrently"""
        
        # Filter out sources we already tried
        remaining_sources = [src for src in sources if src not in sources_attempted]
        if not remaining_sources:
            return None
        
        # Limit concurrent attempts
        sources_to_try = remaining_sources[:max_concurrent]
        
        # Create scraping tasks
        tasks = []
        for source_name in sources_to_try:
            if source_name in self.scrapers:
                scraper = self.scrapers[source_name]
                task = asyncio.create_task(self._scrape_with_timeout(scraper, symbol, source_name))
                tasks.append((source_name, task))
                sources_attempted.append(source_name)
        
        if not tasks:
            return None
        
        # Wait for first successful result or all to complete
        try:
            done, pending = await asyncio.wait(
                [task for _, task in tasks],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=30  # 30 second timeout
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
            
            # Check completed tasks for success
            for source_name, task in tasks:
                if task in done:
                    try:
                        result = await task
                        if result and result.total_count > 0:
                            logger.info(f"Concurrent scraping succeeded with {source_name}")
                            result.successful_source = source_name
                            self._update_scraper_stats(source_name, success=True)
                            return result
                    except Exception as e:
                        logger.warning(f"Concurrent task failed for {source_name}: {e}")
                        self._update_scraper_stats(source_name, success=False, error=str(e))
            
        except asyncio.TimeoutError:
            logger.warning("Concurrent scraping timed out")
            # Cancel all tasks
            for _, task in tasks:
                task.cancel()
        
        return None
    
    async def _scrape_with_timeout(self, scraper: BaseScraper, symbol: str, source_name: str, timeout: int = 15) -> Optional[DividendCalendarResponse]:
        """Scrape with timeout wrapper"""
        try:
            result = await asyncio.wait_for(scraper.scrape_dividend_data(symbol), timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Scraper {source_name} timed out for {symbol}")
            raise ScraperError(f"Timeout scraping {source_name}")
    
    def _update_scraper_stats(self, source_name: str, success: bool, error: Optional[str] = None):
        """Update scraper performance statistics"""
        if source_name not in self.scraper_stats:
            return
        
        stats = self.scraper_stats[source_name]
        
        if success:
            stats['success_count'] += 1
            stats['last_success'] = datetime.utcnow()
        else:
            stats['error_count'] += 1
            stats['last_error'] = datetime.utcnow()
            if error:
                stats['last_error_message'] = error
    
    async def get_multiple_symbols(self, 
                                 symbols: List[str], 
                                 preferred_sources: Optional[List[str]] = None) -> Dict[str, DividendCalendarResponse]:
        """
        Get dividend data for multiple symbols concurrently
        
        Args:
            symbols: List of stock ticker symbols
            preferred_sources: List of preferred scraper sources
            
        Returns:
            Dictionary mapping symbols to their dividend data
        """
        logger.info(f"Getting dividend data for {len(symbols)} symbols")
        
        # Create tasks for each symbol
        tasks = []
        for symbol in symbols:
            task = asyncio.create_task(self.get_dividend_data(symbol, preferred_sources))
            tasks.append((symbol, task))
        
        # Execute all tasks concurrently
        results = {}
        completed_tasks = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        for (symbol, _), result in zip(tasks, completed_tasks):
            if isinstance(result, Exception):
                logger.error(f"Error getting data for {symbol}: {result}")
                results[symbol] = DividendCalendarResponse(
                    symbol=symbol,
                    dividends=[],
                    total_count=0,
                    sources_attempted=[],
                    successful_source=None
                )
            else:
                results[symbol] = result
        
        return results
    
    def get_scraper_stats(self) -> Dict[str, Any]:
        """Get performance statistics for all scrapers"""
        stats = {
            'cache_enabled': self.use_cache,
            'cache_ttl': self.cache_ttl,
            'available_scrapers': list(self.scrapers.keys()),
            'default_priority': self.default_priority,
            'scraper_performance': {}
        }
        
        for name, scraper_stats in self.scraper_stats.items():
            total_requests = scraper_stats['success_count'] + scraper_stats['error_count']
            success_rate = (scraper_stats['success_count'] / total_requests * 100) if total_requests > 0 else 0
            
            stats['scraper_performance'][name] = {
                **scraper_stats,
                'total_requests': total_requests,
                'success_rate_percent': round(success_rate, 2)
            }
        
        # Add cache stats
        if self.use_cache:
            stats['cache_stats'] = cache_manager.get_cache_stats()
        
        return stats
    
    def clear_cache(self) -> int:
        """Clear all cached data"""
        if self.use_cache:
            return cache_manager.clear_all()
        return 0
    
    def invalidate_symbol_cache(self, symbol: str) -> bool:
        """Invalidate cache for a specific symbol"""
        if self.use_cache:
            return cache_manager.invalidate(symbol)
        return False


# Global scraper manager instance
scraper_manager = ScraperManager(use_cache=True, cache_ttl=3600)
