#!/bin/bash
# Script to rebuild and restart the trading system

echo "=== Restarting MRHA Trading System ==="
echo "Stopping container..."
docker-compose down

echo "Rebuilding container..."
docker-compose build

echo "Starting container..."
docker-compose up -d

echo "Container started. Check logs with: docker-compose logs -f"