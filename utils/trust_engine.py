from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import json

class RiskLevel(Enum):
    SAFE = 'safe'
    CAUTION = 'caution'
    HIGH_RISK = 'high_risk'

class TrustTier(Enum):
    BRONZE = 'Bronze'
    SILVER = 'Silver'
    GOLD = 'Gold'
    PLATINUM = 'Platinum'
    DIAMOND = 'Diamond'

class TrustEngine:
    TIER_THRESHOLDS = {
        TrustTier.DIAMOND: 90,
        TrustTier.PLATINUM: 75,
        TrustTier.GOLD: 60,
        TrustTier.SILVER: 40,
        TrustTier.BRONZE: 0
    }
    
    RISK_THRESHOLDS = {
        RiskLevel.SAFE: 70,
        RiskLevel.CAUTION: 40,
        RiskLevel.HIGH_RISK: 0
    }
    
    def __init__(self):
        self.weights = {
            'discord_age': 0.15,
            'roblox_age': 0.15,
            'completion_ratio': 0.25,
            'dispute_ratio': 0.20,
            'value_history': 0.10,
            'behavior_score': 0.15
        }
    
    def calculate_trust_score(self, user_data: Dict) -> float:
        scores = {}
        
        discord_age_days = user_data.get('discord_age_days', 0)
        scores['discord_age'] = min(100, (discord_age_days / 365) * 100)
        
        roblox_age_days = user_data.get('roblox_age_days', 0)
        scores['roblox_age'] = min(100, (roblox_age_days / 365) * 100)
        
        total_trades = user_data.get('total_trades', 0)
        successful = user_data.get('successful_trades', 0)
        if total_trades > 0:
            scores['completion_ratio'] = (successful / total_trades) * 100
        else:
            scores['completion_ratio'] = 50
        
        disputed = user_data.get('disputed_trades', 0)
        if total_trades > 0:
            dispute_rate = disputed / total_trades
            scores['dispute_ratio'] = max(0, 100 - (dispute_rate * 500))
        else:
            scores['dispute_ratio'] = 50
        
        scores['value_history'] = min(100, 50 + (total_trades * 2))
        
        behavior_score = user_data.get('behavior_score', 50)
        scores['behavior_score'] = behavior_score
        
        weighted_score = sum(
            scores[key] * self.weights[key]
            for key in scores
        )
        
        return round(max(0, min(100, weighted_score)), 1)
    
    def get_trust_tier(self, score: float) -> TrustTier:
        for tier, threshold in self.TIER_THRESHOLDS.items():
            if score >= threshold:
                return tier
        return TrustTier.BRONZE
    
    def assess_trade_risk(self, 
                         requester_data: Dict, 
                         target_data: Dict,
                         trade_data: Dict) -> Tuple[RiskLevel, List[str]]:
        warnings = []
        risk_factors = 0
        
        req_score = self.calculate_trust_score(requester_data)
        tgt_score = self.calculate_trust_score(target_data)
        
        if req_score < 40:
            risk_factors += 2
            warnings.append(f"Requester has low trust score ({req_score})")
        if tgt_score < 40:
            risk_factors += 2
            warnings.append(f"Target has low trust score ({tgt_score})")
        
        req_value = trade_data.get('requester_value', 0)
        tgt_value = trade_data.get('target_value', 0)
        
        if req_value > 0 and tgt_value > 0:
            ratio = max(req_value, tgt_value) / min(req_value, tgt_value)
            if ratio > 3:
                risk_factors += 2
                warnings.append(f"Large value imbalance ({ratio:.1f}x)")
            elif ratio > 2:
                risk_factors += 1
                warnings.append(f"Moderate value imbalance ({ratio:.1f}x)")
        
        if requester_data.get('total_trades', 0) < 5:
            risk_factors += 1
            warnings.append("Requester is a new trader")
        if target_data.get('total_trades', 0) < 5:
            risk_factors += 1
            warnings.append("Target is a new trader")
        
        if requester_data.get('disputed_trades', 0) > 2:
            risk_factors += 2
            warnings.append("Requester has dispute history")
        if target_data.get('disputed_trades', 0) > 2:
            risk_factors += 2
            warnings.append("Target has dispute history")
        
        total_value = req_value + tgt_value
        if total_value > 1000000:
            risk_factors += 2
            warnings.append("High-value trade")
        elif total_value > 100000:
            risk_factors += 1
            warnings.append("Significant value trade")
        
        if risk_factors >= 5:
            return RiskLevel.HIGH_RISK, warnings
        elif risk_factors >= 2:
            return RiskLevel.CAUTION, warnings
        else:
            return RiskLevel.SAFE, warnings
    
    def update_reputation(self, current_data: Dict, event: str, details: Dict = None) -> Dict:
        updates = {}
        
        if event == 'trade_completed':
            updates['successful_trades'] = current_data.get('successful_trades', 0) + 1
            updates['total_trades'] = current_data.get('total_trades', 0) + 1
            
            reliability = current_data.get('reliability', 50)
            updates['reliability'] = min(100, reliability + 2)
            
            value_traded = details.get('value', 0) if details else 0
            updates['total_value_traded'] = current_data.get('total_value_traded', 0) + value_traded
            
        elif event == 'trade_disputed':
            updates['disputed_trades'] = current_data.get('disputed_trades', 0) + 1
            updates['total_trades'] = current_data.get('total_trades', 0) + 1
            
            reliability = current_data.get('reliability', 50)
            updates['reliability'] = max(0, reliability - 10)
            
            fairness = current_data.get('fairness', 50)
            updates['fairness'] = max(0, fairness - 5)
            
        elif event == 'trade_cancelled':
            updates['cancelled_trades'] = current_data.get('cancelled_trades', 0) + 1
            
            responsiveness = current_data.get('responsiveness', 50)
            updates['responsiveness'] = max(0, responsiveness - 2)
            
        elif event == 'proof_submitted':
            proof_compliance = current_data.get('proof_compliance', 50)
            updates['proof_compliance'] = min(100, proof_compliance + 5)
            
        elif event == 'scam_detected':
            updates['reliability'] = max(0, current_data.get('reliability', 50) - 20)
            updates['fairness'] = max(0, current_data.get('fairness', 50) - 15)
        
        if updates:
            new_data = {**current_data, **updates}
            updates['trust_score'] = self.calculate_trust_score(new_data)
            updates['trust_tier'] = self.get_trust_tier(updates['trust_score']).value
        
        return updates
    
    def generate_receipt_hash(self, trade_data: Dict) -> str:
        receipt_data = {
            'trade_id': trade_data.get('id'),
            'requester_id': trade_data.get('requester_id'),
            'target_id': trade_data.get('target_id'),
            'requester_items': trade_data.get('requester_items'),
            'target_items': trade_data.get('target_items'),
            'completed_at': trade_data.get('completed_at'),
            'game': trade_data.get('game')
        }
        
        receipt_json = json.dumps(receipt_data, sort_keys=True, default=str)
        return hashlib.sha256(receipt_json.encode()).hexdigest()
    
    def verify_receipt(self, trade_data: Dict, receipt_hash: str) -> bool:
        expected_hash = self.generate_receipt_hash(trade_data)
        return expected_hash == receipt_hash


trust_engine = TrustEngine()
