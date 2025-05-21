import os
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import datetime
import json

# .env 파일 로드
load_dotenv()

class SlackNotifier:
    def __init__(self):
        self.token = os.getenv('SLACK_BOT_TOKEN')
        self.channel = os.getenv('SLACK_CHANNEL')
        
        # Check if credentials are available
        self.enabled = bool(self.token and self.channel)
        
        if self.enabled:
            self.client = WebClient(token=self.token)
            print(f"SlackNotifier initialized: channel={self.channel}")
        else:
            print("WARNING: Slack notifications disabled - missing token or channel")
        
    def send_notification(self, message, blocks=None):
        """Send notification to Slack - with rich blocks support"""
        # Skip if Slack is not configured
        if not self.enabled:
            return False
            
        try:
            # Truncate long messages in logs
            log_message = message[:50] + "..." if len(message) > 50 else message
            print(f"Sending Slack message: {log_message}")
            
            params = {
                "channel": self.channel,
                "text": message
            }
            
            if blocks:
                params["blocks"] = blocks
                
            response = self.client.chat_postMessage(**params)
            
            if not response["ok"]:
                print(f"Slack message failed: {response.get('error', 'Unknown error')}")
                return False
                
            return True
            
        except SlackApiError as e:
            print(f"Slack API error: {e.response['error']}")
            return False
        except Exception as e:
            print(f"Unexpected error sending Slack message: {str(e)}")
            return False
            
    def notify_signal_execution(self, execution_type, data):
        """시그널 실행 결과 알림 - 강화된 정보 제공"""
        try:
            if execution_type == "SELL":
                message, blocks = self._format_sell_notification(data)
            elif execution_type == "BUY":
                message, blocks = self._format_buy_notification(data)
            elif execution_type == "HOLD":
                message, blocks = self._format_hold_notification(data)
            else:
                return False
                
            return self.send_notification(message, blocks)
        except Exception as e:
            print(f"Error sending execution notification: {e}")
            return False
            
    def _format_sell_notification(self, data):
        """매도 실행 알림 포맷 - 리치 블록 포맷 추가"""
        execution_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Extract ticker for display (without KRW- prefix)
        ticker_display = data['ticker'].replace("KRW-", "") if data['ticker'].startswith("KRW-") else data['ticker']
        
        # 기본 텍스트 메시지
        message = f"""
🔴 매도 실행 완료: {ticker_display}
코인: {ticker_display}
수량: {data['amount']}
평균가: {data['avg_price']:,.0f} KRW
실행가: {data['execution_price']:,.0f} KRW
수익률: {data['profit_rate']:.2f}%
실행시간: {execution_time}
"""
        
        # 리치 블록 포맷
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🔴 매도 실행 완료: {ticker_display}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*코인:*\n{ticker_display}"},
                    {"type": "mrkdwn", "text": f"*수량:*\n{data['amount']}"},
                    {"type": "mrkdwn", "text": f"*평균가:*\n{data['avg_price']:,.0f} KRW"},
                    {"type": "mrkdwn", "text": f"*실행가:*\n{data['execution_price']:,.0f} KRW"},
                    {"type": "mrkdwn", "text": f"*수익률:*\n{data['profit_rate']:.2f}%"},
                    {"type": "mrkdwn", "text": f"*실행시간:*\n{execution_time}"}
                ]
            },
            {"type": "divider"}
        ]
        
        if 'order_id' in data:
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Order ID: {data['order_id']}"}
                ]
            })
            
        return message, blocks
            
    def _format_buy_notification(self, data):
        """매수 실행 알림 포맷 - 리치 블록 포맷 추가"""
        execution_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Extract ticker for display (without KRW- prefix)
        ticker_display = data['ticker'].replace("KRW-", "") if data['ticker'].startswith("KRW-") else data['ticker']
        
        # 기본 텍스트 메시지
        message = f"""
🟢 매수 실행 완료: {ticker_display}
코인: {ticker_display}
수량: {data['amount']}
매수가: {data['execution_price']:,.0f} KRW
투자금액: {data['investment_amount']:,.0f} KRW
실행시간: {execution_time}
"""
        
        # 리치 블록 포맷 
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🟢 매수 실행 완료: {ticker_display}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*코인:*\n{ticker_display}"},
                    {"type": "mrkdwn", "text": f"*수량:*\n{data['amount']}"},
                    {"type": "mrkdwn", "text": f"*매수가:*\n{data['execution_price']:,.0f} KRW"},
                    {"type": "mrkdwn", "text": f"*투자금액:*\n{data['investment_amount']:,.0f} KRW"},
                    {"type": "mrkdwn", "text": f"*실행시간:*\n{execution_time}"}
                ]
            },
            {"type": "divider"}
        ]
        
        if 'order_id' in data:
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Order ID: {data['order_id']}"}
                ]
            })
        
        # 모멘텀 정보가 있으면 추가
        if 'is_momentum' in data and data['is_momentum']:
            blocks.append({
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"🚀 모멘텀 트레이드 (스코어: {data.get('momentum_score', 0):.1f})"}
                ]
            })
            
        return message, blocks
            
    def _format_hold_notification(self, data):
        """Format HOLD status notification with rich blocks"""
        update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Extract ticker for display (without KRW- prefix)
        ticker_display = data['ticker'].replace("KRW-", "") if data['ticker'].startswith("KRW-") else data['ticker']
        
        # Calculate profit emoji
        profit_emoji = "🟢" if data['profit_rate'] >= 0 else "🔴"
        
        # Basic text message
        message = f"""
⚪ HOLD Status Updated: {ticker_display}
Coin: {ticker_display}
Amount: {data['amount']}
Avg Price: {data['avg_price']:,.0f} KRW
Current Price: {data['current_price']:,.0f} KRW
Profit: {profit_emoji} {data['profit_rate']:.2f}%
Time: {update_time}
"""
        
        # Rich block format
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"⚪ HOLD Status Updated: {ticker_display}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Coin:*\n{ticker_display}"},
                    {"type": "mrkdwn", "text": f"*Amount:*\n{data['amount']}"},
                    {"type": "mrkdwn", "text": f"*Avg Price:*\n{data['avg_price']:,.0f} KRW"},
                    {"type": "mrkdwn", "text": f"*Current Price:*\n{data['current_price']:,.0f} KRW"},
                    {"type": "mrkdwn", "text": f"*Profit:*\n{profit_emoji} {data['profit_rate']:.2f}%"},
                    {"type": "mrkdwn", "text": f"*Update Time:*\n{update_time}"}
                ]
            },
            {"type": "divider"}
        ]
        
        return message, blocks
            
    def notify_error(self, error_type, error_message):
        """Send error notification with rich block format"""
        error_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Basic text message
        message = f"""
❌ Error Occurred
Type: {error_type}
Message: {error_message}
Time: {error_time}
"""
        
        # Rich block format
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"❌ Error: {error_type}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Type:*\n{error_type}"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{error_time}"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error Message:*\n```{error_message}```"
                }
            },
            {"type": "divider"}
        ]
        
        return self.send_notification(message, blocks)
        
    def notify_system_status(self, status_type, data):
        """시스템 상태 알림 - 종합 상태 보고"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if status_type == "startup":
            # Check if we're in test mode
            is_test_mode = data.get('test_mode', False)
            mode_str = "🧪 TEST MODE (Small Amounts)" if is_test_mode else "🔴 PRODUCTION MODE (Full Amounts)"
            
            message = f"🚀 Trading System Started - {mode_str} ({timestamp})"
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚀 MRHA Trading System Starting - {mode_str}",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*시작 시간:*\n{timestamp}"},
                        {"type": "mrkdwn", "text": f"*시스템 버전:*\nEnhanced 2.0"},
                        {"type": "mrkdwn", "text": f"*Mode:*\n{mode_str}"}
                    ]
                },
                {"type": "divider"}
            ]
            
        elif status_type == "execution_summary":
            buy_count = data.get('buy_count', 0)
            sell_count = data.get('sell_count', 0)
            hold_count = data.get('hold_count', 0)
            total_invested = data.get('total_invested', 0)
            total_returned = data.get('total_returned', 0)
            
            message = f"📊 Trade Execution Summary ({timestamp})\nBuy: {buy_count}, Sell: {sell_count}, Hold: {hold_count}"
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📊 Trade Execution Summary",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Buy Orders:*\n{buy_count}"},
                        {"type": "mrkdwn", "text": f"*Sell Orders:*\n{sell_count}"},
                        {"type": "mrkdwn", "text": f"*Hold Updates:*\n{hold_count}"},
                        {"type": "mrkdwn", "text": f"*Total Invested:*\n{total_invested:,.0f} KRW"},
                        {"type": "mrkdwn", "text": f"*Total Returned:*\n{total_returned:,.0f} KRW"},
                        {"type": "mrkdwn", "text": f"*Completion Time:*\n{timestamp}"}
                    ]
                }
            ]
            
            # 트레이드 목록 추가
            if 'trades' in data and data['trades']:
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*실행된 트레이드:*"
                    }
                })
                
                for trade in data['trades'][:10]:  # 최대 10개까지 표시
                    emoji = "🟢" if trade['type'] == "BUY" else "🔴"
                    ticker = trade.get('ticker', '').replace('KRW-', '')
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{emoji} *{ticker}*: {trade['type']} @ {trade['price']:,.0f} KRW"
                        }
                    })
        
        elif status_type == "portfolio_update":
            total_value = data.get('total_value', 0)
            coin_count = data.get('coin_count', 0)
            profit = data.get('profit', 0)
            
            message = f"💼 포트폴리오 업데이트 ({timestamp})\n총 자산: {total_value:,.0f} KRW"
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "💼 포트폴리오 업데이트",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*총 자산:*\n{total_value:,.0f} KRW"},
                        {"type": "mrkdwn", "text": f"*보유 코인 수:*\n{coin_count}"},
                        {"type": "mrkdwn", "text": f"*수익률:*\n{profit:.2f}%"},
                        {"type": "mrkdwn", "text": f"*업데이트 시간:*\n{timestamp}"}
                    ]
                }
            ]
            
            # 보유 코인 목록 추가
            if 'positions' in data and data['positions']:
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*보유 코인:*"
                    }
                })
                
                positions_text = ""
                for pos in data['positions'][:15]:  # 최대 15개까지 표시
                    if pos['ticker'] == "KRW":
                        continue
                    profit_emoji = "🟢" if pos['profit_rate'] >= 0 else "🔴"
                    positions_text += f"{profit_emoji} *{pos['ticker']}*: {pos['profit_rate']:.2f}%\n"
                
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": positions_text
                    }
                })
                
        elif status_type == "signals_update":
            total = data.get('total', 0)
            success = data.get('success', 0)
            failed = data.get('failed', 0)
            buy_count = data.get('buy_count', 0)
            sell_count = data.get('sell_count', 0)
            hold_count = data.get('hold_count', 0)
            momentum_count = data.get('momentum_count', 0)
            
            message = f"📝 시그널 업데이트 ({timestamp})\n총 {total}개 시그널"
            
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "📝 시그널 생성 완료",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*총 시그널:*\n{total}개"},
                        {"type": "mrkdwn", "text": f"*업데이트 상태:*\n성공: {success}, 실패: {failed}"},
                        {"type": "mrkdwn", "text": f"*BUY 시그널:*\n{buy_count}개"},
                        {"type": "mrkdwn", "text": f"*SELL 시그널:*\n{sell_count}개"},
                        {"type": "mrkdwn", "text": f"*HOLD 시그널:*\n{hold_count}개"},
                        {"type": "mrkdwn", "text": f"*모멘텀 시그널:*\n{momentum_count}개"},
                        {"type": "mrkdwn", "text": f"*생성 시간:*\n{timestamp}"}
                    ]
                }
            ]
        
        elif status_type == "test_iteration":
            iteration = data.get('iteration', 0)
            message = f"🧪 테스트 반복 {iteration} 시작 ({timestamp})"
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🧪 테스트 반복 {iteration} 시작",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"이 테스트 반복에서는 즉시 시그널을 생성하고 5분 후에 실행합니다.\n다음 테스트 반복은 1시간 후에 시작됩니다."
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*반복 횟수:*\n{iteration}"},
                        {"type": "mrkdwn", "text": f"*시작 시간:*\n{timestamp}"}
                    ]
                },
                {"type": "divider"}
            ]
            
        elif status_type == "test_completed":
            message = f"✅ Test Mode Completed ({timestamp})"
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Test Mode Completed",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Test mode execution is complete. To switch to production mode, set TEST_MODE = False in the code."
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Completion Time:*\n{timestamp}"},
                        {"type": "mrkdwn", "text": "*Next Step:*\nSet TEST_MODE = False for full trading"}
                    ]
                },
                {"type": "divider"}
            ]
            
        elif status_type == "production_running":
            message = f"🔴 PRODUCTION MODE ACTIVE - FULL ORDER AMOUNTS ({timestamp})"
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "🔴 PRODUCTION MODE ACTIVE - FULL ORDER AMOUNTS",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "⚠️ *ATTENTION: The system is running in PRODUCTION mode with FULL order amounts.* ⚠️"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Current Time:*\n{timestamp}"},
                        {"type": "mrkdwn", "text": "*Status:*\nMonitoring for signals"}
                    ]
                },
                {"type": "divider"}
            ]
            
        else:  # 기본 상태 메시지
            message = f"ℹ️ 시스템 상태: {status_type} ({timestamp})"
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*시스템 상태:* {status_type}\n*시간:* {timestamp}"
                    }
                }
            ]
        
        return self.send_notification(message, blocks)