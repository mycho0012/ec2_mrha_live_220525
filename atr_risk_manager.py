#!/usr/bin/env python3
"""
ATR-based Risk Management System for MRHA Trading
Monitors existing positions and executes trailing stop-loss and take-profit orders
"""

import os
import pyupbit
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
import traceback
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from enhanced_smart_order_executor import EnhancedSmartOrderExecutor
from slack_notifier import SlackNotifier
from fixed_notion_manager import FixedNotionManager

load_dotenv()

class ATRRiskManager:
    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self.logger = logging.getLogger(__name__)
        
        # ATR Configuration
        self.ATR_PERIOD = 14
        self.STOP_LOSS_MULTIPLIER = 2.0  # 2x ATR below entry
        self.TAKE_PROFIT_MULTIPLIER = 3.0  # 3x ATR above entry
        self.TRAILING_STOP_THRESHOLD = 1.5  # Start trailing after 1.5x ATR profit
        self.MAX_POSITION_RISK = 0.02  # 2% portfolio risk per position
        
        # Initialize components
        self.upbit = pyupbit.Upbit(
            os.getenv('UPBIT_ACCESS_KEY'),
            os.getenv('UPBIT_SECRET_KEY')
        )
        self.order_executor = EnhancedSmartOrderExecutor()
        self.slack = SlackNotifier()
        self.notion = FixedNotionManager()
        
        # Risk tracking
        self.position_data = {}
        self.risk_metrics = {}
        
        self.logger.info(f"ATR Risk Manager initialized - Test Mode: {test_mode}")
    
    def calculate_atr(self, ticker: str, period: int = None) -> float:
        """Calculate Average True Range (ATR)"""
        if period is None:
            period = self.ATR_PERIOD
            
        try:
            # Get extended data for ATR calculation
            df = pyupbit.get_ohlcv(ticker, interval="day", count=period + 5)
            if df is None or len(df) < period:
                return 0.0
            
            # Calculate True Range components
            df['prev_close'] = df['close'].shift(1)
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['prev_close'])
            df['tr3'] = abs(df['low'] - df['prev_close'])
            
            # True Range is the maximum of the three
            df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            
            # Calculate ATR (Simple Moving Average of True Range)
            atr = df['true_range'].rolling(window=period).mean().iloc[-1]
            
            return float(atr) if not pd.isna(atr) else 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating ATR for {ticker}: {e}")
            return 0.0
    
    def get_current_positions(self) -> Dict[str, Dict]:
        """Get all current cryptocurrency positions"""
        positions = {}
        
        try:
            balances = self.upbit.get_balances()
            
            for balance in balances:
                currency = balance['currency']
                if currency == 'KRW':
                    continue
                    
                balance_amount = float(balance['balance'])
                locked_amount = float(balance['locked'])
                total_amount = balance_amount + locked_amount
                
                if total_amount > 0:
                    ticker = f"KRW-{currency}"
                    current_price = pyupbit.get_current_price(ticker)
                    
                    if current_price:
                        market_value = total_amount * current_price
                        
                        positions[ticker] = {
                            'currency': currency,
                            'balance': balance_amount,
                            'locked': locked_amount,
                            'total_amount': total_amount,
                            'current_price': current_price,
                            'market_value': market_value,
                            'last_updated': datetime.now()
                        }
            
            return positions
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return {}
    
    def calculate_position_risk_levels(self, ticker: str, position_data: Dict) -> Dict:
        """Calculate stop-loss and take-profit levels for a position"""
        try:
            current_price = position_data['current_price']
            atr = self.calculate_atr(ticker)
            
            if atr == 0:
                self.logger.warning(f"ATR is 0 for {ticker}, using 2% price-based risk")
                atr = current_price * 0.02
            
            # Get historical data to estimate entry price (using recent average)
            df = pyupbit.get_ohlcv(ticker, interval="day", count=5)
            if df is not None and len(df) > 0:
                # Use recent price range as proxy for entry area
                recent_low = df['low'].tail(3).min()
                recent_high = df['high'].tail(3).max()
                estimated_entry = (recent_low + recent_high) / 2
            else:
                estimated_entry = current_price
            
            # Calculate risk levels
            stop_loss = estimated_entry - (atr * self.STOP_LOSS_MULTIPLIER)
            take_profit = estimated_entry + (atr * self.TAKE_PROFIT_MULTIPLIER)
            trailing_threshold = estimated_entry + (atr * self.TRAILING_STOP_THRESHOLD)
            
            # Calculate trailing stop (dynamic based on current price)
            if current_price > trailing_threshold:
                trailing_stop = current_price - (atr * self.STOP_LOSS_MULTIPLIER)
                # Use the higher of fixed stop or trailing stop
                stop_loss = max(stop_loss, trailing_stop)
            
            risk_data = {
                'atr': atr,
                'atr_percent': (atr / current_price) * 100,
                'estimated_entry': estimated_entry,
                'stop_loss': max(stop_loss, 0),  # Ensure positive
                'take_profit': take_profit,
                'trailing_threshold': trailing_threshold,
                'current_profit_loss': ((current_price - estimated_entry) / estimated_entry) * 100,
                'stop_loss_distance': ((current_price - stop_loss) / current_price) * 100,
                'take_profit_distance': ((take_profit - current_price) / current_price) * 100,
                'position_risk': (position_data['market_value'] / self.get_total_portfolio_value()) * 100
            }
            
            return risk_data
            
        except Exception as e:
            self.logger.error(f"Error calculating risk levels for {ticker}: {e}")
            return {}
    
    def get_total_portfolio_value(self) -> float:
        """Get total portfolio value in KRW"""
        try:
            balances = self.upbit.get_balances()
            total_value = 0
            
            for balance in balances:
                currency = balance['currency']
                total_amount = float(balance['balance']) + float(balance['locked'])
                
                if currency == 'KRW':
                    total_value += total_amount
                elif total_amount > 0:
                    ticker = f"KRW-{currency}"
                    current_price = pyupbit.get_current_price(ticker)
                    if current_price:
                        total_value += total_amount * current_price
            
            return total_value
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio value: {e}")
            return 0
    
    def should_execute_stop_loss(self, ticker: str, position_data: Dict, risk_data: Dict) -> bool:
        """Determine if stop-loss should be executed"""
        current_price = position_data['current_price']
        stop_loss = risk_data['stop_loss']
        
        if current_price <= stop_loss:
            loss_percent = ((current_price - risk_data['estimated_entry']) / risk_data['estimated_entry']) * 100
            self.logger.warning(f"Stop-loss triggered for {ticker}: Price {current_price:,.0f} <= Stop {stop_loss:,.0f} (Loss: {loss_percent:.2f}%)")
            return True
            
        return False
    
    def should_execute_take_profit(self, ticker: str, position_data: Dict, risk_data: Dict) -> bool:
        """Determine if take-profit should be executed"""
        current_price = position_data['current_price']
        take_profit = risk_data['take_profit']
        
        if current_price >= take_profit:
            profit_percent = ((current_price - risk_data['estimated_entry']) / risk_data['estimated_entry']) * 100
            self.logger.info(f"Take-profit triggered for {ticker}: Price {current_price:,.0f} >= Target {take_profit:,.0f} (Profit: {profit_percent:.2f}%)")
            return True
            
        return False
    
    def execute_risk_order(self, ticker: str, position_data: Dict, order_type: str, reason: str) -> bool:
        """Execute stop-loss or take-profit order"""
        try:
            currency = position_data['currency']
            amount = position_data['balance']  # Only sell available balance, not locked
            current_price = position_data['current_price']
            
            if amount <= 0:
                self.logger.warning(f"No available balance to sell for {ticker}")
                return False
            
            # Calculate order value
            order_value = amount * current_price
            
            # In test mode, use smaller amounts
            if self.test_mode:
                test_amount = min(amount, 0.001)  # Small test amount
                amount = test_amount
                order_value = amount * current_price
            
            self.logger.info(f"Executing {order_type} for {ticker}: {amount:.6f} {currency} (Value: {order_value:,.0f} KRW)")
            
            # Execute market sell order
            order_result = self.order_executor.execute_market_sell(
                ticker=ticker,
                amount=amount
            )
            
            if order_result and order_result.get('success'):
                # Send Slack notification
                estimated_entry = position_data.get('estimated_entry', current_price)
                profit_loss = ((current_price - estimated_entry) / estimated_entry) * 100
                
                message = f"🛡️ **{order_type} Executed**\n"
                message += f"• Coin: {ticker}\n"
                message += f"• Amount: {amount:.6f} {currency}\n"
                message += f"• Price: {current_price:,.0f} KRW\n"
                message += f"• Value: {order_value:,.0f} KRW\n"
                message += f"• P&L: {profit_loss:+.2f}%\n"
                message += f"• Reason: {reason}\n"
                message += f"• Order ID: {order_result.get('order', {}).get('uuid', 'N/A')}\n"
                message += f"• Test Mode: {self.test_mode}"
                
                self.slack.send_notification(message)
                
                # Update Notion portfolio database after successful execution
                self.update_notion_portfolio_after_execution(ticker, order_result, order_type, profit_loss)
                
                return True
            else:
                error_msg = f"Failed to execute {order_type} for {ticker}"
                self.logger.error(error_msg)
                self.slack.send_notification(f"❌ {error_msg}")
                return False
                
        except Exception as e:
            error_msg = f"Error executing {order_type} for {ticker}: {e}"
            self.logger.error(error_msg)
            self.slack.send_notification(f"❌ {error_msg}")
            return False
    
    def monitor_positions(self) -> Dict:
        """Monitor all positions and execute risk management"""
        self.logger.info("Starting position risk monitoring...")
        
        positions = self.get_current_positions()
        if not positions:
            self.logger.info("No positions to monitor")
            return {}
        
        portfolio_value = self.get_total_portfolio_value()
        executed_orders = []
        risk_alerts = []
        
        for ticker, position_data in positions.items():
            try:
                # Calculate risk levels
                risk_data = self.calculate_position_risk_levels(ticker, position_data)
                if not risk_data:
                    continue
                
                # Store position data for tracking
                self.position_data[ticker] = {**position_data, **risk_data}
                
                # Check for execution triggers
                executed = False
                
                # Check stop-loss
                if self.should_execute_stop_loss(ticker, position_data, risk_data):
                    if self.execute_risk_order(ticker, position_data, "STOP-LOSS", f"Price below {risk_data['stop_loss']:,.0f} KRW"):
                        executed_orders.append({
                            'ticker': ticker,
                            'type': 'STOP-LOSS',
                            'price': position_data['current_price'],
                            'amount': position_data['balance']
                        })
                        executed = True
                
                # Check take-profit (only if stop-loss wasn't executed)
                elif self.should_execute_take_profit(ticker, position_data, risk_data):
                    if self.execute_risk_order(ticker, position_data, "TAKE-PROFIT", f"Price above {risk_data['take_profit']:,.0f} KRW"):
                        executed_orders.append({
                            'ticker': ticker,
                            'type': 'TAKE-PROFIT',
                            'price': position_data['current_price'],
                            'amount': position_data['balance']
                        })
                        executed = True
                
                # Generate risk alerts for positions that weren't executed
                if not executed:
                    # High volatility alert
                    if risk_data['atr_percent'] > 8:
                        risk_alerts.append(f"⚠️ High volatility {ticker}: ATR {risk_data['atr_percent']:.1f}%")
                    
                    # Large position alert
                    if risk_data['position_risk'] > 10:
                        risk_alerts.append(f"⚠️ Large position {ticker}: {risk_data['position_risk']:.1f}% of portfolio")
                
            except Exception as e:
                self.logger.error(f"Error monitoring {ticker}: {e}")
        
        # Send summary notification
        self.send_monitoring_summary(positions, executed_orders, risk_alerts, portfolio_value)
        
        # Sync portfolio with Notion if any orders were executed or periodically
        if executed_orders or self.should_sync_portfolio():
            self.sync_portfolio_with_notion()
        
        return {
            'positions_monitored': len(positions),
            'orders_executed': len(executed_orders),
            'risk_alerts': len(risk_alerts),
            'executed_orders': executed_orders,
            'portfolio_value': portfolio_value
        }
    
    def send_monitoring_summary(self, positions: Dict, executed_orders: List, risk_alerts: List, portfolio_value: float):
        """Send Slack summary of monitoring session"""
        try:
            message = f"🔍 **Risk Monitoring Summary**\n"
            message += f"📊 Portfolio Value: {portfolio_value:,.0f} KRW\n"
            message += f"💼 Positions Monitored: {len(positions)}\n"
            message += f"⚡ Orders Executed: {len(executed_orders)}\n"
            message += f"⚠️ Risk Alerts: {len(risk_alerts)}\n"
            message += f"🧪 Test Mode: {self.test_mode}\n\n"
            
            if executed_orders:
                message += "**Executed Orders:**\n"
                for order in executed_orders:
                    message += f"• {order['type']}: {order['ticker']} at {order['price']:,.0f} KRW\n"
                message += "\n"
            
            if risk_alerts:
                message += "**Risk Alerts:**\n"
                for alert in risk_alerts[:5]:  # Limit to 5 alerts
                    message += f"{alert}\n"
                if len(risk_alerts) > 5:
                    message += f"... and {len(risk_alerts) - 5} more alerts\n"
                message += "\n"
            
            if positions and not executed_orders:
                message += "**Active Positions:**\n"
                for ticker, data in list(positions.items())[:3]:  # Show top 3
                    if ticker in self.position_data:
                        risk_data = self.position_data[ticker]
                        pnl = risk_data.get('current_profit_loss', 0)
                        message += f"• {ticker}: {pnl:+.1f}% (ATR: {risk_data.get('atr_percent', 0):.1f}%)\n"
            
            self.slack.send_notification(message)
            
        except Exception as e:
            self.logger.error(f"Error sending monitoring summary: {e}")
    
    def run_risk_monitoring_cycle(self):
        """Run a complete risk monitoring cycle"""
        try:
            self.logger.info("=" * 50)
            self.logger.info(f"ATR Risk Monitoring - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info("=" * 50)
            
            # Monitor positions
            result = self.monitor_positions()
            
            self.logger.info(f"Monitoring completed: {result}")
            return result
            
        except Exception as e:
            error_msg = f"Risk monitoring cycle failed: {e}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            self.slack.send_notification(f"❌ **Risk Monitoring Error**\n{error_msg}")
            return None
    
    def update_notion_portfolio_after_execution(self, ticker: str, order_result: Dict, order_type: str, profit_loss: float):
        """Update Notion portfolio database after executing risk management order"""
        try:
            self.logger.info(f"Updating Notion portfolio after {order_type} execution for {ticker}")
            
            # Get current portfolio from Upbit
            current_positions = self.get_current_positions()
            
            # Convert to Notion portfolio format
            portfolio_data = []
            
            # Add KRW balance
            try:
                krw_balance = self.upbit.get_balance("KRW")
                if krw_balance > 0:
                    portfolio_data.append({
                        'ticker': 'KRW',
                        'amount': krw_balance,
                        'avg_price': 1.0,
                        'current_price': 1.0,
                        'total_value': krw_balance
                    })
            except Exception as e:
                self.logger.warning(f"Could not get KRW balance: {e}")
            
            # Add cryptocurrency positions
            for ticker_key, position in current_positions.items():
                try:
                    # Get average price (estimate using current price for now)
                    # In production, this could be enhanced to track actual purchase prices
                    avg_price = position['current_price']  # Simplified for now
                    
                    portfolio_data.append({
                        'ticker': ticker_key,
                        'amount': position['total_amount'],
                        'avg_price': avg_price,
                        'current_price': position['current_price'],
                        'total_value': position['market_value']
                    })
                except Exception as e:
                    self.logger.warning(f"Error processing position {ticker_key}: {e}")
                    continue
            
            # Update Notion portfolio database
            if portfolio_data:
                self.notion.update_portfolio(portfolio_data)
                self.logger.info(f"Portfolio updated in Notion: {len(portfolio_data)} positions")
                
                # Send additional Slack notification about portfolio update
                total_value = sum(p.get('total_value', 0) for p in portfolio_data)
                update_message = f"📊 **Portfolio Updated After {order_type}**\n"
                update_message += f"• Total Positions: {len(portfolio_data) - 1}\n"  # -1 for KRW
                update_message += f"• Total Value: {total_value:,.0f} KRW\n"
                update_message += f"• Executed: {ticker}\n"
                update_message += f"• P&L from execution: {profit_loss:+.2f}%"
                
                self.slack.send_notification(update_message)
            else:
                self.logger.warning("No portfolio data to update in Notion")
                
        except Exception as e:
            error_msg = f"Failed to update Notion portfolio after {order_type}: {e}"
            self.logger.error(error_msg)
            self.slack.send_notification(f"⚠️ **Notion Update Failed**\n{error_msg}")
    
    def get_current_portfolio_for_notion(self) -> List[Dict]:
        """Get current portfolio in format suitable for Notion update"""
        try:
            portfolio_data = []
            
            # Get all balances from Upbit
            balances = self.upbit.get_balances()
            
            for balance in balances:
                currency = balance['currency']
                total_amount = float(balance['balance']) + float(balance['locked'])
                
                if total_amount <= 0:
                    continue
                
                if currency == 'KRW':
                    portfolio_data.append({
                        'ticker': 'KRW',
                        'amount': total_amount,
                        'avg_price': 1.0,
                        'current_price': 1.0,
                        'total_value': total_amount
                    })
                else:
                    ticker = f"KRW-{currency}"
                    current_price = pyupbit.get_current_price(ticker)
                    
                    if current_price:
                        # For avg_price, we use current price as approximation
                        # In a full implementation, you'd want to track actual purchase prices
                        portfolio_data.append({
                            'ticker': ticker,
                            'amount': total_amount,
                            'avg_price': current_price,  # Approximation
                            'current_price': current_price,
                            'total_value': total_amount * current_price
                        })
            
            return portfolio_data
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio for Notion: {e}")
            return []
    
    def should_sync_portfolio(self) -> bool:
        """Determine if periodic portfolio sync is needed"""
        try:
            # Sync every 4 hours or if no recent sync
            current_time = datetime.now()
            
            # Check if it's a sync hour (every 4 hours: 4, 8, 12, 16, 20)
            if current_time.hour % 4 == 0 and current_time.minute < 10:
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking sync schedule: {e}")
            return False
    
    def sync_portfolio_with_notion(self):
        """Sync current portfolio with Notion database"""
        try:
            self.logger.info("Syncing portfolio with Notion database")
            
            # Get current portfolio
            portfolio_data = self.get_current_portfolio_for_notion()
            
            if portfolio_data:
                # Update Notion
                self.notion.update_portfolio(portfolio_data)
                
                # Calculate summary
                total_value = sum(p.get('total_value', 0) for p in portfolio_data)
                crypto_positions = len([p for p in portfolio_data if p.get('ticker') != 'KRW'])
                
                self.logger.info(f"Portfolio synced: {crypto_positions} positions, {total_value:,.0f} KRW total")
                
                # Send sync notification (only during periodic syncs, not after order execution)
                if self.should_sync_portfolio():
                    sync_message = f"🔄 **Portfolio Sync Complete**\n"
                    sync_message += f"• Crypto Positions: {crypto_positions}\n"
                    sync_message += f"• Total Portfolio Value: {total_value:,.0f} KRW\n"
                    sync_message += f"• Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M KST')}"
                    
                    self.slack.send_notification(sync_message)
            else:
                self.logger.warning("No portfolio data available for sync")
                
        except Exception as e:
            error_msg = f"Portfolio sync failed: {e}"
            self.logger.error(error_msg)
            self.slack.send_notification(f"⚠️ **Portfolio Sync Failed**\n{error_msg}")

def main():
    """Main execution function"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'risk_monitoring_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler()
        ]
    )
    
    # Initialize risk manager
    test_mode = os.getenv('TEST_MODE', 'True').lower() == 'true'
    risk_manager = ATRRiskManager(test_mode=test_mode)
    
    # Run monitoring cycle
    result = risk_manager.run_risk_monitoring_cycle()
    
    if result:
        print(f"Risk monitoring completed successfully: {result}")
    else:
        print("Risk monitoring failed")

if __name__ == "__main__":
    main()