import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup, Tag
from app.scrapers.base_scraper import BaseScraper, ScraperError, DataNotFoundError
from app.models.dividend import DividendData, DividendCalendarResponse, DividendType

logger = logging.getLogger(__name__)


class MarketWatchScraper(BaseScraper):
    """Scraper for MarketWatch dividend data"""
    
    def __init__(self):
        super().__init__(
            name="marketwatch",
            base_url="https://www.marketwatch.com",
            rate_limit_delay=1.5  # Slightly higher delay for MarketWatch
        )
    
    async def scrape_dividend_data(self, symbol: str) -> DividendCalendarResponse:
        """
        Scrape dividend data from MarketWatch
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            DividendCalendarResponse with scraped data
        """
        symbol = self._validate_symbol(symbol)
        logger.info(f"Scraping MarketWatch for symbol: {symbol}")
        
        try:
            # MarketWatch has different URL patterns, try multiple approaches
            dividends = []
            
            # Approach 1: Try investing/stocks page for basic dividend info
            basic_dividends = await self._scrape_basic_dividend_info(symbol)
            if basic_dividends:
                dividends.extend(basic_dividends)
            
            # Approach 2: Try to find dividend history from quote page
            if not dividends:
                quote_dividends = await self._scrape_quote_page_dividends(symbol)
                if quote_dividends:
                    dividends.extend(quote_dividends)
            
            response = DividendCalendarResponse(
                symbol=symbol,
                dividends=dividends,
                total_count=len(dividends),
                sources_attempted=["marketwatch"],
                successful_source="marketwatch" if dividends else None
            )
            
            logger.info(f"Successfully scraped {len(dividends)} dividend records from MarketWatch for {symbol}")
            return response
            
        except Exception as e:
            logger.error(f"Error scraping MarketWatch for {symbol}: {e}")
            raise ScraperError(f"Failed to scrape MarketWatch: {e}")
    
    async def _scrape_basic_dividend_info(self, symbol: str) -> List[DividendData]:
        """Scrape basic dividend information from MarketWatch stock page"""
        dividends = []
        
        try:
            # MarketWatch stock overview page
            url = f"{self.base_url}/investing/stock/{symbol.lower()}"
            soup = await self._fetch_page(url)
            
            # Extract company name
            company_name = self._extract_company_name(soup, symbol)
            
            # Look for dividend information in various sections
            dividend_info = self._extract_dividend_overview(soup)
            
            if dividend_info.get('amount') and dividend_info['amount'] > 0:
                dividend = DividendData(
                    symbol=symbol,
                    company_name=company_name,
                    amount=dividend_info.get('amount'),
                    yield_percentage=dividend_info.get('yield'),
                    ex_date=dividend_info.get('ex_date'),
                    pay_date=dividend_info.get('pay_date'),
                    frequency=dividend_info.get('frequency'),
                    currency="USD",
                    source="marketwatch",
                    scraped_at=datetime.utcnow()
                )
                dividends.append(dividend)
            
        except Exception as e:
            logger.warning(f"Error scraping basic dividend info from MarketWatch: {e}")
        
        return dividends
    
    async def _scrape_quote_page_dividends(self, symbol: str) -> List[DividendData]:
        """Scrape dividend data from MarketWatch quote page"""
        dividends = []
        
        try:
            # Alternative URL format
            url = f"{self.base_url}/investing/stock/{symbol.lower()}/overview"
            soup = await self._fetch_page(url)
            
            # Extract company name
            company_name = self._extract_company_name(soup, symbol)
            
            # Look for key statistics or dividend section
            dividend_section = soup.find('section', class_=re.compile(r'dividend', re.IGNORECASE))
            if not dividend_section:
                # Look for key statistics
                stats_section = soup.find('div', class_=re.compile(r'key.*stat', re.IGNORECASE))
                if stats_section:
                    dividend_section = stats_section
            
            if dividend_section:
                dividend_data = self._parse_dividend_section(dividend_section, symbol, company_name)
                if dividend_data:
                    dividends.append(dividend_data)
            
        except Exception as e:
            logger.warning(f"Error scraping quote page dividends from MarketWatch: {e}")
        
        return dividends
    
    def _extract_company_name(self, soup: BeautifulSoup, symbol: str) -> Optional[str]:
        """Extract company name from MarketWatch page"""
        try:
            # Look for h1 or title with company name
            title_selectors = [
                'h1.company__name',
                'h1[data-module="CompanyName"]',
                'h1',
                '.company-header h1',
                '[data-module="NameAndPrice"] h1'
            ]
            
            for selector in title_selectors:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text().strip()
                    # Remove symbol if present
                    text = re.sub(f'\\s*\\({re.escape(symbol)}\\)\\s*', '', text, flags=re.IGNORECASE)
                    if text and len(text) > 2:
                        return text
            
        except Exception as e:
            logger.warning(f"Could not extract company name from MarketWatch: {e}")
        
        return None
    
    def _extract_dividend_overview(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract dividend overview information from the page"""
        dividend_info = {}
        
        try:
            # Look for dividend-related data in various sections
            dividend_keywords = ['dividend', 'yield', 'payout']
            
            # Search for dividend information in the page
            all_text_elements = soup.find_all(text=True)
            
            for i, text in enumerate(all_text_elements):
                if any(keyword in text.lower() for keyword in dividend_keywords):
                    # Check nearby elements for values
                    parent = text.parent if text.parent else None
                    if parent:
                        self._extract_dividend_values_from_element(parent, dividend_info)
            
            # Look for specific selectors that might contain dividend data
            dividend_selectors = [
                '.kv__item',
                '.data-module-body tr',
                '.table--key-values tr',
                '[data-module="KeyStats"] tr'
            ]
            
            for selector in dividend_selectors:
                elements = soup.select(selector)
                for element in elements:
                    self._extract_dividend_values_from_element(element, dividend_info)
            
        except Exception as e:
            logger.warning(f"Error extracting dividend overview: {e}")
        
        return dividend_info
    
    def _extract_dividend_values_from_element(self, element: Tag, dividend_info: Dict[str, Any]):
        """Extract dividend values from a specific element"""
        try:
            text = element.get_text().lower()
            
            # Look for dividend amount
            if 'dividend' in text and not dividend_info.get('amount'):
                amount_match = re.search(r'\$(\d+\.?\d*)', element.get_text())
                if amount_match:
                    dividend_info['amount'] = float(amount_match.group(1))
            
            # Look for dividend yield
            if 'yield' in text and not dividend_info.get('yield'):
                yield_match = re.search(r'(\d+\.?\d*)%', element.get_text())
                if yield_match:
                    dividend_info['yield'] = float(yield_match.group(1))
            
            # Look for ex-dividend date
            if 'ex-dividend' in text or 'ex dividend' in text:
                date_text = element.get_text()
                ex_date = self._extract_date_from_text(date_text)
                if ex_date:
                    dividend_info['ex_date'] = ex_date
            
            # Look for payment date
            if 'pay' in text and 'date' in text:
                date_text = element.get_text()
                pay_date = self._extract_date_from_text(date_text)
                if pay_date:
                    dividend_info['pay_date'] = pay_date
            
            # Look for frequency
            frequency_keywords = ['quarterly', 'annual', 'monthly', 'semi-annual']
            for freq in frequency_keywords:
                if freq in text:
                    dividend_info['frequency'] = freq
                    break
                    
        except Exception as e:
            logger.warning(f"Error extracting values from element: {e}")
    
    def _extract_date_from_text(self, text: str) -> Optional[datetime]:
        """Extract date from text using various patterns"""
        date_patterns = [
            r'(\w{3}\s+\d{1,2},?\s+\d{4})',  # Jan 15, 2024 or Jan 15 2024
            r'(\d{1,2}\/\d{1,2}\/\d{4})',     # 01/15/2024
            r'(\d{1,2}-\d{1,2}-\d{4})',       # 01-15-2024
            r'(\d{4}-\d{2}-\d{2})'            # 2024-01-15
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                parsed_date = self._parse_date(date_str)
                if parsed_date:
                    return parsed_date
        
        return None
    
    def _parse_dividend_section(self, section: Tag, symbol: str, company_name: Optional[str]) -> Optional[DividendData]:
        """Parse dividend information from a specific section"""
        try:
            dividend_info = {}
            
            # Extract all relevant information from the section
            self._extract_dividend_values_from_element(section, dividend_info)
            
            # Also check child elements
            for child in section.find_all(['td', 'span', 'div']):
                self._extract_dividend_values_from_element(child, dividend_info)
            
            if dividend_info.get('amount') and dividend_info['amount'] > 0:
                return DividendData(
                    symbol=symbol,
                    company_name=company_name,
                    amount=dividend_info.get('amount'),
                    yield_percentage=dividend_info.get('yield'),
                    ex_date=dividend_info.get('ex_date'),
                    pay_date=dividend_info.get('pay_date'),
                    frequency=dividend_info.get('frequency'),
                    currency="USD",
                    source="marketwatch",
                    scraped_at=datetime.utcnow()
                )
                
        except Exception as e:
            logger.warning(f"Error parsing dividend section: {e}")
        
        return None
