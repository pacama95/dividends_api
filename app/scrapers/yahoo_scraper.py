import logging
import asyncio
import requests
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
# Lazy import heavy dependencies for cold start optimization
# import yfinance as yf  # Heavy import - loaded lazily
# import pandas as pd    # Heavy import - loaded lazily
from app.scrapers.base_scraper import BaseScraper, ScraperError, DataNotFoundError, RateLimitError
from app.models.dividend import DividendData, DividendCalendarResponse, DividendType
from app.utils.lazy_imports import get_yfinance, get_pandas

logger = logging.getLogger(__name__)


class YahooFinanceScraper(BaseScraper):
    """Scraper for Yahoo Finance dividend data using yfinance library"""
    
    def __init__(self):
        super().__init__(
            name="yahoo",
            base_url="https://finance.yahoo.com",
            rate_limit_delay=1.0
        )
        # Configure session with better headers for Docker environments
        self._setup_session()
    
    def _setup_session(self):
        """Set up requests session with headers that work better in Docker"""
        try:
            # Create a session with proper headers to avoid blocking
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })
            
            # Configure yfinance to use our session
            yf.pdr_override()  # Override pandas datareader with yfinance
            
            # Try to configure the session for yfinance
            if hasattr(yf, '_SHARED_'):
                yf._SHARED_.session = session
                logger.info("Configured yfinance with custom session for Docker compatibility")
            
        except Exception as e:
            logger.warning(f"Could not configure custom session: {e}, using default yfinance session")
    
    async def scrape_dividend_data(self, symbol: str) -> DividendCalendarResponse:
        """
        Scrape dividend data from Yahoo Finance using yfinance
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            DividendCalendarResponse with scraped data
        """
        symbol = self._validate_symbol(symbol)
        logger.info(f"Fetching dividend data from Yahoo Finance for symbol: {symbol}")
        
        try:
            # Use asyncio.to_thread to run the synchronous yfinance code in a thread pool
            dividends = await asyncio.to_thread(self._fetch_dividends_sync, symbol)
            
            response = DividendCalendarResponse(
                symbol=symbol,
                dividends=dividends,
                total_count=len(dividends),
                sources_attempted=["yahoo"],
                successful_source="yahoo" if dividends else None
            )
            
            logger.info(f"Successfully fetched {len(dividends)} dividend records for {symbol}")
            return response
            
        except Exception as e:
            logger.error(f"Error fetching dividend data from Yahoo Finance for {symbol}: {e}")
            raise ScraperError(f"Failed to fetch Yahoo Finance data: {e}")
    
    def _fetch_dividends_sync(self, symbol: str) -> List[DividendData]:
        """
        Synchronous method to fetch dividends using yfinance
        This runs in a separate thread to avoid blocking the async event loop
        """
        dividends = []
        max_retries = 3
        
        try:
            for attempt in range(max_retries):
                try:
                    # Lazy load yfinance only when needed (saves ~1s on cold start)
                    yf = get_yfinance()
                    
                    session = requests.Session()
                    session.headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    })
                    # Create ticker object with retry logic
                    ticker = yf.Ticker(symbol)
                    
                    # Get company info for company name
                    company_name = self._get_company_name(ticker, symbol)
                    
                    # Get dividend data with timeout and retries
                    # yfinance returns dividends as a pandas Series with dates as index
                    ticker.session = session
                    dividend_data = ticker.dividends
                    
                    # Break out of retry loop if successful
                    break
                    
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed for {symbol}: {e}")
                    if attempt == max_retries - 1:
                        logger.error(f"All {max_retries} attempts failed for {symbol}")
                        raise ScraperError(f"Failed to fetch data after {max_retries} attempts: {e}")
                    
                    # Wait before retry (exponential backoff)
                    import time
                    time.sleep(2 ** attempt)
                    continue
            
            # Check if dividend_data is empty or None
            if dividend_data is None:
                logger.info(f"No dividend data found for {symbol} (None returned)")
                return dividends
            
            # Handle both pandas Series and other types
            if hasattr(dividend_data, 'empty'):
                # It's a pandas Series
                if dividend_data.empty:
                    logger.info(f"No dividend data found for {symbol} (empty Series)")
                    return dividends
            elif isinstance(dividend_data, (list, tuple)):
                # It's a list or tuple
                if len(dividend_data) == 0:
                    logger.info(f"No dividend data found for {symbol} (empty list)")
                    return dividends
            elif hasattr(dividend_data, '__len__'):
                # Has length method
                if len(dividend_data) == 0:
                    logger.info(f"No dividend data found for {symbol} (empty collection)")
                    return dividends
            
            # Convert pandas Series to our DividendData objects
            for date, amount in dividend_data.items():
                try:
                    # Convert pandas timestamp to datetime
                    if hasattr(date, 'to_pydatetime'):
                        ex_date = date.to_pydatetime()
                    else:
                        # Lazy load pandas only when needed
                        pd = get_pandas()
                        ex_date = pd.to_datetime(date).to_pydatetime()
                    
                    # Create dividend data object
                    dividend = DividendData(
                        symbol=symbol,
                        company_name=company_name,
                        ex_date=ex_date,
                        amount=float(amount),
                        currency="USD",
                        source="yahoo",
                        scraped_at=datetime.utcnow()
                    )
                    
                    dividends.append(dividend)
                    
                except Exception as e:
                    logger.warning(f"Error processing dividend entry for {symbol}: {e}")
                    continue
            
            # Sort dividends by ex_date in descending order (most recent first)
            dividends.sort(key=lambda x: x.ex_date or datetime.min, reverse=True)
            
            # Get additional info if available
            dividends = self._enrich_dividend_data(ticker, dividends, symbol)
            
            logger.info(f"Processed {len(dividends)} dividend records for {symbol}")
            return dividends
            
        except Exception as e:
            logger.error(f"Error in _fetch_dividends_sync for {symbol}: {e}")
            raise ScraperError(f"yfinance error: {e}")
    
    def _get_company_name(self, ticker, symbol: str) -> Optional[str]:
        """Extract company name from ticker info"""
        try:
            info = ticker.info
            
            # Check if info is empty or contains errors
            if not info or 'error' in str(info):
                logger.debug(f"No company info available for {symbol}")
                return None
            
            # Try different fields for company name
            name_fields = ['longName', 'shortName', 'displayName', 'companyName']
            
            for field in name_fields:
                if field in info and info[field]:
                    company_name = str(info[field]).strip()
                    if company_name and company_name != symbol:
                        return company_name
            
            return None
            
        except Exception as e:
            # Don't log rate limit errors as warnings since they're common
            if "429" in str(e) or "Too Many Requests" in str(e):
                logger.debug(f"Rate limited when getting company name for {symbol}")
            else:
                logger.warning(f"Could not extract company name for {symbol}: {e}")
            return None
    
    def _enrich_dividend_data(self, ticker, dividends: List[DividendData], symbol: str) -> List[DividendData]:
        """Enrich dividend data with additional information from ticker info"""
        try:
            info = ticker.info
            
            # Skip enrichment if we have no info or errors
            if not info or 'error' in str(info):
                logger.debug(f"Skipping dividend enrichment for {symbol} - no ticker info")
                return dividends
            
            # Extract additional dividend information
            dividend_yield = info.get('dividendYield')
            dividend_rate = info.get('dividendRate')
            ex_dividend_date = info.get('exDividendDate')
            payout_ratio = info.get('payoutRatio')
            
            # Convert dividend yield from decimal to percentage
            if dividend_yield is not None:
                dividend_yield = float(dividend_yield) * 100
            
            # Try to determine dividend frequency
            frequency = self._determine_dividend_frequency(dividends)
            
            # Enrich the most recent dividends with additional data
            for i, dividend in enumerate(dividends[:5]):  # Only enrich last 5 dividends
                if dividend_yield is not None:
                    dividend.yield_percentage = dividend_yield
                    
                if frequency:
                    dividend.frequency = frequency
                    
                # For the most recent dividend, add ex-dividend date from info if available
                if i == 0 and ex_dividend_date:
                    try:
                        # ex_dividend_date might be a timestamp
                        if isinstance(ex_dividend_date, (int, float)):
                            ex_date_from_info = datetime.fromtimestamp(ex_dividend_date)
                            # Only use if it's more recent than what we have
                            if not dividend.ex_date or ex_date_from_info > dividend.ex_date:
                                dividend.ex_date = ex_date_from_info
                    except Exception as e:
                        logger.debug(f"Could not parse ex-dividend date from info: {e}")
            
        except Exception as e:
            logger.warning(f"Error enriching dividend data for {symbol}: {e}")
        
        return dividends
    
    def _determine_dividend_frequency(self, dividends: List[DividendData]) -> Optional[str]:
        """Determine dividend frequency based on historical data"""
        try:
            if len(dividends) < 2:
                return None
            
            # Calculate time differences between dividends
            intervals = []
            for i in range(len(dividends) - 1):
                if dividends[i].ex_date and dividends[i + 1].ex_date:
                    interval = dividends[i].ex_date - dividends[i + 1].ex_date
                    intervals.append(interval.days)
            
            if not intervals:
                return None
            
            # Calculate average interval
            avg_interval = sum(intervals) / len(intervals)
            
            # Determine frequency based on average interval
            if 80 <= avg_interval <= 100:  # Around 3 months
                return "quarterly"
            elif 160 <= avg_interval <= 200:  # Around 6 months
                return "semi-annual"
            elif 350 <= avg_interval <= 380:  # Around 1 year
                return "annual"
            elif 25 <= avg_interval <= 35:  # Around 1 month
                return "monthly"
            else:
                return "irregular"
                
        except Exception as e:
            logger.debug(f"Could not determine dividend frequency: {e}")
            return None
    
    async def get_ticker_info(self, symbol: str) -> Dict[str, Any]:
        """
        Get general ticker information (useful for debugging)
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dictionary with ticker information
        """
        try:
            ticker = yf.Ticker(symbol)
            info = await asyncio.to_thread(lambda: ticker.info)
            
            # Extract relevant dividend-related information
            dividend_info = {
                'symbol': symbol,
                'company_name': info.get('longName') or info.get('shortName'),
                'sector': info.get('sector'),
                'industry': info.get('industry'),
                'dividend_rate': info.get('dividendRate'),
                'dividend_yield': info.get('dividendYield'),
                'ex_dividend_date': info.get('exDividendDate'),
                'payout_ratio': info.get('payoutRatio'),
                'last_dividend_value': info.get('lastDividendValue'),
                'last_dividend_date': info.get('lastDividendDate'),
                'currency': info.get('currency', 'USD')
            }
            
            return dividend_info
            
        except Exception as e:
            logger.error(f"Error getting ticker info for {symbol}: {e}")
            return {'error': str(e), 'symbol': symbol}
    
    async def get_dividend_history(self, symbol: str, period: str = "2y") -> List[DividendData]:
        """
        Get dividend history for a specific period
        
        Args:
            symbol: Stock ticker symbol
            period: Period to fetch data for (1y, 2y, 5y, max)
            
        Returns:
            List of DividendData objects
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Fetch dividend data for specific period
            dividend_data = await asyncio.to_thread(
                lambda: ticker.dividends.loc[
                    ticker.dividends.index >= (datetime.now() - self._parse_period(period))
                ]
            )
            
            company_name = self._get_company_name(ticker, symbol)
            dividends = []
            
            for date, amount in dividend_data.items():
                try:
                    if hasattr(date, 'to_pydatetime'):
                        ex_date = date.to_pydatetime()
                    else:
                        # Lazy load pandas only when needed
                        pd = get_pandas()
                        ex_date = pd.to_datetime(date).to_pydatetime()
                    
                    dividend = DividendData(
                        symbol=symbol,
                        company_name=company_name,
                        ex_date=ex_date,
                        amount=float(amount),
                        currency="USD",
                        source="yahoo",
                        scraped_at=datetime.utcnow()
                    )
                    
                    dividends.append(dividend)
                    
                except Exception as e:
                    logger.warning(f"Error processing dividend entry: {e}")
                    continue
            
            return sorted(dividends, key=lambda x: x.ex_date or datetime.min, reverse=True)
            
        except Exception as e:
            logger.error(f"Error getting dividend history for {symbol}: {e}")
            raise ScraperError(f"Failed to get dividend history: {e}")
    
    def _parse_period(self, period: str) -> timedelta:
        """Parse period string into timedelta"""
        period_mapping = {
            '1y': timedelta(days=365),
            '2y': timedelta(days=730),
            '5y': timedelta(days=1825),
            '10y': timedelta(days=3650),
            'max': timedelta(days=36500)  # 100 years
        }
        
        return period_mapping.get(period, timedelta(days=730))  # Default to 2 years
