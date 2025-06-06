import pyupbit
from typing import Dict, Optional
import time
import logging
import os
from dotenv import load_dotenv

load_dotenv()

class EnhancedSmartOrderExecutor:
    def __init__(self, access_key: str = None, secret_key: str = None):
        self.access_key = access_key or os.getenv('UPBIT_ACCESS_KEY')
        self.secret_key = secret_key or os.getenv('UPBIT_SECRET_KEY')
        
        if not self.access_key or not self.secret_key:
            self.logger = logging.getLogger(__name__)
            self.logger.error("Missing API keys in environment variables")
            raise ValueError("UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY must be set")
            
        self.upbit = pyupbit.Upbit(self.access_key, self.secret_key)
        self.logger = logging.getLogger(__name__)
        
        # Print API key first few and last few characters for debugging
        masked_key = f"{self.access_key[:4]}...{self.access_key[-4:]}" if len(self.access_key) > 8 else "***" 
        self.logger.info(f"Initialized with API key: {masked_key}")
        
        # Set minimal order size
        self.min_order_size = 5000  # 5,000 KRW minimum
        
        # Check authentication works by getting KRW balance
        try:
            krw_balance = self.upbit.get_balance("KRW")
            self.logger.info(f"Authentication successful - KRW balance: {krw_balance:,.0f}")
        except Exception as e:
            self.logger.error(f"Authentication failed - can't get balance: {e}")
            raise ValueError(f"API authentication failed: {e}")
        
    def get_market_info(self, ticker: str) -> Dict:
        """Get market trading constraints"""
        try:
            markets = pyupbit.get_market_all()
            for market in markets:
                if market['market'] == ticker:
                    return market
            return {}
        except Exception as e:
            self.logger.error(f"Error getting market info: {e}")
            return {}
    
    def round_price_to_tick(self, price: float, ticker: str) -> float:
        """Round price to valid tick size for the market"""
        try:
            orderbook = pyupbit.get_orderbook(ticker)
            if orderbook and len(orderbook) > 0:
                # Determine tick size based on price level
                if price >= 1000000:
                    tick_size = 1000
                elif price >= 100000:
                    tick_size = 100
                elif price >= 10000:
                    tick_size = 10
                elif price >= 1000:
                    tick_size = 1
                elif price >= 100:
                    tick_size = 0.1
                else:
                    tick_size = 0.01
                
                return round(price / tick_size) * tick_size
            return price
        except Exception as e:
            self.logger.error(f"Error rounding price: {e}")
            return price
    
    def execute_iceberg_order(self, order_type: str, ticker: str, total_amount: float, price: float, slice_count: int = 5):
        """Execute large orders in smaller slices to reduce market impact"""
        try:
            slice_amount = total_amount / slice_count
            executed_amount = 0
            results = []
            
            for i in range(slice_count):
                # Adjust price slightly for each slice
                slice_price = price * (1 + (i * 0.0001))  # Tiny price improvement
                slice_price = self.round_price_to_tick(slice_price, ticker)
                
                if order_type == 'sell':
                    order = self.upbit.sell_limit_order(ticker, slice_amount, slice_price)
                else:
                    order = self.upbit.buy_limit_order(ticker, slice_amount, slice_price)
                
                results.append(order)
                executed_amount += slice_amount
                
                # Wait between slices
                time.sleep(2)
                
                # Check if order is filling
                order_status = self.upbit.get_order(order['uuid'])
                if order_status['state'] != 'done' and order_status['state'] != 'wait':
                    self.logger.warning(f"Order slice {i+1} not filling well, adjusting strategy")
                    break
            
            return {
                'success': True,
                'orders': results,
                'executed_amount': executed_amount,
                'remaining_amount': total_amount - executed_amount
            }
            
        except Exception as e:
            self.logger.error(f"Error in iceberg order: {e}")
            return {'success': False, 'error': str(e)}
    
    def execute_sell_with_anti_slippage(self, ticker: str, amount: float) -> Dict:
        """Simplified function that only uses market orders for maximum reliability"""
        self.logger.info(f"Using direct market sell for reliability: {ticker}, {amount} coins")
        # Skip all complex strategies and go straight to market orders
        return self.execute_market_sell(ticker, amount)
    
    def execute_market_sell(self, ticker: str, amount: float) -> Dict:
        """Dead-simple market sell - direct call to Upbit API"""
        try:
            # Check if in test mode 
            is_test_mode = os.getenv('TEST_MODE', 'False').lower() in ('true', '1', 't')
            
            # In test mode, use a small percentage of holding
            if is_test_mode:
                original_amount = amount
                current_balance = self.upbit.get_balance(ticker)
                if current_balance > 0:
                    # Use 5% of balance in test mode or the requested amount, whichever is smaller
                    test_amount = min(current_balance * 0.05, amount)
                    amount = max(test_amount, 0.0001)  # Ensure we have at least minimum amount
                    self.logger.info(f"TEST MODE: Limited sell from {original_amount} to {amount} coins (5% of balance)")
            else:
                self.logger.info(f"PRODUCTION: Using full amount of {amount} coins")
            
            # Get current price for reporting
            current_price = pyupbit.get_current_price(ticker)
            
            # Direct market sell
            self.logger.info(f"Placing market sell for {ticker}: {amount} coins")
            response = self.upbit.sell_market_order(ticker, amount)
            
            if response and 'uuid' in response:
                self.logger.info(f"Market sell for {ticker} placed: {response['uuid']}")
                return {
                    'success': True,
                    'order': response,
                    'executed_price': current_price,
                    'executed_amount': amount
                }
            else:
                self.logger.error(f"Failed to place market sell order: {response}")
                return {'success': False, 'error': f"Failed market sell: {response}"}
            
        except Exception as e:
            self.logger.error(f"Market sell failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def execute_buy_with_anti_slippage(self, ticker: str, krw_amount: float) -> Dict:
        """Simplified function that only uses market orders for maximum reliability"""
        self.logger.info(f"Using direct market buy for reliability: {ticker}, {krw_amount:,.0f} KRW")
        # Skip all complex strategies and go straight to market orders
        return self.execute_market_buy(ticker, krw_amount)
    
    def execute_market_buy(self, ticker: str, krw_amount: float) -> Dict:
        """Dead-simple market buy - just an easy wrapper around Upbit API"""
        try:
            # Check if in test mode 
            is_test_mode = os.getenv('TEST_MODE', 'False').lower() in ('true', '1', 't')
            
            # In test mode, limit amount to small value
            if is_test_mode:
                original_amount = krw_amount
                krw_amount = min(krw_amount, 5500)  # Use at most 5,500 KRW in test mode
                self.logger.info(f"TEST MODE: Limited order from {original_amount:,.0f} to {krw_amount:,.0f} KRW")
            else:
                self.logger.info(f"PRODUCTION: Using full amount of {krw_amount:,.0f} KRW")
            
            # Get current price to calculate amount
            current_price = pyupbit.get_current_price(ticker)
            if not current_price:
                self.logger.error(f"Can't get price for {ticker}")
                return {'success': False, 'error': f"Couldn't get current price for {ticker}"}
            
            coin_amount = (krw_amount * 0.995) / current_price
            
            # Direct call to buy_market_order (works with total KRW amount)
            self.logger.info(f"Placing market buy for {ticker}: {krw_amount:,.0f} KRW")
            response = self.upbit.buy_market_order(ticker, krw_amount)
            
            if response and 'uuid' in response:
                self.logger.info(f"Market buy order for {ticker} placed: {response['uuid']}")
                return {
                    'success': True,
                    'order': response,
                    'executed_price': current_price,
                    'executed_amount': coin_amount
                }
            else:
                self.logger.error(f"Failed to place market buy order: {response}")
                return {'success': False, 'error': f"Failed market buy: {response}"}
                
        except Exception as e:
            self.logger.error(f"Market buy failed: {e}")
            return {'success': False, 'error': str(e)}