#!/bin/bash
# Docker specific run script for EC2 deployments

# Set timezone to KST
export TZ=Asia/Seoul

# Logging setup
LOG_DIR="logs"
mkdir -p $LOG_DIR
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/docker_${TIMESTAMP}.log"

# Function to log messages
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Check environment file
log "INFO" "Checking environment file..."
if [ ! -f ".env" ]; then
    log "ERROR" ".env file not found. Please create it from .env.example"
    exit 1
fi

# Check Docker and Docker Compose
log "INFO" "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    log "ERROR" "Docker not found. Please install Docker"
    exit 1
fi

log "INFO" "Checking Docker Compose installation..."
if ! command -v docker-compose &> /dev/null; then
    log "WARNING" "Docker Compose not found. Attempting to use Docker Compose plugin..."
    if ! docker compose version &> /dev/null; then
        log "ERROR" "Docker Compose not found. Please install Docker Compose"
        exit 1
    else
        DOCKER_COMPOSE="docker compose"
    fi
else
    DOCKER_COMPOSE="docker-compose"
fi

# Check if container is already running
CONTAINER_NAME="mrha_trading_bot"
if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    log "WARNING" "$CONTAINER_NAME container is already running."
    read -p "Do you want to stop it and restart? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log "INFO" "Stopping existing container..."
        docker stop $CONTAINER_NAME
        docker rm $CONTAINER_NAME
    else
        log "INFO" "Exiting without restarting container."
        exit 0
    fi
fi

# Build and start the container
log "INFO" "Building and starting Docker container..."
$DOCKER_COMPOSE build
if [ $? -ne 0 ]; then
    log "ERROR" "Docker build failed."
    exit 1
fi

log "INFO" "Starting container in detached mode..."
$DOCKER_COMPOSE up -d
if [ $? -ne 0 ]; then
    log "ERROR" "Docker Compose up failed."
    exit 1
fi

# Monitor logs
log "INFO" "Container started successfully. Monitoring logs..."
$DOCKER_COMPOSE logs -f

log "INFO" "Docker deployment complete."