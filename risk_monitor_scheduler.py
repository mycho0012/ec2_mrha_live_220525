#!/usr/bin/env python3
"""
Hourly Risk Monitoring Scheduler for MRHA Trading System
Runs ATR-based risk management every hour during market hours
"""

import os
import time
import schedule
import logging
from datetime import datetime, timedelta
import pytz
from atr_risk_manager import ATRRiskManager
from slack_notifier import SlackNotifier
import traceback

class RiskMonitorScheduler:
    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self.logger = logging.getLogger(__name__)
        self.slack = SlackNotifier()
        
        # Set timezone to Seoul
        self.timezone = pytz.timezone('Asia/Seoul')
        
        # Market hours (24/7 for crypto, but we can set business hours)
        self.start_hour = 6  # 6 AM KST
        self.end_hour = 23   # 11 PM KST
        
        # Initialize risk manager
        self.risk_manager = ATRRiskManager(test_mode=test_mode)
        
        self.logger.info(f"Risk Monitor Scheduler initialized - Test Mode: {test_mode}")
        
    def is_market_hours(self) -> bool:
        """Check if it's within market monitoring hours"""
        now = datetime.now(self.timezone)
        current_hour = now.hour
        
        # For crypto, we can monitor 24/7, but let's be reasonable
        return self.start_hour <= current_hour <= self.end_hour
    
    def should_run_monitoring(self) -> bool:
        """Determine if monitoring should run now"""
        if self.test_mode:
            return True  # Always run in test mode
            
        return self.is_market_hours()
    
    def run_risk_monitoring(self):
        """Execute risk monitoring with error handling"""
        try:
            if not self.should_run_monitoring():
                self.logger.info(f"Outside monitoring hours ({self.start_hour}:00-{self.end_hour}:00 KST)")
                return
            
            self.logger.info("Starting scheduled risk monitoring...")
            
            # Run the risk monitoring cycle
            result = self.risk_manager.run_risk_monitoring_cycle()
            
            if result:
                self.logger.info(f"Risk monitoring completed: {result}")
                
                # Send periodic status update (every 4 hours)
                now = datetime.now(self.timezone)
                if now.hour % 4 == 0 and now.minute < 5:  # At the top of every 4th hour
                    self.send_status_update(result)
            else:
                self.logger.error("Risk monitoring failed")
                
        except Exception as e:
            error_msg = f"Scheduled risk monitoring error: {e}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            
            # Send error notification
            self.slack.send_notification(
                f"❌ **Risk Monitor Scheduler Error**\n"
                f"Time: {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S KST')}\n"
                f"Error: {error_msg}\n"
                f"Test Mode: {self.test_mode}"
            )
    
    def send_status_update(self, monitoring_result: dict):
        """Send periodic status updates"""
        try:
            now = datetime.now(self.timezone)
            
            message = f"📊 **Risk Monitor Status Update**\n"
            message += f"🕐 Time: {now.strftime('%Y-%m-%d %H:%M KST')}\n"
            message += f"💼 Positions: {monitoring_result.get('positions_monitored', 0)}\n"
            message += f"⚡ Orders: {monitoring_result.get('orders_executed', 0)}\n"
            message += f"⚠️ Alerts: {monitoring_result.get('risk_alerts', 0)}\n"
            message += f"💰 Portfolio: {monitoring_result.get('portfolio_value', 0):,.0f} KRW\n"
            message += f"🧪 Test Mode: {self.test_mode}\n"
            message += f"📈 System: Running normally"
            
            self.slack.send_notification(message)
            
        except Exception as e:
            self.logger.error(f"Error sending status update: {e}")
    
    def setup_schedule(self):
        """Setup the hourly monitoring schedule"""
        if self.test_mode:
            # In test mode, run every 5 minutes for testing
            schedule.every(5).minutes.do(self.run_risk_monitoring)
            self.logger.info("Test mode: Scheduled to run every 5 minutes")
        else:
            # Production: run every hour
            schedule.every().hour.do(self.run_risk_monitoring)
            self.logger.info("Production mode: Scheduled to run every hour")
        
        # Send startup notification
        self.slack.send_notification(
            f"🚀 **Risk Monitor Started**\n"
            f"Mode: {'Test' if self.test_mode else 'Production'}\n"
            f"Schedule: {'Every 5 minutes' if self.test_mode else 'Hourly'}\n"
            f"Hours: {self.start_hour}:00-{self.end_hour}:00 KST\n"
            f"Started: {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S KST')}"
        )
    
    def run_scheduler(self):
        """Main scheduler loop"""
        self.setup_schedule()
        
        self.logger.info("Risk monitoring scheduler started")
        
        # Run initial monitoring
        self.run_risk_monitoring()
        
        # Start the scheduler loop
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                self.logger.info("Scheduler stopped by user")
                self.slack.send_notification(
                    f"⏹️ **Risk Monitor Stopped**\n"
                    f"Time: {datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S KST')}\n"
                    f"Reason: User interruption"
                )
                break
                
            except Exception as e:
                error_msg = f"Scheduler loop error: {e}"
                self.logger.error(error_msg)
                self.slack.send_notification(f"❌ **Scheduler Error**\n{error_msg}")
                
                # Wait a bit before continuing
                time.sleep(300)  # 5 minutes

def main():
    """Main execution function"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'risk_scheduler_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    
    # Get test mode from environment
    test_mode = os.getenv('TEST_MODE', 'True').lower() == 'true'
    
    logger.info(f"Starting Risk Monitor Scheduler - Test Mode: {test_mode}")
    
    try:
        scheduler = RiskMonitorScheduler(test_mode=test_mode)
        scheduler.run_scheduler()
        
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()