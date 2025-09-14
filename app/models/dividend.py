from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class DividendType(str, Enum):
    REGULAR = "regular"
    SPECIAL = "special"
    INTERIM = "interim"
    FINAL = "final"


class DividendData(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol")
    company_name: Optional[str] = Field(None, description="Company name")
    ex_date: Optional[datetime] = Field(None, description="Ex-dividend date")
    record_date: Optional[datetime] = Field(None, description="Record date")
    pay_date: Optional[datetime] = Field(None, description="Payment date")
    announcement_date: Optional[datetime] = Field(None, description="Announcement date")
    amount: Optional[float] = Field(None, description="Dividend amount per share")
    currency: str = Field(default="USD", description="Currency of dividend payment")
    dividend_type: Optional[DividendType] = Field(None, description="Type of dividend")
    frequency: Optional[str] = Field(None, description="Dividend frequency (quarterly, annual, etc.)")
    yield_percentage: Optional[float] = Field(None, description="Current dividend yield percentage")
    source: str = Field(..., description="Data source (yahoo, marketwatch, investing)")
    scraped_at: datetime = Field(default_factory=datetime.utcnow, description="When data was scraped")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class DividendCalendarResponse(BaseModel):
    symbol: str = Field(..., description="Stock ticker symbol")
    dividends: List[DividendData] = Field(default_factory=list, description="List of dividend records")
    total_count: int = Field(0, description="Total number of dividend records found")
    cached: bool = Field(False, description="Whether data was served from cache")
    cache_expires_at: Optional[datetime] = Field(None, description="When cached data expires")
    sources_attempted: List[str] = Field(default_factory=list, description="List of sources that were attempted")
    successful_source: Optional[str] = Field(None, description="Source that provided the data")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        
    def model_dump(self, **kwargs):
        """Override model_dump to ensure proper datetime serialization"""
        data = super().model_dump(**kwargs)
        
        # Ensure datetime fields are properly serialized
        if data.get('cache_expires_at'):
            data['cache_expires_at'] = data['cache_expires_at'].isoformat() if isinstance(data['cache_expires_at'], datetime) else data['cache_expires_at']
        
        # Process dividends list
        if data.get('dividends'):
            for dividend in data['dividends']:
                for field in ['ex_date', 'record_date', 'pay_date', 'announcement_date', 'scraped_at']:
                    if dividend.get(field) and isinstance(dividend[field], datetime):
                        dividend[field] = dividend[field].isoformat()
        
        return data


class BatchDividendRequest(BaseModel):
    symbols: List[str] = Field(..., description="List of stock ticker symbols", min_items=1, max_items=50)
    sources: Optional[List[str]] = Field(None, description="Preferred data sources")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")
    symbol: Optional[str] = Field(None, description="Stock ticker symbol if applicable")
    sources_attempted: List[str] = Field(default_factory=list, description="Sources that were attempted")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
