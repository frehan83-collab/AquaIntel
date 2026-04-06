#!/bin/bash
# FishIntel Deployment Script
# Usage: ./deploy.sh [server-ip]

set -e

SERVER=${1:-"your-server-ip"}

echo "=== FishIntel Deployment ==="
echo "Server: $SERVER"
echo ""

# 1. Check .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in credentials."
    exit 1
fi

# 2. Build Docker images
echo "Building Docker images..."
docker compose build

# 3. If deploying to remote server
if [ "$SERVER" != "localhost" ] && [ "$SERVER" != "your-server-ip" ]; then
    echo "Pushing to server $SERVER..."
    # Save images
    docker save fishintel-fishintel fishintel-frontend | gzip > /tmp/fishintel-images.tar.gz

    # Copy to server
    scp /tmp/fishintel-images.tar.gz $SERVER:/tmp/
    scp docker-compose.yml $SERVER:~/fishintel/
    scp nginx.conf $SERVER:~/fishintel/
    scp .env $SERVER:~/fishintel/

    # Load and start on server
    ssh $SERVER "cd ~/fishintel && docker load < /tmp/fishintel-images.tar.gz && docker compose up -d"

    echo "Deployed to $SERVER!"
    echo "Frontend: http://$SERVER"
    echo "API: http://$SERVER/api/health"
else
    # Local deployment
    echo "Starting locally..."
    docker compose up -d

    echo ""
    echo "=== FishIntel Running ==="
    echo "Frontend:  http://localhost:3000"
    echo "API:       http://localhost:8000/api/health"
    echo "Landing:   http://localhost:3000/landing"
    echo "Login:     http://localhost:3000/login"
    echo ""
    echo "Logs: docker compose logs -f"
    echo "Stop: docker compose down"
fi
