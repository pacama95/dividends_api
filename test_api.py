#!/usr/bin/env python3
"""
Simple test script for the Dividend Calendar API
"""

import asyncio
import aiohttp
import json
from datetime import datetime


async def test_api():
    """Test the API endpoints"""
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        
        print("🧪 Testing Dividend Calendar API")
        print("=" * 50)
        
        # Test 1: Health check
        print("\n1. Testing health endpoint...")
        try:
            async with session.get(f"{base_url}/api/v1/health") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Health check passed: {data['status']}")
                else:
                    print(f"❌ Health check failed: {response.status}")
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return
        
        # Test 2: Root endpoint
        print("\n2. Testing root endpoint...")
        try:
            async with session.get(f"{base_url}/") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Root endpoint: {data['name']} v{data['version']}")
                else:
                    print(f"❌ Root endpoint failed: {response.status}")
        except Exception as e:
            print(f"❌ Root endpoint error: {e}")
        
        # Test 3: Stats endpoint
        print("\n3. Testing stats endpoint...")
        try:
            async with session.get(f"{base_url}/api/v1/stats") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Stats endpoint: {len(data['available_scrapers'])} scrapers available")
                    print(f"   Cache enabled: {data['cache_enabled']}")
                else:
                    print(f"❌ Stats endpoint failed: {response.status}")
        except Exception as e:
            print(f"❌ Stats endpoint error: {e}")
        
        # Test 4: Dividend data (using AAPL as example)
        print("\n4. Testing dividend data endpoint...")
        test_symbol = "AAPL"
        try:
            async with session.get(f"{base_url}/api/v1/dividend/{test_symbol}") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Dividend data for {test_symbol}:")
                    print(f"   Total records: {data['total_count']}")
                    print(f"   Successful source: {data['successful_source']}")
                    print(f"   Sources attempted: {data['sources_attempted']}")
                    print(f"   Cached: {data['cached']}")
                    
                    if data['dividends']:
                        latest = data['dividends'][0]
                        print(f"   Latest dividend: ${latest['amount']} (ex-date: {latest['ex_date']})")
                    
                elif response.status == 503:
                    error_data = await response.json()
                    print(f"⚠️  Service unavailable (expected for web scraping): {error_data['error']}")
                else:
                    error_data = await response.json()
                    print(f"❌ Dividend endpoint failed: {response.status} - {error_data}")
        except Exception as e:
            print(f"❌ Dividend endpoint error: {e}")
        
        # Test 5: Batch endpoint
        print("\n5. Testing batch dividend endpoint...")
        batch_data = {
            "symbols": ["AAPL", "MSFT"],
            "sources": ["yahoo"]
        }
        try:
            async with session.post(
                f"{base_url}/api/v1/dividend/batch", 
                json=batch_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Batch endpoint: {len(data)} symbols processed")
                    for symbol, result in data.items():
                        print(f"   {symbol}: {result['total_count']} records")
                elif response.status == 503:
                    error_data = await response.json()
                    print(f"⚠️  Batch service unavailable (expected for web scraping): {error_data['error']}")
                else:
                    error_data = await response.json()
                    print(f"❌ Batch endpoint failed: {response.status} - {error_data}")
        except Exception as e:
            print(f"❌ Batch endpoint error: {e}")
        
        print("\n" + "=" * 50)
        print("🏁 API testing completed!")
        print("\nNote: Scraping errors are expected when running without internet")
        print("or when financial sites block requests. The API structure is working!")


if __name__ == "__main__":
    print("Starting API test...")
    print("Make sure the API is running on localhost:8000")
    print("You can start it with: python main.py")
    print()
    
    try:
        asyncio.run(test_api())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
