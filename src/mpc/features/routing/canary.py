import random
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class CanaryRouter:
    """Route traffic between stable and canary manifest versions."""
    
    stable_hash: str
    canary_hash: str
    weight: float = 0.1 # 0.0 to 1.0 (10% canary default)
    
    def resolve_version(self, actor_id: str | None = None) -> str:
        """Determine which manifest version to use.
        
        If actor_id is provided, we could implement stickiness 
        using hash(actor_id) % 100.
        """
        if actor_id:
            # Deterministic hash-based routing for sticky sessions
            bucket = hash(actor_id) % 100
            if bucket < (self.weight * 100):
                return self.canary_hash
            return self.stable_hash
            
        # Random distribution
        if random.random() < self.weight:
            return self.canary_hash
        return self.stable_hash

    def update_weight(self, new_weight: float) -> None:
        self.weight = max(0.0, min(1.0, new_weight))
