#!/usr/bin/env python3
"""
MRHA 트레이딩 시스템용 고정 Notion 매니저

이 클래스는 Notion API와 상호작용하기 위한 간소화된 클래스로,
구체적인 속성 이름과 단순한 API 호출을 사용합니다.
"""

import os
import time
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client
from slack_notifier import SlackNotifier

# 환경 변수 로드
load_dotenv()

class FixedNotionManager:
    """
    정확한 DB 스키마 속성을 사용하는 단순화된 Notion 매니저
    """
    def __init__(self):
        # 환경 변수 로드 확인
        self.notion_token = os.getenv('NOTION_TOKEN')
        self.daily_signals_db_id = os.getenv('DAILY_SIGNALS_DB_ID')
        self.portfolio_db_id = os.getenv('PORTFOLIO_DB_ID')
        
        if not all([self.notion_token, self.daily_signals_db_id, self.portfolio_db_id]):
            raise ValueError("필수 환경 변수가 설정되지 않았습니다.")
            
        self.notion = Client(auth=self.notion_token)
        self.slack = SlackNotifier()
        
        print("Notion 매니저 초기화 완료")
        print(f"일일 시그널 DB: {self.daily_signals_db_id}")
        print(f"포트폴리오 DB: {self.portfolio_db_id}")
    
    def update_daily_signals(self, signals_data):
        """
        일일 시그널 DB 업데이트
        """
        print(f"{len(signals_data)}개 시그널로 DB 업데이트 시작...")
        self.slack.send_notification(f"💾 {len(signals_data)}개 시그널 업데이트 시작...")
        
        try:
            # 기존 데이터 삭제
            print("기존 시그널 삭제 중...")
            try:
                results = self.notion.databases.query(
                    database_id=self.daily_signals_db_id,
                    page_size=100
                )
                
                for page in results.get('results', []):
                    if page and 'id' in page:
                        self.notion.pages.update(
                            page_id=page['id'],
                            archived=True
                        )
                        time.sleep(0.2)
                print(f"{len(results.get('results', []))}개 시그널 삭제 완료")
            except Exception as e:
                print(f"시그널 삭제 중 오류: {e}")
                self.slack.notify_error("시그널 삭제 실패", str(e))
            
            # 새 시그널 추가
            success_count = 0
            fail_count = 0
            momentum_count = 0
            
            for signal in signals_data:
                try:
                    today = datetime.now().strftime('%Y-%m-%d')
                    
                    # 기본 속성
                    properties = {
                        "Record ID": {
                            "title": [{
                                "text": {
                                    "content": f"{datetime.now().strftime('%Y%m%d')}-{signal['ticker']}"
                                }
                            }]
                        },
                        "Date": {
                            "date": {
                                "start": today
                            }
                        },
                        "Ticker": {
                            "select": {
                                "name": signal['ticker']
                            }
                        },
                        "Rank": {
                            "number": signal['rank']
                        },
                        "Trading_Value": {
                            "number": signal['trading_value']
                        },
                        "Signal": {
                            "select": {
                                "name": signal['signal']
                            }
                        },
                        "Status": {
                            "select": {
                                "name": "PENDING"
                            }
                        },
                        "Execution_time": {
                            "date": {
                                "start": today
                            }
                        }
                    }
                    
                    # 모멘텀 필드 추가
                    if 'is_momentum' in signal:
                        properties["Is_Momentum"] = {
                            "checkbox": signal['is_momentum']
                        }
                        if signal['is_momentum']:
                            momentum_count += 1
                    
                    if 'momentum_score' in signal:
                        properties["Momentum_Score"] = {
                            "number": signal['momentum_score']
                        }
                    
                    if 'signal_strength' in signal:
                        properties["Signal_Strength"] = {
                            "number": signal['signal_strength']
                        }
                    
                    # 시그널 생성
                    result = self.notion.pages.create(
                        parent={"database_id": self.daily_signals_db_id},
                        properties=properties
                    )
                    
                    if result and 'id' in result:
                        print(f"{signal['ticker']} 시그널 추가 성공")
                        success_count += 1
                    else:
                        print(f"{signal['ticker']} 시그널 추가 실패")
                        fail_count += 1
                    
                    time.sleep(0.3)
                    
                except Exception as e:
                    print(f"{signal.get('ticker', 'unknown')} 시그널 추가 실패: {e}")
                    fail_count += 1
                    continue
            
            # 알림 전송
            notification_msg = f"""
📊 일일 시그널 생성 완료
생성시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
총 시그널 수: {len(signals_data)}
성공: {success_count}, 실패: {fail_count}
BUY 시그널: {len([s for s in signals_data if s['signal'] == 'BUY'])}
SELL 시그널: {len([s for s in signals_data if s['signal'] == 'SELL'])}
HOLD 시그널: {len([s for s in signals_data if s['signal'] == 'HOLD'])}
모멘텀 시그널: {momentum_count}
"""
            self.slack.send_notification(notification_msg)
            print(f"시그널 업데이트 완료")
            return success_count > 0
            
        except Exception as e:
            error_msg = f"시그널 업데이트 중 오류: {e}"
            print(error_msg)
            self.slack.notify_error("시그널 업데이트 실패", error_msg)
            return False
    
    def update_signal_status(self, signal_id, status, execution_data=None):
        """
        시그널 상태 업데이트 - 각 단계별 Slack 알림 추가
        """
        ticker = "Unknown"
        signal_type = "Unknown"
        old_status = "Unknown"
        
        # 현재 시그널 정보 가져오기
        try:
            signal_page = self.notion.pages.retrieve(page_id=signal_id)
            if 'properties' in signal_page:
                # 티커 정보 추출
                if 'Ticker' in signal_page['properties']:
                    ticker_prop = signal_page['properties']['Ticker']
                    if 'select' in ticker_prop and ticker_prop['select'] and 'name' in ticker_prop['select']:
                        ticker = ticker_prop['select']['name']
                
                # 시그널 타입 추출 (BUY/SELL/HOLD)
                if 'Signal' in signal_page['properties']:
                    signal_prop = signal_page['properties']['Signal']
                    if 'select' in signal_prop and signal_prop['select'] and 'name' in signal_prop['select']:
                        signal_type = signal_prop['select']['name']
                
                # 현재 상태 확인
                if 'Status' in signal_page['properties']:
                    status_prop = signal_page['properties']['Status']
                    if 'select' in status_prop and status_prop['select'] and 'name' in status_prop['select']:
                        old_status = status_prop['select']['name']
        except Exception as e:
            print(f"시그널 정보 추출 중 오류: {e}")
            
        # Log update attempt
        print(f"⏳ {ticker} ({signal_type}) signal status update: {old_status} → {status}")
        
        # Don't send start notification to avoid excessive messages
        emoji = "✅" if status == "DONE" else "⚠️" if status == "FAILED" else "🔄" if status == "IN_PROGRESS" else "📝"
        
        # 업데이트 속성 준비
        update_properties = {
            "Status": {
                "select": {
                    "name": status
                }
            },
            "Execution_time": {
                "date": {
                    "start": datetime.now().isoformat()
                }
            }
        }
        
        # 추가 정보 있으면 포함
        execution_price = None
        execution_amount = None
        total_value = None
        order_id = None
        error_message = None
        
        if execution_data:
            if 'price' in execution_data:
                execution_price = execution_data.get('price', 0)
                update_properties["Execution_Price"] = {
                    "number": execution_price
                }
            if 'amount' in execution_data:
                execution_amount = execution_data.get('amount', 0)
                update_properties["Amount"] = {
                    "number": execution_amount
                }
            if 'total_value' in execution_data:
                total_value = execution_data.get('total_value', 0)
                update_properties["Transaction_Value"] = {
                    "number": total_value
                }
            if 'order_id' in execution_data:
                order_id = execution_data.get('order_id', '')
                update_properties["Order_ID"] = {
                    "rich_text": [{
                        "text": {
                            "content": order_id
                        }
                    }]
                }
            if 'error' in execution_data and status == "FAILED":
                error_message = execution_data.get('error', 'Unknown error')
                update_properties["Error_Message"] = {
                    "rich_text": [{
                        "text": {
                            "content": error_message
                        }
                    }]
                }
        
        # 업데이트 시도 (최대 3번)
        for attempt in range(3):
            try:
                # Just log the API call attempt, don't send Slack notification
                print(f"🔄 Notion API call: {ticker} status update (attempt {attempt+1}/3)")
                
                # Actual API call
                result = self.notion.pages.update(
                    page_id=signal_id,
                    properties=update_properties
                )
                
                # 업데이트 성공 확인
                time.sleep(1)
                verify = self.notion.pages.retrieve(page_id=signal_id)
                
                if 'properties' in verify and 'Status' in verify['properties']:
                    status_prop = verify['properties']['Status']
                    if 'select' in status_prop and status_prop['select'] and 'name' in status_prop['select']:
                        verified_status = status_prop['select']['name']
                        
                        if verified_status == status:
                            # 3. 성공 알림
                            success_msg = f"✅ {ticker} 상태 업데이트 성공: {old_status} → {status}"
                            
                            # 추가 정보가 있으면 포함
                            details = []
                            if execution_price:
                                details.append(f"실행가: {execution_price:,.0f}원")
                            if execution_amount:
                                details.append(f"수량: {execution_amount:.8f}")
                            if total_value:
                                details.append(f"총액: {total_value:,.0f}원")
                            if order_id:
                                details.append(f"주문ID: {order_id[:8]}...")
                            
                            if details:
                                success_msg += f" ({', '.join(details)})"
                            
                            print(success_msg)
                            self.slack.send_notification(success_msg)
                            return True
                
                # Verification failure - just log it, don't send Slack
                print(f"⚠️ {ticker} status update verification failed, retrying {attempt+1}/3")
                time.sleep(2)
                
            except Exception as e:
                # Log error but don't send intermediate Slack notifications
                error_msg = f"❌ {ticker} status update error ({attempt+1}/3): {type(e).__name__}"
                print(f"{error_msg}: {str(e)}")
                time.sleep(3)
                
                # Only send Slack notification after the final attempt fails
                if attempt == 2:  # Last attempt
                    self.slack.notify_error(f"{ticker} Status Update Failed", str(e))
                    return False
        
        return False
    
    def get_pending_signals(self):
        """
        PENDING 상태의 시그널 조회 - 상세 알림 추가
        """
        try:
            # 시그널 조회 시작 알림
            start_msg = "🔎 PENDING 시그널 조회 중..."
            print(start_msg)
            self.slack.send_notification(start_msg)
            
            # API 호출
            results = self.notion.databases.query(
                database_id=self.daily_signals_db_id,
                filter={
                    "property": "Status",
                    "select": {
                        "equals": "PENDING"
                    }
                },
                page_size=100
            )
            
            signals = results.get('results', [])
            print(f"PENDING 상태의 시그널 {len(signals)}개 조회 완료")
            
            # 각 시그널의 타입(BUY/SELL/HOLD)에 따라 분류
            buy_signals = []
            sell_signals = []
            hold_signals = []
            unknown_signals = []
            
            # 티커 목록 가져오기
            for signal in signals:
                if 'properties' in signal and 'Ticker' in signal['properties'] and 'Signal' in signal['properties']:
                    ticker_prop = signal['properties']['Ticker']
                    signal_prop = signal['properties']['Signal']
                    
                    if ('select' in ticker_prop and ticker_prop['select'] and 'name' in ticker_prop['select'] and
                        'select' in signal_prop and signal_prop['select'] and 'name' in signal_prop['select']):
                        
                        ticker = ticker_prop['select']['name']
                        signal_type = signal_prop['select']['name']
                        
                        if signal_type == "BUY":
                            buy_signals.append(ticker)
                        elif signal_type == "SELL":
                            sell_signals.append(ticker)
                        elif signal_type == "HOLD":
                            hold_signals.append(ticker)
                        else:
                            unknown_signals.append(ticker)
            
            # 상세 통계와 함께 알림 전송
            if signals:
                signal_details = []
                if buy_signals:
                    signal_details.append(f"BUY: {len(buy_signals)}개 ({', '.join(buy_signals[:3])}{' 외 더 있음' if len(buy_signals) > 3 else ''})")
                if sell_signals:
                    signal_details.append(f"SELL: {len(sell_signals)}개 ({', '.join(sell_signals[:3])}{' 외 더 있음' if len(sell_signals) > 3 else ''})")
                if hold_signals:
                    signal_details.append(f"HOLD: {len(hold_signals)}개 ({', '.join(hold_signals[:3])}{' 외 더 있음' if len(hold_signals) > 3 else ''})")
                
                detail_msg = f"🔑 {len(signals)}개 PENDING 시그널 발견\n" + "\n".join(signal_details)
                print(detail_msg)
                self.slack.send_notification(detail_msg)
                
                # 각 시그널의 상세 내용 출력 (최대 10개)
                for i, signal in enumerate(signals[:10]):
                    if 'properties' in signal and 'Ticker' in signal['properties'] and 'Signal' in signal['properties']:
                        ticker = signal['properties']['Ticker']['select']['name'] if 'select' in signal['properties']['Ticker'] and signal['properties']['Ticker']['select'] else "Unknown"
                        signal_type = signal['properties']['Signal']['select']['name'] if 'select' in signal['properties']['Signal'] and signal['properties']['Signal']['select'] else "Unknown"
                        
                        signal_msg = f"{i+1}. {ticker} 시그널: {signal_type} (상태: PENDING)"
                        print(signal_msg)
                        # 개별 시그널 알림은 너무 많아서 Slack으로 전송하지 않음
            else:
                no_signals_msg = "🚩 실행할 PENDING 시그널이 없습니다."
                print(no_signals_msg)
                self.slack.send_notification(no_signals_msg)
            
            return signals
            
        except Exception as e:
            error_msg = f"PENDING 시그널 조회 중 오류: {e}"
            print(error_msg)
            self.slack.notify_error("시그널 조회 실패", error_msg)
            return []
    
    def get_average_price_from_notion(self, ticker: str) -> float:
        """
        Notion 포트폴리오 DB에서 특정 티커의 평균 매수 단가를 가져옵니다.
        """
        try:
            response = self.notion.databases.query(
                database_id=self.portfolio_db_id,
                filter={
                    "property": "Ticker",
                    "select": {
                        "equals": ticker
                    }
                }
            )
            
            results = response.get('results', [])
            if not results:
                print(f"Notion에서 {ticker}에 대한 포지션 정보를 찾을 수 없습니다.")
                return 0.0

            # 가장 최근 항목을 사용 (여러 개가 있을 경우)
            page = results[0]
            properties = page.get('properties', {})
            
            avg_price_prop = properties.get('Average_Price')
            if avg_price_prop and avg_price_prop.get('number') is not None:
                avg_price = float(avg_price_prop['number'])
                print(f"Notion에서 {ticker}의 평균 매수 단가 조회 성공: {avg_price:,.0f} KRW")
                return avg_price
            else:
                print(f"Notion의 {ticker} 항목에 'Average_Price' 속성이 없거나 값이 비어있습니다.")
                return 0.0

        except Exception as e:
            error_msg = f"Notion에서 평균 매수 단가 조회 중 오류 발생 ({ticker}): {e}"
            print(error_msg)
            self.slack.notify_error("Notion 조회 오류", error_msg)
            return 0.0

    def update_portfolio(self, portfolio_data):
        """
        포트폴리오 DB 업데이트
        """
        print(f"{len(portfolio_data)}개 포트폴리오 항목 업데이트 시작...")
        self.slack.send_notification(f"💼 {len(portfolio_data)}개 포트폴리오 항목 업데이트 시작...")
        
        try:
            # 기존 데이터 삭제
            print("기존 포트폴리오 항목 삭제 중...")
            try:
                results = self.notion.databases.query(
                    database_id=self.portfolio_db_id,
                    page_size=100
                )
                
                for page in results.get('results', []):
                    if page and 'id' in page:
                        self.notion.pages.update(
                            page_id=page['id'],
                            archived=True
                        )
                        time.sleep(0.1)
                
                print(f"{len(results.get('results', []))}개 포트폴리오 항목 삭제 완료")
                time.sleep(0.5)  # 삭제 완료 대기
                
            except Exception as e:
                print(f"포트폴리오 항목 삭제 중 오류: {e}")
                self.slack.notify_error("포트폴리오 삭제 실패", str(e))
            
            # 새 포트폴리오 항목 추가
            success_count = 0
            fail_count = 0
            
            for position in portfolio_data:
                try:
                    # 티커 정보
                    ticker = position['ticker']
                    
                    # 수익률 계산
                    profit_rate = 0
                    if position.get('avg_price', 0) > 0 and position.get('current_price', 0) > 0:
                        profit_rate = ((position['current_price'] / position['avg_price']) - 1) * 100
                    
                    # 현재 시간
                    current_time = datetime.now().isoformat()
                    
                    # 수동으로 포트폴리오 DB의 정확한 속성명 매핑
                    properties = {
                        "Position ID": {
                            "title": [{
                                "text": {
                                    "content": ticker
                                }
                            }]
                        },
                        "Ticker": {
                            "select": {
                                "name": ticker
                            }
                        },
                        "Amount": {
                            "number": position.get('amount', 0)
                        },
                        "Average_Price": {
                            "number": position.get('avg_price', 0)
                        },
                        "Current_Price": {
                            "number": position.get('current_price', 0)
                        },
                        "Total_Value": {
                            "number": position.get('total_value', 0)
                        },
                        "Profit_Rate": {
                            "number": profit_rate
                        },
                        "Last_Update": {
                            "date": {
                                "start": current_time
                            }
                        }
                    }
                    
                    # 항목 생성
                    result = self.notion.pages.create(
                        parent={"database_id": self.portfolio_db_id},
                        properties=properties
                    )
                    
                    if result and 'id' in result:
                        print(f"{ticker} 포트폴리오 항목 추가 성공")
                        success_count += 1
                    else:
                        print(f"{ticker} 포트폴리오 항목 추가 실패")
                        fail_count += 1
                    
                    time.sleep(0.3)
                    
                except Exception as e:
                    print(f"{position.get('ticker', 'unknown')} 항목 추가 실패: {e}")
                    fail_count += 1
                    continue
            
            # 업데이트 결과 알림
            non_krw = [p for p in portfolio_data if p.get('ticker') != 'KRW']
            total_value = sum(p.get('total_value', 0) for p in portfolio_data)
            
            result_msg = f"""
💰 포트폴리오 업데이트 완료
총 자산: {total_value:,.0f} KRW
코인 수: {len(non_krw)}개
항목: {', '.join([p['ticker'] for p in non_krw[:5]])}{' 외 더 있음' if len(non_krw) > 5 else ''}
업데이트 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            self.slack.send_notification(result_msg)
            print(f"포트폴리오 업데이트 완료: 성공 {success_count}, 실패 {fail_count}")
            return success_count > 0
            
        except Exception as e:
            error_msg = f"포트폴리오 업데이트 중 오류: {e}"
            print(error_msg)
            self.slack.notify_error("포트폴리오 업데이트 실패", error_msg)
            return False
