import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import time
import pyupbit
import pandas as pd
from sympy import false
from fixed_notion_manager import FixedNotionManager as EnhancedNotionManager
from slack_notifier import SlackNotifier
from class_mrha import MRHATradingSystem
from enhanced_smart_order_executor import EnhancedSmartOrderExecutor
from capital_allocator import CapitalAllocator
from improved_order_manager import ImprovedOrderManager as OrderManager
import logging
import traceback
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'trading_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

load_dotenv()

def get_trading_candidates(upbit, owned_coins=None, base_count=10):
    """Get trading candidates including momentum detection - improved error handling & ranking"""
    try:
        all_tickers = pyupbit.get_tickers(fiat="KRW")
        logging.info(f"Found {len(all_tickers)} KRW-based tickers for analysis")
        candidates = []
        processed = 0
        errors = 0
        
        for ticker in all_tickers:
            try:
                # Get recent data for momentum analysis
                df = pyupbit.get_ohlcv(ticker, interval="day", count=5)
                if df is None or df.empty:
                    continue
                
                # Calculate key metrics
                current_price = df['close'].iloc[-1]
                prev_close = df['close'].iloc[-2]
                daily_change = (current_price - prev_close) / prev_close
                
                # Volume metrics
                current_volume = df['volume'].iloc[-1] * current_price
                avg_volume = df['volume'].iloc[:-1].mean() * df['close'].iloc[:-1].mean()
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
                
                # Momentum detection criteria
                is_momentum = False
                momentum_score = 0
                momentum_factors = []
                
                # Criteria 1: Price surge (>10% daily increase)
                if daily_change > 0.10:
                    is_momentum = True
                    factor_score = daily_change * 100
                    momentum_score += factor_score
                    momentum_factors.append(f"Price surge: {daily_change*100:.1f}% (+{factor_score:.1f})")
                
                # Criteria 2: Volume spike (>3x average volume)
                if volume_ratio > 3:
                    is_momentum = True
                    factor_score = volume_ratio * 10
                    momentum_score += factor_score
                    momentum_factors.append(f"Volume spike: {volume_ratio:.1f}x (+{factor_score:.1f})")
                
                # Criteria 3: Breakout detection (price above 5-day high)
                five_day_high = df['high'].iloc[:-1].max()
                if current_price > five_day_high * 1.05:  # 5% above recent high
                    is_momentum = True
                    factor_score = 20
                    momentum_score += factor_score
                    pct_above_high = ((current_price / five_day_high) - 1) * 100
                    momentum_factors.append(f"Breakout: {pct_above_high:.1f}% above 5d high (+{factor_score:.1f})")
                
                # Add more details for future analysis
                candidates.append({
                    'ticker': ticker,
                    'trading_value': current_volume,
                    'daily_change': daily_change,
                    'volume_ratio': volume_ratio,
                    'is_momentum': is_momentum,
                    'momentum_score': momentum_score,
                    'momentum_factors': momentum_factors,
                    'current_price': current_price,
                    'is_owned': ticker in (owned_coins or [])
                })
                
                processed += 1
                time.sleep(0.05)  # Rate limiting
                
            except Exception as e:
                errors += 1
                logging.debug(f"Error processing {ticker}: {e}")
                continue
        
        logging.info(f"Processed {processed}/{len(all_tickers)} tickers successfully ({errors} errors)")
        
        # Sort by trading value for ranking
        candidates.sort(key=lambda x: x['trading_value'], reverse=True)
        
        # Assign volume-based ranking 
        for i, candidate in enumerate(candidates, 1):
            candidate['rank'] = i
        
        # Get top coins by volume
        top_by_volume = candidates[:base_count]
        
        # Get momentum coins
        momentum_coins = [c for c in candidates if c['is_momentum'] and c not in top_by_volume]
        momentum_coins.sort(key=lambda x: x['momentum_score'], reverse=True)
        
        # Get owned coins not in top list
        owned_not_in_top = [c for c in candidates if c['is_owned'] and c not in top_by_volume]
        
        # Log momentum details
        if momentum_coins:
            top5_momentum = momentum_coins[:5]
            momentum_details = [f"{c['ticker']} (Score: {c['momentum_score']:.1f}, {', '.join(c['momentum_factors'])})" 
                               for c in top5_momentum]
            logging.info(f"Top momentum coins: {', '.join(momentum_details)}")
        
        # Combine: Top 10 + Top 5 momentum + All owned
        final_selection = top_by_volume + momentum_coins[:5] + owned_not_in_top
        
        # Remove duplicates but preserve first occurrence (which has correct rank)
        seen = set()
        unique_selection = []
        for coin in final_selection:
            if coin['ticker'] not in seen:
                seen.add(coin['ticker'])
                unique_selection.append(coin)
        
        logging.info(f"Selected {len(unique_selection)} coins: {base_count} top volume + {len(momentum_coins[:5])} momentum + {len(owned_not_in_top)} owned")
        
        return unique_selection
        
    except Exception as e:
        logging.error(f"Error getting trading candidates: {e}")
        return []

def generate_enhanced_signals(top_coins, slack):
    """Generate signals with market context"""
    signals = []
    signal_summary = {'BUY': [], 'SELL': [], 'HOLD': []}
    momentum_buys = []
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    for coin_data in top_coins:
        coin = coin_data['ticker']
        try:
            # Run MRHA analysis
            bot = MRHATradingSystem(coin, "day", count=365)
            bot.run_analysis()
            
            # Get signal
            last_signal = "HOLD"
            signal_strength = 0
            
            # Check for recent signals
            if bot.trades is not None and not bot.trades.empty:
                for _, trade in bot.trades.iterrows():
                    trade_date = trade['Date'].strftime("%Y-%m-%d")
                    if trade_date == yesterday:
                        last_signal = "BUY" if trade['Type'] == 'Buy' else "SELL"
                        break
            
            # Enhance signal with momentum context
            if last_signal == "BUY" and coin_data['is_momentum']:
                signal_strength = coin_data['momentum_score']
                momentum_buys.append({
                    'ticker': coin,
                    'momentum_score': coin_data['momentum_score'],
                    'volume_ratio': coin_data['volume_ratio']
                })
            
            signals.append({
                'ticker': coin.replace('KRW-', ''),
                'rank': coin_data.get('rank', 999),
                'trading_value': coin_data['trading_value'],
                'signal': last_signal,
                'signal_strength': signal_strength,
                'is_momentum': coin_data['is_momentum'],
                'momentum_score': coin_data.get('momentum_score', 0),
                'status': 'PENDING'
            })
            
            signal_summary[last_signal].append(coin.replace('KRW-', ''))
            
        except Exception as e:
            logging.error(f"Error processing {coin}: {e}")
            continue
    
    # Special notification for momentum opportunities
    if momentum_buys:
        momentum_msg = "🚀 Momentum Opportunities Detected:\n"
        for mb in momentum_buys[:3]:
            momentum_msg += f"• {mb['ticker']}: Score {mb['momentum_score']:.1f}, Volume {mb['volume_ratio']:.1f}x\n"
        slack.send_notification(momentum_msg)
    
    return signals

def execute_buy_with_amount(signal, amount, notion_manager, executor, order_manager):
    """Enhanced buy order execution with proper status updates"""
    try:
        ticker = f"KRW-{signal['properties']['Ticker']['select']['name']}"
        signal_id = signal['id']
        
        logging.info(f"Executing BUY order for {ticker} with {amount:,.0f} KRW")
        
        # 메타데이터 추출
        is_momentum = False
        momentum_score = 0
        
        if 'Is_Momentum' in signal['properties']:
            is_momentum = signal['properties']['Is_Momentum'].get('checkbox', False)
        if 'Momentum_Score' in signal['properties']:
            momentum_score = signal['properties']['Momentum_Score'].get('number', 0)
        
        # 주문 실행 시도 - use the enhanced method
        result = executor.execute_buy_with_anti_slippage(ticker, amount)
        
        if result['success']:
            # 주문이 시작되었지만 완료되지 않은 경우
            if 'order' in result and 'uuid' in result['order']:
                order_id = result['order']['uuid']
                logging.info(f"Buy order placed for {ticker}: {amount:,.0f} KRW, order_id={order_id}")
                
                # 노션 상태 업데이트 - IN_PROGRESS
                notion_manager.update_signal_status(signal_id, "IN_PROGRESS", {
                    'order_id': order_id,
                    'amount': amount
                })
                
                # 주문 완료 기다리기
                order_result = order_manager.monitor_order(order_id, timeout=60)
                
                if order_result['state'] == 'done':
                    # 주문 완료된 경우
                    executed_price = float(order_result.get('avg_price', 0))
                    executed_amount = float(order_result.get('executed_volume', 0))
                    total_value = float(order_result.get('paid_fee', 0)) + float(order_result.get('executed_volume', 0)) * executed_price
                    
                    # 성공 상태 업데이트
                    notion_manager.update_signal_status(signal_id, "DONE", {
                        'order_id': order_id,
                        'price': executed_price,
                        'amount': executed_amount,
                        'total_value': total_value
                    })
                    
                    # Slack 알림
                    slack_data = {
                        'ticker': ticker,
                        'amount': executed_amount,
                        'execution_price': executed_price,
                        'investment_amount': total_value,
                        'order_id': order_id,
                        'is_momentum': is_momentum,
                        'momentum_score': momentum_score
                    }
                    notion_manager.slack.notify_signal_execution("BUY", slack_data)
                    
                    logging.info(f"Buy order completed for {ticker}: {executed_amount} @ {executed_price:,.0f} KRW")
                    return {'success': True, 'order': order_result, 'status': 'DONE'}
                else:
                    # 주문이 완료되지 않은 경우
                    notion_manager.update_signal_status(signal_id, "FAILED", {
                        'order_id': order_id,
                        'error': f"Order timeout or cancelled: {order_result['state']}"
                    })
                    logging.error(f"Buy order incomplete for {ticker}: {order_result['state']}")
                    return {'success': False, 'order': order_result, 'status': 'FAILED', 
                            'error': f"Order state: {order_result['state']}"}
            
            # 주문이 즉시 완료된 경우 또는 주문 ID가 없는 경우
            if 'executed_price' in result:
                notion_manager.update_signal_status(signal_id, "DONE", {
                    'price': result['executed_price'],
                    'amount': result.get('executed_amount', amount / result['executed_price']),
                    'total_value': amount
                })
                
                # Slack 알림
                slack_data = {
                    'ticker': ticker,
                    'amount': result.get('executed_amount', amount / result['executed_price']),
                    'execution_price': result['executed_price'],
                    'investment_amount': amount,
                    'is_momentum': is_momentum,
                    'momentum_score': momentum_score
                }
                notion_manager.slack.notify_signal_execution("BUY", slack_data)
                
                logging.info(f"Buy order immediately executed for {ticker} @ {result['executed_price']:,.0f} KRW")
            else:
                notion_manager.update_signal_status(signal_id, "DONE")
                logging.info(f"Buy order completed for {ticker} (details unavailable)")
                
            return result
        else:
            # Order failure - more detailed error handling
            error_msg = result.get('error', "Unknown error")
            if error_msg == "0" or not error_msg:
                error_msg = "Order execution failed - API returned empty response"
                
            logging.error(f"Buy order failed for {ticker}: {error_msg}")
            
            # Store detailed failure information
            notion_manager.update_signal_status(signal_id, "FAILED", {
                'error': error_msg,
                'retry_count': 0
            })
            
            # Better error notification
            notion_manager.slack.notify_error(f"{ticker} Buy Failed", f"Amount: {amount:,.0f} KRW\nError: {error_msg}")
            
            return result
    except Exception as e:
        error_msg = f"Error executing buy order: {str(e)}"
        logging.error(error_msg)
        
        try:
            # 예외 발생 시 Notion 상태 업데이트
            notion_manager.update_signal_status(signal_id, "FAILED", {
                'error': error_msg,
                'retry_count': 0
            })
            notion_manager.slack.notify_error(f"{ticker} 매수 예외 발생", error_msg)
        except Exception as update_error:
            logging.error(f"Failed to update signal status: {update_error}")
            
        return {'success': False, 'error': error_msg}

def execute_sell_with_monitoring(signal, notion_manager, executor, order_manager, upbit):
    """Enhanced sell order execution with proper status tracking"""
    try:
        ticker = f"KRW-{signal['properties']['Ticker']['select']['name']}"
        signal_id = signal['id']
        
        # 보유 가능한 수량 확인
        balance = upbit.get_balance(ticker)
        
        if balance <= 0:
            logging.warning(f"No balance available for {ticker}, cannot execute sell order")
            notion_manager.update_signal_status(signal_id, "SKIPPED", {
                'error': 'No balance available'
            })
            return {'success': False, 'error': 'No balance available'}
            
        avg_price = float(upbit.get_avg_buy_price(ticker))
        current_price = pyupbit.get_current_price(ticker)
        profit_rate = ((current_price / avg_price) - 1) * 100 if avg_price > 0 else 0
        
        logging.info(f"Executing SELL order for {ticker}: {balance} coins @ ~{current_price:,.0f} KRW")
        
        # Execute using the enhanced executor's method 
        result = executor.execute_sell_with_anti_slippage(ticker, balance)
        
        if result['success']:
            # 주문이 시작되었지만 완료되지 않은 경우
            if 'order' in result and 'uuid' in result['order']:
                order_id = result['order']['uuid']
                logging.info(f"Sell order placed for {ticker}: {balance} coins, order_id={order_id}")
                
                # 노션 상태 업데이트 - IN_PROGRESS
                notion_manager.update_signal_status(signal_id, "IN_PROGRESS", {
                    'order_id': order_id
                })
                
                # 주문 완료 기다리기
                order_result = order_manager.monitor_order(order_id, timeout=60)
                
                if order_result['state'] == 'done':
                    # 주문 완료된 경우
                    executed_price = float(order_result.get('avg_price', 0))
                    executed_amount = float(order_result.get('executed_volume', 0))
                    total_value = executed_price * executed_amount
                    
                    # 성공 상태 업데이트
                    notion_manager.update_signal_status(signal_id, "DONE", {
                        'order_id': order_id,
                        'price': executed_price,
                        'amount': executed_amount,
                        'total_value': total_value
                    })
                    
                    # 수익률 재계산
                    updated_profit_rate = ((executed_price / avg_price) - 1) * 100 if avg_price > 0 else 0
                    
                    # Slack 알림
                    slack_data = {
                        'ticker': ticker,
                        'amount': executed_amount,
                        'avg_price': avg_price,
                        'execution_price': executed_price,
                        'profit_rate': updated_profit_rate,
                        'order_id': order_id
                    }
                    notion_manager.slack.notify_signal_execution("SELL", slack_data)
                    
                    logging.info(f"Sell order completed for {ticker}: {executed_amount} @ {executed_price:,.0f} KRW, profit: {updated_profit_rate:.2f}%")
                    return {'success': True, 'order': order_result, 'status': 'DONE'}
                else:
                    # 주문이 완료되지 않은 경우
                    notion_manager.update_signal_status(signal_id, "FAILED", {
                        'order_id': order_id,
                        'error': f"Order timeout or cancelled: {order_result['state']}"
                    })
                    logging.error(f"Sell order incomplete for {ticker}: {order_result['state']}")
                    return {'success': False, 'order': order_result, 'status': 'FAILED', 
                            'error': f"Order state: {order_result['state']}"}
            
            # 주문이 즉시 완료된 경우
            if 'executed_price' in result:
                executed_price = result['executed_price']
                updated_profit_rate = ((executed_price / avg_price) - 1) * 100 if avg_price > 0 else 0
                
                notion_manager.update_signal_status(signal_id, "DONE", {
                    'price': executed_price,
                    'amount': balance,
                    'total_value': executed_price * balance
                })
                
                # Slack 알림
                slack_data = {
                    'ticker': ticker,
                    'amount': balance,
                    'avg_price': avg_price,
                    'execution_price': executed_price,
                    'profit_rate': updated_profit_rate
                }
                notion_manager.slack.notify_signal_execution("SELL", slack_data)
                
                logging.info(f"Sell order immediately executed for {ticker} @ {executed_price:,.0f} KRW, profit: {updated_profit_rate:.2f}%")
            else:
                notion_manager.update_signal_status(signal_id, "DONE")
                logging.info(f"Sell order completed for {ticker} (details unavailable)")
                
            return result
        else:
            # Order failure - more detailed error handling
            error_msg = result.get('error', "Unknown error")
            if error_msg == "0" or not error_msg:
                error_msg = "Order execution failed - API returned empty response"
                
            logging.error(f"Sell order failed for {ticker}: {error_msg}")
            
            # Store detailed failure information
            notion_manager.update_signal_status(signal_id, "FAILED", {
                'error': error_msg,
                'retry_count': 0
            })
            
            # Better error notification
            notion_manager.slack.notify_error(f"{ticker} Sell Failed", 
                                             f"Amount: {balance} coins\nPrice: ~{current_price:,.0f} KRW\nError: {error_msg}")
            
            return result
    except Exception as e:
        error_msg = f"Error executing sell order: {str(e)}"
        logging.error(error_msg)
        
        try:
            # 예외 발생 시 Notion 상태 업데이트
            notion_manager.update_signal_status(signal_id, "FAILED", {
                'error': error_msg,
                'retry_count': 0
            })
            notion_manager.slack.notify_error(f"{ticker} 매도 예외 발생", error_msg)
        except Exception as update_error:
            logging.error(f"Failed to update signal status: {update_error}")
            
        return {'success': False, 'error': error_msg}

def run_enhanced_trading_system(test_mode=True):
    """Enhanced trading system with momentum detection - improved execution and error handling
    
    In test mode: Generate signals immediately, execute after 5min, repeat after 1hr
    In normal mode: Generate at 9:00 KST, execute at 9:05 KST
    """
    # System initialization
    notion_manager = EnhancedNotionManager()
    slack = SlackNotifier()
    access_key = os.getenv('UPBIT_ACCESS_KEY')
    secret_key = os.getenv('UPBIT_SECRET_KEY')
    upbit = pyupbit.Upbit(access_key, secret_key)
    executor = EnhancedSmartOrderExecutor(access_key, secret_key)
    order_manager = OrderManager(upbit)
    allocator = CapitalAllocator()
    
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        mode_str = "TEST MODE" if test_mode else "PRODUCTION MODE"
        
        # Clear indicator of whether orders will be real or test orders
        if test_mode:
            logging.info("==================================================================")
            logging.info("=== TEST MODE ACTIVE - USING MINIMAL AMOUNTS FOR REAL ORDERS! ===")
            logging.info("==================================================================")
        
        logging.info(f"=== Starting Enhanced Trading System ({mode_str}) at {timestamp} ===")
        slack.notify_system_status("startup", {"test_mode": test_mode})
        
        # 1. Get current positions
        balances = upbit.get_balances()
        owned_coins = []
        for balance in balances:
            if balance['currency'] != 'KRW' and float(balance['balance']) > 0:
                owned_coins.append(f"KRW-{balance['currency']}")
        
        logging.info(f"Current portfolio: {len(owned_coins)} coins + KRW")
        
        # 2. Get trading candidates with momentum detection
        trading_candidates = get_trading_candidates(upbit, owned_coins, base_count=10)
        logging.info(f"Selected {len(trading_candidates)} total trading candidates")
        
        # 3. Generate enhanced signals
        signals = generate_enhanced_signals(trading_candidates, slack)
        
        # 4. Update Notion with enhanced signals
        signals_updated = notion_manager.update_daily_signals(signals)
        if not signals_updated:
            logging.error("Failed to update signals in Notion database")
            slack.notify_error("Signal Generation", "Failed to update Notion database with signals")
            # 계속 진행 (Notion DB 업데이트 실패해도 거래는 진행)
        
        # 5. Wait for execution time
        if test_mode:
            # Test mode: wait 5 minutes from now
            execution_time = datetime.now() + timedelta(minutes=5)
            wait_seconds = 5 * 60  # 5 minutes in seconds
            logging.info(f"TEST MODE: Waiting {wait_seconds/60:.1f} minutes until execution time ({execution_time.strftime('%H:%M:%S')})")
        else:
            # Normal mode: execute at 9:05 KST
            execution_time = datetime.now().replace(hour=9, minute=5, second=0, microsecond=0)
            if datetime.now() < execution_time:
                wait_seconds = (execution_time - datetime.now()).total_seconds()
                logging.info(f"Waiting {wait_seconds/60:.1f} minutes until execution time (9:05 KST)")
            else:
                wait_seconds = 0
                logging.info(f"Current time is past execution time, proceeding immediately")
                
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        
        # 6. Execute trades
        pending_signals = notion_manager.get_pending_signals()
        if not pending_signals:
            logging.warning("No pending signals found for execution")
            slack.notify_error("Signal Execution", "No pending signals found to execute")
            return
            
        execution_start_time = datetime.now()
        logging.info(f"Found {len(pending_signals)} pending signals for execution")
        
        # 시스템 시작시 모든 시그널 상태 확인 - PENDING이 아닌데 IN_PROGRESS인 경우 DONE으로 업데이트
        try:
            # 이전에 진행 중이던 시그널 상태 업데이트 (시스템이 비정상 종료된 경우 대비)
            in_progress_signals = []
            
            try:
                in_progress_results = notion_manager.notion.databases.query(
                    database_id=notion_manager.daily_signals_db_id,
                    filter={
                        "property": "Status",
                        "select": {
                            "equals": "IN_PROGRESS"
                        }
                    }
                )
                in_progress_signals = in_progress_results.get('results', [])
                
                if in_progress_signals:
                    logging.info(f"Found {len(in_progress_signals)} IN_PROGRESS signals from previous run, marking as DONE")
                    for signal in in_progress_signals:
                        notion_manager.update_signal_status(signal['id'], "DONE")
            except Exception as e:
                logging.error(f"Error checking IN_PROGRESS signals: {e}")
        except Exception as e:
            logging.error(f"Error updating IN_PROGRESS signals: {e}")
            
        # 포트폴리오 업데이트
        try:
            # 현재 포트폴리오 데이터 수집
            portfolio_data = []
            
            # Get KRW balance first
            krw_balance = upbit.get_balance("KRW")
            if krw_balance > 0:
                portfolio_data.append({
                    'ticker': 'KRW',
                    'amount': krw_balance,
                    'avg_price': 1,
                    'current_price': 1,
                    'total_value': krw_balance
                })
                
            # Then get all coin balances
            balances = upbit.get_balances()
            for balance in balances:
                if balance['currency'] != 'KRW':
                    ticker = balance['currency']  # Just the symbol (BTC, ETH, etc.)
                    full_ticker = f"KRW-{ticker}"
                    amount = float(balance['balance'])
                    avg_price = float(balance['avg_buy_price']) if 'avg_buy_price' in balance else 0
                    current_price = pyupbit.get_current_price(full_ticker)
                    
                    if amount > 0 and current_price:
                        portfolio_data.append({
                            'ticker': ticker,
                            'amount': amount,
                            'avg_price': avg_price, 
                            'current_price': current_price,
                            'total_value': amount * current_price
                        })
            
            logging.info(f"Collected portfolio data for {len(portfolio_data)} assets (including KRW)")
            
            # 포트폴리오 DB 업데이트 - 실패해도 계속 진행
            if portfolio_data:
                update_success = notion_manager.update_portfolio(portfolio_data)
                if not update_success:
                    logging.error("Failed to update portfolio in Notion database")
                else:
                    logging.info(f"Successfully updated portfolio with {len(portfolio_data)} positions")
            else:
                logging.warning("No portfolio data to update")
        
        except Exception as portfolio_error:
            logging.error(f"Failed to update portfolio: {portfolio_error}")
            slack.notify_error("Portfolio Update", f"Failed to update portfolio: {str(portfolio_error)}")
            # 오류가 발생해도 거래 계속 진행
            
        # Execute SELLs first
        sell_signals = [s for s in pending_signals if s['properties']['Signal']['select']['name'] == 'SELL']
        sell_results = []
        sell_count = 0
        total_sell_value = 0
        
        for signal in sell_signals:
            try:
                result = execute_sell_with_monitoring(signal, notion_manager, executor, order_manager, upbit)
                sell_results.append(result)
                
                if result.get('success', False):
                    sell_count += 1
                    if 'order' in result and 'executed_volume' in result['order'] and 'avg_price' in result['order']:
                        total_sell_value += float(result['order']['executed_volume']) * float(result['order']['avg_price'])
            except Exception as sell_error:
                logging.error(f"Error processing sell signal: {sell_error}")
                continue
        
        # Wait for sells to complete and market to stabilize
        logging.info(f"Completed {sell_count}/{len(sell_signals)} sell orders")
        time.sleep(3)  # 주문 완료를 기다려 시장에 영향을 주지 않도록 준비
        
        # Get updated balance and execute BUYs
        available_krw = upbit.get_balance("KRW")
        logging.info(f"Available KRW for buy orders: {available_krw:,.0f}")
        
        buy_signals = [s for s in pending_signals if s['properties']['Signal']['select']['name'] == 'BUY']
        
        # Prepare buy signal data for allocation
        buy_signal_data = []
        for signal in buy_signals:
            properties = signal['properties']
            buy_signal_data.append({
                'ticker': properties['Ticker']['select']['name'],
                'is_momentum': properties.get('Is_Momentum', {}).get('checkbox', False),
                'momentum_score': properties.get('Momentum_Score', {}).get('number', 0)
            })
        
        # Get capital allocations
        allocations = allocator.allocate_capital_dynamically(available_krw, buy_signal_data)
        logging.info(f"Capital allocation completed for {len(allocations)} buy signals")
        
        # Execute BUYs with allocated amounts
        buy_results = []
        buy_count = 0
        total_buy_value = 0
        
        for signal in buy_signals:
            ticker = signal['properties']['Ticker']['select']['name']
            if ticker in allocations:
                try:
                    result = execute_buy_with_amount(signal, allocations[ticker], notion_manager, executor, order_manager)
                    buy_results.append(result)
                    
                    if result.get('success', False):
                        buy_count += 1
                        total_buy_value += allocations[ticker]
                except Exception as buy_error:
                    logging.error(f"Error processing buy signal for {ticker}: {buy_error}")
                    continue
                    
        # Process HOLD signals - update them from PENDING to DONE
        hold_signals = [s for s in pending_signals if s['properties']['Signal']['select']['name'] == 'HOLD']
        hold_count = 0
        
        for signal in hold_signals:
            try:
                ticker = signal['properties']['Ticker']['select']['name']
                full_ticker = f"KRW-{ticker}"
                signal_id = signal['id']
                
                # Get coin data if it's owned
                amount = 0
                avg_price = 0
                current_price = 0
                profit_rate = 0
                
                try:
                    # Check if we own this coin
                    amount = upbit.get_balance(full_ticker)
                    if amount > 0:
                        avg_price = float(upbit.get_avg_buy_price(full_ticker))
                        current_price = pyupbit.get_current_price(full_ticker)
                        profit_rate = ((current_price / avg_price) - 1) * 100 if avg_price > 0 else 0
                except Exception as e:
                    logging.warning(f"Unable to get balance info for {ticker}: {e}")
                
                # Update signal status to DONE - don't try to update properties for HOLD
                # Simplify by just updating the status without execution data
                result = notion_manager.update_signal_status(signal_id, "DONE")
                
                # Send hold notification if we own the coin
                if amount > 0 and current_price > 0:
                    slack_data = {
                        'ticker': full_ticker,
                        'amount': amount,
                        'avg_price': avg_price,
                        'current_price': current_price,
                        'profit_rate': profit_rate
                    }
                    notion_manager.slack.notify_signal_execution("HOLD", slack_data)
                    
                hold_count += 1
                logging.info(f"Updated HOLD signal for {ticker} to DONE")
                
            except Exception as hold_error:
                logging.error(f"Error processing hold signal: {hold_error}")
                continue
        
        # Update portfolio again after all trades
        try:
            # 최종 포트폴리오 데이터 수집
            final_portfolio_data = []
            updated_balances = upbit.get_balances()
            
            for balance in updated_balances:
                ticker = balance['currency']
                amount = float(balance['balance'])
                avg_price = float(balance['avg_buy_price']) if 'avg_buy_price' in balance else 0
                current_price = 1 if ticker == 'KRW' else pyupbit.get_current_price(f"KRW-{ticker}")
                
                final_portfolio_data.append({
                    'ticker': ticker,
                    'amount': amount,
                    'avg_price': avg_price,
                    'current_price': current_price,
                    'total_value': amount * current_price
                })
            
            # DB 업데이트 - 실행 전에 한번 업데이트했기 때문에 여기서는 필요하지 않음
            # 대신, 아래에서 거래 실행 후 다시 업데이트합니다
            pass
        except Exception as final_portfolio_error:
            logging.error(f"Failed to update final portfolio: {final_portfolio_error}")
        
        # Update portfolio after all trades are completed
        try:
            logging.info("Updating portfolio after trade execution")
            
            # 최종 포트폴리오 데이터 수집
            final_portfolio_data = []
            
            # KRW balance first
            krw_balance = upbit.get_balance("KRW")
            if krw_balance > 0:
                final_portfolio_data.append({
                    'ticker': 'KRW',
                    'amount': krw_balance,
                    'avg_price': 1,
                    'current_price': 1,
                    'total_value': krw_balance
                })
            
            # Then all coin balances
            balances = upbit.get_balances()
            for balance in balances:
                if balance['currency'] != 'KRW':
                    ticker = balance['currency']
                    full_ticker = f"KRW-{ticker}"
                    amount = float(balance['balance'])
                    avg_price = float(balance['avg_buy_price']) if 'avg_buy_price' in balance else 0
                    current_price = pyupbit.get_current_price(full_ticker)
                    
                    if amount > 0 and current_price:
                        final_portfolio_data.append({
                            'ticker': ticker,
                            'amount': amount,
                            'avg_price': avg_price,
                            'current_price': current_price,
                            'total_value': amount * current_price
                        })
            
            # Update Notion portfolio DB
            if final_portfolio_data:
                notion_manager.update_portfolio(final_portfolio_data)
                
            # Calculate portfolio stats for notification
            total_value = sum(p.get('total_value', 0) for p in final_portfolio_data)
            non_krw = [p for p in final_portfolio_data if p.get('ticker') != 'KRW']
            
            # Calculate average profit
            profit_positions = [p for p in non_krw if p.get('avg_price', 0) > 0]
            avg_profit = 0
            if profit_positions:
                profits = [((p.get('current_price', 0) / p.get('avg_price', 1)) - 1) * 100 for p in profit_positions]
                avg_profit = sum(profits) / len(profits) if profits else 0
                
            # Send portfolio update notification
            slack.notify_system_status("portfolio_update", {
                'total_value': total_value,
                'coin_count': len(non_krw),
                'profit': avg_profit,
                'positions': non_krw
            })
            
        except Exception as final_update_error:
            logging.error(f"Failed to update final portfolio: {final_update_error}")
            
        # Final reporting
        execution_duration = (datetime.now() - execution_start_time).total_seconds() / 60
        
        # Collect executed trades for report
        executed_trades = []
        for result in sell_results + buy_results:
            if result.get('success') and 'order' in result:
                order = result['order']
                executed_trades.append({
                    'ticker': order.get('market', 'unknown'),
                    'type': 'SELL' if order.get('side') == 'ask' else 'BUY',
                    'price': float(order.get('avg_price', 0)),
                    'amount': float(order.get('executed_volume', 0)),
                    'value': float(order.get('executed_volume', 0)) * float(order.get('avg_price', 0))
                })
        
        # 종합 실행 보고서 전송
        slack.notify_system_status("execution_summary", {
            'buy_count': buy_count,
            'sell_count': sell_count,
            'hold_count': hold_count,
            'total_invested': total_buy_value,
            'total_returned': total_sell_value,
            'duration_minutes': execution_duration,
            'trades': executed_trades
        })
        
        logging.info(f"=== Trading System Completed ({execution_duration:.1f} minutes) ===")
        logging.info(f"Buy orders: {buy_count}/{len(buy_signals)} completed, {total_buy_value:,.0f} KRW invested")
        logging.info(f"Sell orders: {sell_count}/{len(sell_signals)} completed, {total_sell_value:,.0f} KRW returned")
        logging.info(f"Hold signals: {hold_count}/{len(hold_signals)} updated to DONE")
        
    except Exception as e:
        error_message = f"Error in trading system: {str(e)}"
        logging.error(error_message)
        slack.notify_error("System Error", error_message)

def wait_until_execution_time(test_mode=True):
    """Wait until execution time for signal generation
    
    In test mode: Immediate execution
    In normal mode: Wait until 09:00:00 KST
    """
    if test_mode:
        logging.info("TEST MODE: Generating signals immediately")
        return
    else:
        # Normal production schedule
        target_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        
        if datetime.now() >= target_time:
            target_time += timedelta(days=1)
        
        wait_seconds = (target_time - datetime.now()).total_seconds()
        logging.info(f"Waiting {wait_seconds/3600:.1f} hours until 09:00:00 KST")
        time.sleep(wait_seconds)

if __name__ == "__main__":
    # Set TEST_MODE to True for testing, False for production
    # IMPORTANT: Change to False when ready for real trading with full amounts
    TEST_MODE = False
    # Export TEST_MODE environment variable for order executors
    os.environ['TEST_MODE'] = str(TEST_MODE)
    test_iteration = 0
    
    while True:
        try:
            if TEST_MODE:
                # In test mode, we run a limited number of iterations
                test_iteration += 1
                logging.info(f"\n==== TEST ITERATION {test_iteration} ====\n")
                slack = SlackNotifier()
                slack.notify_system_status("test_iteration", {"iteration": test_iteration})
                
                # Stop after 2 iterations in test mode
                if test_iteration > 2:
                    logging.info("\n==== TEST COMPLETED - TWO ITERATIONS FINISHED ====\n")
                    logging.info("To run in production mode, change TEST_MODE to False")
                    slack.notify_system_status("test_completed", {"message": "Test completed successfully"})
                    break
            else:
                # In production mode - show clear indicator
                logging.info("\n==== PRODUCTION MODE RUNNING - USING FULL ORDER AMOUNTS ====\n")
                slack = SlackNotifier()
                slack.notify_system_status("production_running", {
                    "message": "System running in PRODUCTION mode with FULL order amounts"})
            
            # Generate signals (either immediately in test mode or at 9:00 KST in production)
            wait_until_execution_time(TEST_MODE)
            run_enhanced_trading_system(TEST_MODE)
            
            if TEST_MODE:
                # In test mode, wait 1 hour before next iteration
                wait_time = 60 * 60  # 1 hour in seconds
                logging.info(f"TEST MODE: Waiting {wait_time/60:.1f} minutes until next test iteration")
                time.sleep(wait_time)
            
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            # Notify about critical error
            try:
                slack = SlackNotifier()
                slack.notify_error("Critical System Error", f"Error in main loop: {str(e)}")
            except:
                pass
            time.sleep(60)