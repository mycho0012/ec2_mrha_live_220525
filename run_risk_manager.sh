#!/bin/bash

# Risk Manager Execution Script for MRHA Trading System
# Provides multiple execution modes for ATR-based risk management

set -e

# Default values
MODE="scheduler"
TEST_MODE="true"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_usage() {
    echo -e "${BLUE}MRHA Risk Manager - Execution Script${NC}"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -m, --mode MODE        Execution mode: 'scheduler', 'once', 'test' (default: scheduler)"
    echo "  -p, --production       Run in production mode (default: test mode)"
    echo "  -t, --test             Run in test mode (default)"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Modes:"
    echo "  scheduler              Run continuous hourly monitoring (default)"
    echo "  once                   Run risk monitoring once and exit"
    echo "  test                   Run test monitoring cycle"
    echo ""
    echo "Examples:"
    echo "  $0                     # Run scheduler in test mode"
    echo "  $0 -m once -p          # Run once in production mode"
    echo "  $0 -m test             # Run test cycle"
    echo "  $0 --production        # Run scheduler in production mode"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -p|--production)
            TEST_MODE="false"
            shift
            ;;
        -t|--test)
            TEST_MODE="true"
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            print_usage
            exit 1
            ;;
    esac
done

# Validate mode
case $MODE in
    scheduler|once|test)
        ;;
    *)
        echo -e "${RED}Invalid mode: $MODE${NC}"
        print_usage
        exit 1
        ;;
esac

# Check if we're in the right directory
if [ ! -f "atr_risk_manager.py" ]; then
    echo -e "${RED}Error: atr_risk_manager.py not found${NC}"
    echo "Please run this script from the MRHA trading system directory"
    exit 1
fi

# Check if required environment file exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Make sure environment variables are set"
fi

# Set environment variable
export TEST_MODE=$TEST_MODE

# Print configuration
echo -e "${BLUE}MRHA Risk Manager Starting...${NC}"
echo -e "Mode: ${GREEN}$MODE${NC}"
echo -e "Test Mode: ${GREEN}$TEST_MODE${NC}"
echo -e "Time: ${GREEN}$(date)${NC}"
echo ""

# Execute based on mode
case $MODE in
    scheduler)
        echo -e "${BLUE}Starting continuous risk monitoring scheduler...${NC}"
        if [ "$TEST_MODE" = "true" ]; then
            echo -e "${YELLOW}Running in TEST mode - using small amounts and frequent checks${NC}"
        else
            echo -e "${GREEN}Running in PRODUCTION mode - using full amounts${NC}"
        fi
        echo ""
        python3 risk_monitor_scheduler.py
        ;;
    
    once)
        echo -e "${BLUE}Running risk monitoring once...${NC}"
        python3 atr_risk_manager.py
        echo -e "${GREEN}Risk monitoring completed${NC}"
        ;;
    
    test)
        echo -e "${BLUE}Running test monitoring cycle...${NC}"
        export TEST_MODE="true"
        python3 atr_risk_manager.py
        echo -e "${GREEN}Test monitoring completed${NC}"
        ;;
esac

echo ""
echo -e "${GREEN}Risk Manager execution finished${NC}"