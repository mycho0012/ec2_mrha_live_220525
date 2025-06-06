from typing import Dict, List
import logging

class CapitalAllocator:
    def __init__(self):
        self.min_order_size = 5000  # 5,000 KRW minimum
        self.reserve_ratio = 0.02   # 2% reserve
        self.momentum_capital_ratio = 0.6  # 60% to momentum trades
        self.logger = logging.getLogger(__name__)
        
    def allocate_capital_dynamically(self, available_krw: float, buy_signals: List[Dict]) -> Dict[str, float]:
        """Allocate capital based on signal strength and momentum"""
        try:
            if not buy_signals:
                self.logger.info("No buy signals to allocate capital")
                return {}
            
            # Reserve capital
            tradeable_capital = available_krw * (1 - self.reserve_ratio)
            self.logger.info(f"Tradeable capital: {tradeable_capital:,.0f} KRW")
            
            # Categorize signals
            momentum_signals = [s for s in buy_signals if s.get('is_momentum', False)]
            regular_signals = [s for s in buy_signals if not s.get('is_momentum', False)]
            
            # Determine capital split
            if momentum_signals and regular_signals:
                momentum_capital = tradeable_capital * self.momentum_capital_ratio
                regular_capital = tradeable_capital * (1 - self.momentum_capital_ratio)
            elif momentum_signals:
                momentum_capital = tradeable_capital
                regular_capital = 0
            else:
                momentum_capital = 0
                regular_capital = tradeable_capital
            
            allocations = {}
            
            # Allocate to momentum signals (weighted by score)
            if momentum_signals and momentum_capital > 0:
                total_score = sum(s.get('momentum_score', 1) for s in momentum_signals)
                
                for signal in momentum_signals:
                    ticker = signal.get('ticker', signal.get('coin'))
                    score = signal.get('momentum_score', 1)
                    weight = score / total_score if total_score > 0 else 1 / len(momentum_signals)
                    allocation = momentum_capital * weight
                    
                    if allocation >= self.min_order_size:
                        allocations[ticker] = allocation
            
            # Allocate to regular signals (equal weight)
            if regular_signals and regular_capital > 0:
                equal_allocation = regular_capital / len(regular_signals)
                
                for signal in regular_signals:
                    ticker = signal.get('ticker', signal.get('coin'))
                    
                    if equal_allocation >= self.min_order_size:
                        allocations[ticker] = equal_allocation
            
            return allocations
            
        except Exception as e:
            self.logger.error(f"Error allocating capital: {e}")
            return {}