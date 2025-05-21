# Enhanced MRHA Trading System

This is an enhanced version of the MRHA (Modified Revised Heikin Ashi) cryptocurrency trading system with momentum detection and smart order execution.

## New Features

1. **Momentum Detection**: Identifies coins with unusual price movements and volume spikes
2. **Smart Order Execution**: Uses limit orders with intelligent pricing based on orderbook analysis
3. **Dynamic Capital Allocation**: Allocates more capital to momentum opportunities
4. **Docker Support**: Containerized deployment for consistency
5. **Enhanced Logging**: Comprehensive logging for debugging and monitoring
6. **Robust Order Management**: Improved order monitoring with retry logic for optimal execution

## Installation

1. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```

2. Build and run with Docker:
   ```bash
   ./run.sh
   ```

   Or manually:
   ```bash
   docker-compose build
   docker-compose up -d
   ```

## System Components

- `enhanced_realtime_trader.py`: Main trading system with momentum detection
- `improved_order_manager.py`: Robust order monitoring with extended timeouts
- `fixed_notion_manager.py`: Reliable Notion integration with proper error handling
- `enhanced_smart_order_executor.py`: Intelligent order placement with liquidity analysis
- `capital_allocator.py`: Dynamic capital allocation based on signal strength
- `slack_notifier.py`: Real-time notifications with rich formatting
- `class_mrha.py`: Core MRHA strategy implementation

## Trading Strategy

1. **Signal Generation (09:00 KST)**
   - Analyzes top 10 coins by volume
   - Detects momentum opportunities (price surges, volume spikes)
   - Includes all owned coins
   - Generates MRHA signals

2. **Trade Execution (09:05 KST)**
   - Executes SELL orders first
   - Allocates capital dynamically to BUY signals
   - Uses smart pricing to minimize slippage

## Momentum Detection Criteria

- Price surge: >10% daily increase
- Volume spike: >3x average volume
- Breakout: Price >5% above 5-day high

## Configuration

Key parameters in the code:
- Base volume coins: 10
- Max momentum coins: 5
- Momentum capital ratio: 60%
- Min order size: 5,000 KRW

## Monitoring

View logs:
```bash
docker-compose logs -f
```

Stop the system:
```bash
docker-compose down
```

## Safety Features

- Pre-trade orderbook analysis
- Maximum slippage limits
- Comprehensive error handling
- Automatic retry logic with exponential backoff
- Slack notifications for all events
- Detailed diagnostic logging for API operations

## Notion API Integration

The system integrates with two Notion databases:
- **Daily Signals DB**: Tracks trading signals and their execution status
- **Portfolio DB**: Tracks current positions and performance

Updates to these databases are:
- Performed with automatic retry logic
- Include exponential backoff for rate limiting
- Generate detailed logs for troubleshooting
- Include verification steps to confirm successful updates

## Test Mode vs Production Mode

The system has two operational modes:

- **Test Mode**: 
  - Uses minimal order amounts (5,000-10,000 KRW)
  - Executes immediately for quick testing
  - Limits to 2 iterations by default

- **Production Mode**:
  - Uses full calculated order amounts
  - Follows 9:00 AM KST schedule
  - Runs continuously

To switch between modes, change `TEST_MODE` in `enhanced_realtime_trader.py`:
```python
TEST_MODE = True  # For test mode
TEST_MODE = False  # For production mode
```

## Troubleshooting

If you encounter issues with Notion updates, check `README_FIX.md` for solutions to common problems.

## Notes

- The system runs continuously, executing trades daily at scheduled times
- All trades are logged and reported via Slack
- Notion databases track all signals and portfolio changes
- Docker ensures consistent execution environment