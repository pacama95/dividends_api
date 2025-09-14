# Dividend Calendar API

A FastAPI-based service for retrieving dividend calendar data from multiple financial data sources with caching and fallback mechanisms.

## Features

- **Multiple Data Sources**: Scrapes data from Yahoo Finance and MarketWatch
- **Automatic Fallback**: If one source fails, automatically tries others
- **Intelligent Caching**: Caches results with configurable TTL to reduce scraping load
- **Batch Processing**: Support for querying multiple symbols concurrently
- **Rate Limiting**: Built-in rate limiting to respect source websites
- **Comprehensive Logging**: Detailed logging and error tracking
- **Performance Monitoring**: Built-in statistics and health monitoring

## Local Development Setup

### Prerequisites

- Python 3.11+ (tested with Python 3.13)
- Git

### Installation & Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd dividens_api
```

2. **Create and activate virtual environment:**
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Running the Application

#### Development Mode (with auto-reload)
```bash
# Using uvicorn directly
python main.py

# Or with uvicorn command
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### Production Mode (with Gunicorn)
```bash
# Using gunicorn with optimized settings
gunicorn main:app -c gunicorn.conf.py

# Or with custom port
PORT=8000 gunicorn main:app -c gunicorn.conf.py
```

The API will be available at `http://localhost:8000`

### Testing the Local Setup

1. **Health Check:**
```bash
curl "http://localhost:8000/api/v1/health"
```

2. **Test Yahoo Finance (Historical Data):**
```bash
# Get comprehensive historical dividend data
curl "http://localhost:8000/api/v1/dividend/AAPL?sources=yahoo"

# Should return 80+ historical records
curl "http://localhost:8000/api/v1/dividend/MSFT?sources=yahoo"
```

3. **Test Multi-Source Fallback:**
```bash
# Uses Yahoo first, falls back to MarketWatch if needed
curl "http://localhost:8000/api/v1/dividend/TSLA"
```

4. **Test Batch Processing:**
```bash
curl -X POST "http://localhost:8000/api/v1/dividend/batch" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "MSFT", "GOOGL"]}'
```

### Environment Variables

Set these environment variables for customization:

```bash
export LOG_LEVEL="INFO"          # DEBUG, INFO, WARNING, ERROR
export PORT="8000"               # Server port
export HOST="0.0.0.0"           # Server host
export WORKERS="1"              # Number of workers (for production)
```

### Development Tips

- **Yahoo Finance works better locally** than in Docker containers
- **Historical data**: Yahoo provides 80+ records vs MarketWatch's 1 record
- **Auto-reload**: Use `python main.py` for development with auto-reload
- **Production testing**: Use gunicorn to test production-like performance
- **Logs**: Check console output for detailed scraping logs

### Local vs Docker Comparison

| Feature | Local Development | Docker |
|---------|------------------|---------|
| **Yahoo Finance** | ✅ Works (80+ records) | ❌ Blocked (rate limited) |
| **MarketWatch** | ✅ Works (1 record) | ✅ Works (1 record) |
| **Setup Speed** | Fast | Slower (build time) |
| **Development** | Auto-reload | Manual rebuilds |
| **Production** | Use gunicorn | Optimized container |

## Docker Setup

### Quick Start with Docker

1. **Build the Docker image:**
```bash
docker build -t dividend-api .
```

2. **Run the container:**
```bash
docker run -d --name dividend-api-test -p 8000:8000 -e PORT=8000 -e LOG_LEVEL=INFO dividend-api
```

3. **Test the API:**
```bash
curl "http://localhost:8000/api/v1/health"
```

### Docker Testing Guide

#### Build and Run
```bash
# Build the optimized Docker image
docker build -t dividend-api .

# Run container with environment variables
docker run -d \
  --name dividend-api-test \
  -p 8000:8000 \
  -e PORT=8000 \
  -e LOG_LEVEL=DEBUG \
  dividend-api

# Check container status
docker ps
```

#### Test API Endpoints
```bash
# Health check
curl "http://localhost:8000/api/v1/health"

# Root endpoint
curl "http://localhost:8000/"

# Get dividend data
curl "http://localhost:8000/api/v1/dividend/AAPL"

# Performance stats
curl "http://localhost:8000/api/v1/stats"

# Batch request
curl -X POST "http://localhost:8000/api/v1/dividend/batch" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "MSFT", "GOOGL"]}'
```

#### Monitor Container
```bash
# View logs in real-time
docker logs -f dividend-api-test

# Check resource usage
docker stats dividend-api-test

# Inspect container details
docker inspect dividend-api-test
```

#### Cleanup
```bash
# Stop and remove container
docker stop dividend-api-test
docker rm dividend-api-test

# Remove image (optional)
docker rmi dividend-api
```

### Docker Optimization Features

This Docker setup is optimized for production deployment:

- **Fast Cold Starts**: Optimized layer caching and minimal image size
- **Production Web Server**: Uses Gunicorn with Uvicorn workers
- **Health Checks**: Built-in health monitoring for container orchestration
- **Security**: Runs as non-root user
- **Environment Variables**: Configurable via environment variables
- **Cloud Ready**: Compatible with Railway, AWS, GCP, Azure, and other cloud providers

### Cloud Deployment

The Docker container is ready for deployment on:
- **AWS ECS/Fargate**: Container orchestration
- **Google Cloud Run**: Serverless containers  
- **Azure Container Instances**: Managed containers
- **Kubernetes**: Full orchestration support

## Railway Deployment (Recommended)

Railway deployment using **Nixpacks** (no Docker) provides the best performance for this API, especially for Yahoo Finance historical data.

### Why Railway + Nixpacks?

- ✅ **Yahoo Finance works perfectly** (80+ historical records)
- ✅ **Faster cold starts** than Docker
- ✅ **Automatic scaling** and port management
- ✅ **No Docker build overhead**
- ✅ **Optimized for Python applications**

### Deployment Steps

1. **Prepare your repository:**
```bash
# Ensure all files are committed
git add .
git commit -m "Add Railway deployment configuration"
git push origin main
```

2. **Railway Configuration Files:**

The repository includes these Railway-optimized files:
- `railway.toml` - Railway deployment configuration
- `gunicorn.conf.py` - Production server settings
- `Procfile` - Alternative startup command
- `runtime.txt` - Python version specification
- `start.sh` - Production startup script

3. **Deploy to Railway:**
- Connect your GitHub repository to Railway
- Railway auto-detects Python and uses Nixpacks
- Set environment variables (optional):
  - `LOG_LEVEL=INFO`
  - Railway automatically sets `PORT`

4. **Verify Deployment:**
```bash
# Test your deployed API
curl "https://your-app.railway.app/api/v1/health"

# Test historical data (Yahoo Finance works!)
curl "https://your-app.railway.app/api/v1/dividend/AAPL?sources=yahoo"
```

### Railway Environment Variables

Set these in Railway dashboard:

| Variable | Value | Description |
|----------|-------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `PYTHONUNBUFFERED` | `1` | Real-time logging |
| `PYTHONDONTWRITEBYTECODE` | `1` | Skip .pyc files |

### Railway vs Docker Performance

| Aspect | Railway (Nixpacks) | Docker |
|--------|-------------------|---------|
| **Yahoo Finance** | ✅ 80+ records | ❌ Rate limited |
| **Cold Start** | ~2-3 seconds | ~5-7 seconds |
| **Build Time** | ~30-60 seconds | ~2-3 minutes |
| **Memory Usage** | Optimized | Higher overhead |
| **Maintenance** | Zero config | Manual updates |

## API Documentation

Once the server is running, you can access:
- Interactive API docs: http://localhost:8000/docs
- ReDoc documentation: http://localhost:8000/redoc

## API Endpoints

### Get Dividend Data for Single Symbol

```http
GET /api/v1/dividend/{symbol}
```

**Parameters:**
- `symbol` (required): Stock ticker symbol (e.g., AAPL, MSFT)
- `sources` (optional): Preferred data sources (yahoo, marketwatch)
- `use_cache` (optional): Whether to use cached data (default: true)

**Example:**
```bash
curl "http://localhost:8000/api/v1/dividend/AAPL"
curl "http://localhost:8000/api/v1/dividend/AAPL?sources=yahoo&sources=marketwatch"
```

### Get Dividend Data for Multiple Symbols

```http
POST /api/v1/dividend/batch
```

**Body:**
```json
{
  "symbols": ["AAPL", "MSFT", "GOOGL"],
  "sources": ["yahoo", "marketwatch"]
}
```

### Health Check

```http
GET /api/v1/health
```

### Performance Statistics

```http
GET /api/v1/stats
```

### Cache Management

```http
DELETE /api/v1/cache              # Clear all cache
DELETE /api/v1/cache/{symbol}     # Clear cache for specific symbol
```

## Configuration

The application can be configured using environment variables:

- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_FILE`: Path to log file (optional, logs to console by default)
- `HOST`: Server host (default: 0.0.0.0)
- `PORT`: Server port (default: 8000)
- `RELOAD`: Enable auto-reload for development (default: false)
- `WORKERS`: Number of worker processes (default: 1)

**Example:**
```bash
LOG_LEVEL=DEBUG PORT=8080 python main.py
```

## Data Sources

The API tries multiple sources in order of reliability:

1. **Yahoo Finance** - Primary source with comprehensive data
2. **MarketWatch** - Backup source with good coverage  

## Response Format

```json
{
  "symbol": "AAPL",
  "dividends": [
    {
      "symbol": "AAPL",
      "company_name": "Apple Inc.",
      "ex_date": "2024-02-09T00:00:00",
      "record_date": null,
      "pay_date": "2024-02-16T00:00:00",
      "announcement_date": null,
      "amount": 0.24,
      "currency": "USD",
      "dividend_type": null,
      "frequency": "quarterly",
      "yield_percentage": 0.52,
      "source": "yahoo",
      "scraped_at": "2024-01-15T10:30:00.123456"
    }
  ],
  "total_count": 1,
  "cached": false,
  "cache_expires_at": "2024-01-15T11:30:00.123456",
  "sources_attempted": ["yahoo"],
  "successful_source": "yahoo"
}
```

## Development

### Project Structure

```
dividens_api/
├── app/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py          # FastAPI routes
│   ├── cache/
│   │   ├── __init__.py
│   │   └── cache_manager.py   # Caching logic
│   ├── models/
│   │   ├── __init__.py
│   │   └── dividend.py        # Pydantic models
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base_scraper.py    # Base scraper class
│   │   ├── yahoo_scraper.py   # Yahoo Finance scraper
│   │   ├── marketwatch_scraper.py  # MarketWatch scraper
│   │   └── scraper_manager.py      # Scraper coordination
│   └── utils/
│       ├── __init__.py
│       ├── logging_config.py   # Logging configuration
│       └── error_handlers.py   # Error handling
├── main.py                     # FastAPI application
├── requirements.txt            # Dependencies
└── README.md                   # This file
```

### Adding New Scrapers

To add a new data source:

1. Create a new scraper class inheriting from `BaseScraper`
2. Implement the `scrape_dividend_data` method
3. Add the scraper to `ScraperManager.__init__`
4. Update the default priority list

### Testing

The API includes built-in health checks and statistics endpoints for monitoring:

- `/api/v1/health` - Basic health check
- `/api/v1/stats` - Performance statistics and scraper status

## Error Handling

The API provides detailed error responses with consistent formatting:

```json
{
  "error": "Error description",
  "error_code": "ERROR_CODE",
  "symbol": "AAPL",
  "sources_attempted": ["yahoo", "marketwatch"],
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

## Rate Limiting

Built-in rate limiting respects the rate limits of source websites:
- Yahoo Finance: 1 request per second
- MarketWatch: 1.5 requests per second  

## Caching

- Default TTL: 1 hour
- In-memory storage using `TTLCache`
- Thread-safe operations
- Configurable cache size and TTL

## License

© 2025 Pablo Cazorla. All rights reserved.
This code is proprietary and confidential.

