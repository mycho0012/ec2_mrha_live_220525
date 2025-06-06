# ATR-Based Risk Management System

## Overview

This enhanced risk management system adds ATR (Average True Range) based trailing stop-loss and take-profit functionality to the MRHA trading system. It monitors existing positions hourly and automatically executes protective orders based on market volatility.

## Key Features

### 🛡️ ATR-Based Risk Management
- **Dynamic Stop-Loss**: 2.0x ATR below estimated entry price
- **Take-Profit Targets**: 3.0x ATR above estimated entry price  
- **Trailing Stops**: Adjusts stop-loss as price moves favorably
- **Volatility Adaptation**: Risk levels adjust based on current market volatility

### 📊 Position Monitoring
- **Hourly Monitoring**: Runs every hour during market hours (6 AM - 11 PM KST)
- **Real-time Risk Assessment**: Continuous evaluation of all positions
- **Portfolio Risk Tracking**: Monitors position sizes and total exposure
- **Automated Execution**: No manual intervention required

### 🔔 Comprehensive Notifications
- **Slack Integration**: Real-time alerts for all risk events
- **Execution Confirmations**: Detailed trade notifications
- **Risk Alerts**: Warnings for high volatility or large positions
- **Status Updates**: Periodic system health reports

### 📊 Notion Database Integration
- **Automatic Portfolio Updates**: Updates portfolio database after every execution
- **Real-time Synchronization**: Maintains consistency with main trading system
- **Periodic Sync**: Syncs portfolio every 4 hours for data integrity
- **Position Tracking**: Tracks all holdings with current values and P&L

## Files Added

### Core Components
- **`atr_risk_manager.py`** - Main ATR risk management engine
- **`risk_monitor_scheduler.py`** - Hourly monitoring scheduler
- **`run_risk_manager.sh`** - Execution script with multiple modes

### Configuration Updates
- **`requirements.txt`** - Added `schedule` and `pytz` dependencies
- **`docker-compose.yml`** - Added risk-manager service
- **`ATR_RISK_MANAGEMENT.md`** - This documentation

## Configuration Parameters

### Risk Settings (Configurable in `atr_risk_manager.py`)
```python
ATR_PERIOD = 14                    # ATR calculation period
STOP_LOSS_MULTIPLIER = 2.0         # Stop-loss: 2x ATR below entry
TAKE_PROFIT_MULTIPLIER = 3.0       # Take-profit: 3x ATR above entry
TRAILING_STOP_THRESHOLD = 1.5      # Start trailing after 1.5x ATR profit
MAX_POSITION_RISK = 0.02           # 2% portfolio risk per position
```

### Monitoring Schedule
- **Production**: Every hour
- **Test Mode**: Every 5 minutes
- **Market Hours**: 6 AM - 11 PM KST
- **Crypto Markets**: 24/7 monitoring available

## Usage

### 1. Standalone Execution

#### Run Risk Manager Once
```bash
./run_risk_manager.sh -m once
```

#### Start Hourly Monitoring (Test Mode)
```bash
./run_risk_manager.sh -m scheduler
```

#### Start Production Monitoring
```bash
./run_risk_manager.sh -m scheduler --production
```

#### Test Run Only
```bash
./run_risk_manager.sh -m test
```

### 2. Docker Deployment

#### Start Both Trading and Risk Management
```bash
docker-compose up -d
```

#### Start Only Risk Manager
```bash
docker-compose up -d risk-manager
```

#### View Risk Manager Logs
```bash
docker-compose logs -f risk-manager
```

### 3. Integration with Main System

The risk manager runs independently and monitors positions created by the main trading system. No changes to existing trading logic are required.

## How It Works

### 1. Position Detection
- Scans all non-KRW balances in Upbit account
- Calculates current market value for each position
- Identifies positions requiring risk management

### 2. ATR Calculation
- Downloads 14-day price history for each coin
- Calculates True Range: max(High-Low, |High-PrevClose|, |Low-PrevClose|)
- Computes ATR as 14-period moving average of True Range
- Adapts to current market volatility

### 3. Risk Level Determination
- **Entry Price Estimation**: Uses recent price range average
- **Stop-Loss**: Entry - (ATR × 2.0)
- **Take-Profit**: Entry + (ATR × 3.0)
- **Trailing Stop**: Adjusts stop-loss upward as price rises

### 4. Execution Logic
- **Stop-Loss Trigger**: Current price ≤ Stop-loss level
- **Take-Profit Trigger**: Current price ≥ Take-profit level
- **Order Execution**: Market sell orders via existing order executor
- **Notion Update**: Immediately updates portfolio database
- **Notification**: Slack alerts with trade details and portfolio status

### 5. Portfolio Synchronization
- **Immediate Updates**: Portfolio updated after every execution
- **Periodic Sync**: Every 4 hours (4 AM, 8 AM, 12 PM, 4 PM, 8 PM)
- **Data Consistency**: Ensures main system and risk manager stay synchronized
- **Error Recovery**: Automatic retry on sync failures

### 6. Risk Monitoring
- **High Volatility Alert**: ATR > 8% of current price
- **Large Position Alert**: Position > 10% of portfolio
- **Portfolio Tracking**: Total value and risk exposure

## Slack Notifications

### Risk Events
```
🛡️ STOP-LOSS Executed
• Coin: KRW-BTC
• Amount: 0.001234 BTC
• Price: 45,000,000 KRW
• Value: 55,530 KRW
• P&L: -5.2%
• Reason: Price below 43,000,000 KRW
• Order ID: abc123-def456-ghi789
• Test Mode: false
```

### Portfolio Updates
```
📊 Portfolio Updated After STOP-LOSS
• Total Positions: 7
• Total Value: 2,150,000 KRW
• Executed: KRW-BTC
• P&L from execution: -5.2%
```

### Monitoring Summary
```
🔍 Risk Monitoring Summary
📊 Portfolio Value: 1,250,000 KRW
💼 Positions Monitored: 5
⚡ Orders Executed: 1
⚠️ Risk Alerts: 2
🧪 Test Mode: false
```

### Status Updates (Every 4 Hours)
```
📊 Risk Monitor Status Update
🕐 Time: 2024-12-06 16:00 KST
💼 Positions: 8
⚡ Orders: 0
⚠️ Alerts: 1
💰 Portfolio: 2,340,000 KRW
📈 System: Running normally
```

## Test Mode vs Production Mode

### Test Mode (`TEST_MODE=true`)
- **Order Size**: Small amounts (0.001 coins or 5,000 KRW)
- **Frequency**: Every 5 minutes
- **Safety**: Minimal financial impact
- **Purpose**: Validation and testing

### Production Mode (`TEST_MODE=false`)
- **Order Size**: Full calculated amounts
- **Frequency**: Every hour
- **Risk**: Full position management
- **Purpose**: Live trading protection

## Logging

### Log Files
- **`risk_monitoring_YYYYMMDD.log`** - Daily risk monitoring logs
- **`risk_scheduler_YYYYMMDD.log`** - Scheduler operation logs
- **`trading_YYYYMMDD.log`** - Main trading system logs (existing)

### Log Levels
- **INFO**: Normal operations and monitoring results
- **WARNING**: Risk alerts and position warnings
- **ERROR**: Execution failures and system errors

## Safety Features

### Position Protection
- **Minimum Order Size**: Respects Upbit 5,000 KRW minimum
- **Balance Validation**: Only sells available (non-locked) balance
- **Price Validation**: Confirms current prices before execution

### Error Handling
- **API Failures**: Graceful handling with retry logic
- **Network Issues**: Continues monitoring after temporary failures
- **Invalid Data**: Skips problematic positions with warnings

### Risk Limits
- **Maximum Position Risk**: 2% of portfolio per position
- **Stop-Loss Floor**: Never below zero
- **Order Size Limits**: Respects exchange constraints

## Monitoring and Maintenance

### System Health
- Monitor Slack notifications for system status
- Check log files for errors or warnings
- Verify Docker container health: `docker-compose ps`

### Performance Metrics
- **Execution Rate**: Successfully executed vs attempted orders
- **Position Coverage**: Monitored positions vs total positions
- **Alert Accuracy**: Risk alerts vs actual risk events

### Troubleshooting
- **No Positions Detected**: Check API keys and permissions
- **ATR Calculation Errors**: Verify market data availability
- **Order Execution Failures**: Check account balance and market conditions
- **Slack Notification Issues**: Verify Slack webhook configuration

## Advanced Configuration

### Custom Risk Parameters
Edit `atr_risk_manager.py` to customize:
- ATR calculation period
- Stop-loss and take-profit multipliers
- Trailing stop threshold
- Maximum position risk limits

### Schedule Modification
Edit `risk_monitor_scheduler.py` to change:
- Monitoring frequency
- Market hours
- Status update intervals

### Integration Options
The system can be extended to:
- Support additional exchanges
- Implement custom risk models
- Add machine learning predictions
- Integrate with external risk systems

## Support and Updates

For issues or enhancements:
1. Check log files for error details
2. Verify environment configuration
3. Test in test mode before production
4. Monitor Slack notifications for system health

The ATR risk management system enhances your trading strategy with professional-grade risk controls while maintaining the simplicity and reliability of the original MRHA system.