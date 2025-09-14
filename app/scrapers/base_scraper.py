import logging
import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import aiohttp
import requests
from bs4 import BeautifulSoup
import time
from app.models.dividend import DividendData, DividendCalendarResponse

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Base exception for scraper errors"""
    pass


class RateLimitError(ScraperError):
    """Exception raised when rate limit is exceeded"""
    pass


class DataNotFoundError(ScraperError):
    """Exception raised when no data is found for a symbol"""
    pass


class BaseScraper(ABC):
    """Base class for all dividend data scrapers"""
    
    def __init__(self, name: str, base_url: str, rate_limit_delay: float = 1.0):
        """
        Initialize base scraper
        
        Args:
            name: Name of the scraper (e.g., 'yahoo', 'marketwatch')
            base_url: Base URL for the data source
            rate_limit_delay: Delay between requests in seconds
        """
        self.name = name
        self.base_url = base_url
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time = 0
        
        # Default headers to appear more like a regular browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
    
    async def _respect_rate_limit(self):
        """Ensure rate limiting between requests"""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time
        
        if time_since_last_request < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    async def _fetch_page(self, url: str, params: Optional[Dict[str, Any]] = None) -> BeautifulSoup:
        """
        Fetch a page and return BeautifulSoup object
        
        Args:
            url: URL to fetch
            params: Optional URL parameters
            
        Returns:
            BeautifulSoup object of the page content
            
        Raises:
            ScraperError: If unable to fetch the page
        """
        await self._respect_rate_limit()
        
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                logger.debug(f"Fetching URL: {url}")
                
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 429:
                        raise RateLimitError(f"Rate limit exceeded for {self.name}")
                    
                    if response.status != 200:
                        raise ScraperError(f"HTTP {response.status} error fetching {url}")
                    
                    content = await response.text()
                    return BeautifulSoup(content, 'html.parser')
                    
        except aiohttp.ClientError as e:
            raise ScraperError(f"Network error fetching {url}: {e}")
        except Exception as e:
            raise ScraperError(f"Unexpected error fetching {url}: {e}")
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse date string into datetime object
        
        Args:
            date_str: Date string to parse
            
        Returns:
            datetime object or None if parsing fails
        """
        if not date_str or date_str.strip() == '':
            return None
        
        # Common date formats to try
        date_formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%b %d, %Y",
            "%B %d, %Y",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y %H:%M:%S"
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def _parse_amount(self, amount_str: Optional[str]) -> Optional[float]:
        """
        Parse amount string into float
        
        Args:
            amount_str: Amount string to parse (e.g., "$1.25", "1.25")
            
        Returns:
            Float value or None if parsing fails
        """
        if not amount_str or amount_str.strip() == '':
            return None
        
        try:
            # Remove common currency symbols and whitespace
            cleaned = amount_str.strip().replace('$', '').replace(',', '').replace(' ', '')
            return float(cleaned)
        except (ValueError, TypeError):
            logger.warning(f"Could not parse amount: {amount_str}")
            return None
    
    def _validate_symbol(self, symbol: str) -> str:
        """
        Validate and normalize stock symbol
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Normalized symbol
            
        Raises:
            ScraperError: If symbol is invalid
        """
        if not symbol or not isinstance(symbol, str):
            raise ScraperError("Invalid symbol: must be a non-empty string")
        
        # Basic validation - remove whitespace and convert to uppercase
        normalized = symbol.strip().upper()
        
        if not normalized or len(normalized) > 10:
            raise ScraperError(f"Invalid symbol format: {symbol}")
        
        return normalized
    
    @abstractmethod
    async def scrape_dividend_data(self, symbol: str) -> DividendCalendarResponse:
        """
        Scrape dividend data for a given symbol
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            DividendCalendarResponse with scraped data
            
        Raises:
            ScraperError: If unable to scrape data
        """
        pass
    
    def get_scraper_info(self) -> Dict[str, Any]:
        """
        Get information about this scraper
        
        Returns:
            Dictionary with scraper information
        """
        return {
            "name": self.name,
            "base_url": self.base_url,
            "rate_limit_delay": self.rate_limit_delay,
            "last_request_time": self._last_request_time
        }
