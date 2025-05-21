import time
from typing import Dict, List, Optional
import logging

class ImprovedOrderManager:
    def __init__(self, upbit_client):
        self.upbit = upbit_client
        self.logger = logging.getLogger(__name__)
        self.pending_orders = {}
        self.completed_orders = {}
        self.order_timeout = 60  # Increased default timeout to 60 seconds
        
    def monitor_order(self, order_id: str, timeout: int = None, check_interval: float = 0.5) -> Dict:
        """
        Monitor order status until completion or timeout with enhanced retry logic
        
        Args:
            order_id: The UUID of the order to monitor
            timeout: Time in seconds to wait for completion (defaults to self.order_timeout)
            check_interval: How often to check for updates in seconds
            
        Returns:
            Dict containing order status and details
        """
        timeout = timeout or self.order_timeout
        start_time = time.time()
        
        self.logger.info(f"Monitoring order {order_id} (timeout: {timeout}s)")
        
        # Track failures to implement exponential backoff
        consecutive_failures = 0
        max_failures = 5
        last_order_state = None
        retry_delay = check_interval
        
        while time.time() - start_time < timeout:
            try:
                order = self.upbit.get_order(order_id)
                consecutive_failures = 0  # Reset failure counter on success
                
                # Cache order state for better reporting
                if order and 'state' in order:
                    if order['state'] != last_order_state:
                        last_order_state = order['state']
                        self.logger.info(f"Order {order_id} state: {last_order_state}")
                
                if order['state'] == 'done':
                    self.logger.info(f"Order {order_id} completed successfully")
                    self.completed_orders[order_id] = order
                    if order_id in self.pending_orders:
                        del self.pending_orders[order_id]
                    return order
                    
                elif order['state'] == 'cancel':
                    self.logger.warning(f"Order {order_id} was cancelled")
                    return order
                
                # For wait state, check volume/remaining to report progress
                elif order['state'] == 'wait':
                    if 'volume' in order and 'remaining_volume' in order:
                        volume = float(order['volume'])
                        remaining = float(order['remaining_volume'])
                        if volume > 0 and remaining < volume:
                            completed_pct = ((volume - remaining) / volume) * 100
                            self.logger.info(f"Order {order_id} partially filled: {completed_pct:.1f}% complete")
                
                # Reset retry delay since we got a valid response
                retry_delay = check_interval
                
                # Wait before next check
                time.sleep(retry_delay)
                
            except Exception as e:
                consecutive_failures += 1
                
                # Exponential backoff for retries
                retry_delay = min(check_interval * (2 ** consecutive_failures), 5)
                
                self.logger.warning(f"Error monitoring order {order_id} (attempt {consecutive_failures}): {e}")
                
                if consecutive_failures >= max_failures:
                    self.logger.error(f"Too many failures ({consecutive_failures}) monitoring order {order_id}")
                    return {'state': 'error', 'uuid': order_id, 'error': str(e)}
                
                time.sleep(retry_delay)
        
        # If we're still here, we've timed out
        elapsed = time.time() - start_time
        self.logger.warning(f"Order {order_id} monitoring timed out after {elapsed:.1f}s")
        
        # Try one last time to get final state
        try:
            final_check = self.upbit.get_order(order_id)
            if final_check and final_check['state'] == 'done':
                self.logger.info(f"Final check: Order {order_id} actually completed")
                return final_check
            elif final_check:
                self.logger.warning(f"Final state for order {order_id}: {final_check['state']}")
                return final_check
        except Exception as e:
            self.logger.error(f"Final check failed for order {order_id}: {e}")
        
        return {'state': 'timeout', 'uuid': order_id, 'elapsed_seconds': elapsed}
    
    def wait_for_orders_completion(self, orders: List[Dict], timeout: int = 60) -> Dict[str, Dict]:
        """Wait for multiple orders to complete with improved reporting"""
        order_count = len(orders)
        self.logger.info(f"Waiting for {order_count} orders to complete (timeout: {timeout}s)")
        
        results = {}
        start_time = time.time()
        
        for i, order in enumerate(orders, 1):
            if 'uuid' in order:
                order_id = order['uuid']
                # Calculate remaining timeout for this order
                elapsed = time.time() - start_time
                remaining_timeout = max(1, timeout - elapsed)  # Ensure at least 1 second
                
                self.logger.info(f"Monitoring order {i}/{order_count}: {order_id} ({remaining_timeout:.1f}s remaining)")
                result = self.monitor_order(order_id, timeout=remaining_timeout)
                results[order_id] = result
        
        # Summary statistics
        completed = len([r for r in results.values() if r.get('state') == 'done'])
        cancelled = len([r for r in results.values() if r.get('state') == 'cancel'])
        timeout_count = len([r for r in results.values() if r.get('state') == 'timeout'])
        elapsed = time.time() - start_time
        
        self.logger.info(
            f"Order batch completion ({elapsed:.1f}s): "
            f"{completed}/{order_count} completed, {cancelled} cancelled, {timeout_count} timed out"
        )
        
        return results
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order with retry"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = self.upbit.cancel_order(order_id)
                self.logger.info(f"Cancelled order {order_id}")
                return True
            except Exception as e:
                self.logger.warning(f"Error cancelling order {order_id} (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
        
        self.logger.error(f"Failed to cancel order {order_id} after {max_retries} attempts")
        return False
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get current order status with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                order = self.upbit.get_order(order_id)
                return order
            except Exception as e:
                self.logger.warning(f"Error getting order status {order_id} (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
        
        self.logger.error(f"Failed to get status for order {order_id}")
        return {'state': 'unknown', 'uuid': order_id}