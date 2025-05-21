#!/bin/bash

# Enhanced MRHA Trading System Startup Script

# Set timezone to KST
export TZ=Asia/Seoul

# Logging setup
LOG_DIR="logs"
mkdir -p $LOG_DIR
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/system_${TIMESTAMP}.log"

# Function to log messages
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Check for required environment variables
log "INFO" "Checking environment variables..."
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    log "ERROR" ".env file not found. Please create it with required credentials."
    exit 1
fi

# Check Python installation
log "INFO" "Checking Python installation..."
PYTHON_CMD=$(which python3 || which python)
if [ -z "$PYTHON_CMD" ]; then
    log "ERROR" "Python not found. Please install Python 3.7 or later."
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
log "INFO" "Using Python $PYTHON_VERSION"

# Check pip installation and packages
log "INFO" "Checking required packages..."
if ! $PYTHON_CMD -m pip -V &>/dev/null; then
    log "ERROR" "pip not found. Please install pip."
    exit 1
fi

log "INFO" "Installing/updating required packages..."
$PYTHON_CMD -m pip install -r requirements.txt --no-cache-dir

# Start the trading system
log "INFO" "Starting Enhanced MRHA Trading System in TEST MODE..."
log "INFO" "Log file: $LOG_FILE"
log "INFO" "The system will run in test mode, executing trades immediately and then 5 minutes later"
log "INFO" "After testing is complete, set TEST_MODE=False in enhanced_realtime_trader.py"

# Run the enhanced realtime trader
$PYTHON_CMD enhanced_realtime_trader.py 2>&1 | tee -a "$LOG_FILE"

# Check the exit status
PYTHON_EXIT_CODE=${PIPESTATUS[0]}
if [ $PYTHON_EXIT_CODE -ne 0 ]; then
    log "ERROR" "Trading system exited with code $PYTHON_EXIT_CODE"
    
    # Send error notification (if available)
    if $PYTHON_CMD -c "import sys; sys.path.append('.'); from slack_notifier import SlackNotifier; notifier = SlackNotifier(); notifier.notify_error('System Crash', 'Trading system exited with code $PYTHON_EXIT_CODE');" &>/dev/null; then
        log "INFO" "Error notification sent"
    else
        log "WARNING" "Failed to send error notification"
    fi
    
    exit $PYTHON_EXIT_CODE
else
    log "INFO" "Trading system completed successfully"
fi