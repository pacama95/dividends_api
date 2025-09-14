#!/bin/bash

# Dividend Calendar API Startup Script for Railway

echo "🚀 Starting Dividend Calendar API on Railway..."

# Set default environment variables if not provided
export PORT=${PORT:-8000}
export LOG_LEVEL=${LOG_LEVEL:-INFO}

echo "📋 Configuration:"
echo "  PORT: $PORT"
echo "  LOG_LEVEL: $LOG_LEVEL"
echo "  PYTHONPATH: $PYTHONPATH"

# Create logs directory if it doesn't exist (Railway has persistent storage)
mkdir -p logs

# Start the application with gunicorn for production
echo "🎯 Starting FastAPI application with gunicorn..."
exec gunicorn main:app -c gunicorn.conf.py
