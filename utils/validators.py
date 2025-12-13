from typing import Optional, List, Tuple
import re
from datetime import datetime

class Validators:
    ROBLOX_USERNAME_PATTERN = re.compile(r'^[a-zA-Z0-9_]{3,20}$')
    
    SCAM_PHRASES = [
        'free robux', 'free items', 'trust trade', 'drop first',
        'i go first next time', 'prove you trust me', 'my friend will hold',
        'middleman my friend', 'send me first', 'quick trade no time',
        'hurry up', 'now or never', 'limited time', 'act fast',
        'too good to be true', 'doubling', 'tripling', 'guaranteed profit'
    ]
    
    PRESSURE_PHRASES = [
        'hurry', 'quick', 'fast', 'now', 'immediately', 'asap',
        'last chance', 'going soon', 'someone else wants', 'other offers'
    ]
    
    @classmethod
    def validate_roblox_username(cls, username: str) -> Tuple[bool, Optional[str]]:
        if not username:
            return False, "Username cannot be empty"
        
        if len(username) < 3:
            return False, "Username must be at least 3 characters"
        
        if len(username) > 20:
            return False, "Username cannot exceed 20 characters"
        
        if not cls.ROBLOX_USERNAME_PATTERN.match(username):
            return False, "Username can only contain letters, numbers, and underscores"
        
        if username.startswith('_') or username.endswith('_'):
            return False, "Username cannot start or end with underscore"
        
        return True, None
    
    @classmethod
    def validate_trade_items(cls, items: List[str], max_items: int = 10) -> Tuple[bool, Optional[str]]:
        if not items:
            return False, "Trade must include at least one item"
        
        if len(items) > max_items:
            return False, f"Trade cannot exceed {max_items} items"
        
        if len(items) != len(set(items)):
            return False, "Duplicate items detected"
        
        return True, None
    
    @classmethod
    def check_scam_phrases(cls, text: str) -> List[str]:
        text_lower = text.lower()
        detected = []
        
        for phrase in cls.SCAM_PHRASES:
            if phrase in text_lower:
                detected.append(phrase)
        
        return detected
    
    @classmethod
    def check_pressure_tactics(cls, text: str) -> List[str]:
        text_lower = text.lower()
        detected = []
        
        for phrase in cls.PRESSURE_PHRASES:
            if phrase in text_lower:
                detected.append(phrase)
        
        return detected
    
    @classmethod
    def validate_value_ratio(cls, offering_value: float, receiving_value: float, 
                            max_ratio: float = 5.0) -> Tuple[bool, float, str]:
        if offering_value <= 0 or receiving_value <= 0:
            return True, 1.0, "Unable to calculate value ratio"
        
        ratio = max(offering_value, receiving_value) / min(offering_value, receiving_value)
        
        if ratio > max_ratio:
            if offering_value > receiving_value:
                return False, ratio, f"You're overpaying by {ratio:.1f}x"
            else:
                return False, ratio, f"This appears to be a lowball offer ({ratio:.1f}x difference)"
        
        return True, ratio, "Fair trade"
    
    @classmethod
    def validate_account_age(cls, created_at: datetime, min_days: int = 30) -> Tuple[bool, int]:
        if not created_at:
            return False, 0
        
        age_days = (datetime.now() - created_at).days
        return age_days >= min_days, age_days
    
    @classmethod
    def sanitize_input(cls, text: str, max_length: int = 500) -> str:
        text = text.strip()
        text = re.sub(r'[<>]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text[:max_length]
