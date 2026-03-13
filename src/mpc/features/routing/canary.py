import random
from dataclasses import dataclass
from typing import Any, Dict

@dataclass
class CanaryRouter:
    """Route traffic between stable and canary manifest versions with Segmentation."""
    
    stable_hash: str
    canary_hash: str
    weight: float = 0.1 # 0.0 to 1.0 (10% canary default)
    # segments: {attribute_name: [list_of_values]}
    # If actor has attribute matching any value, they go to canary.
    segments: Dict[str, List[Any]] = field(default_factory=dict)
    
    def resolve_version(self, actor_id: str | None = None, attributes: Dict[str, Any] | None = None) -> str:
        """Determine which manifest version to use.
        
        Priority:
        1. Segment Match (Explicit targeting)
        2. Hash-based stickiness (if actor_id provided)
        3. Random weight
        """
        # 1. Segment Match
        if attributes and self.segments:
            for attr, target_values in self.segments.items():
                if attr in attributes and attributes[attr] in target_values:
                    return self.canary_hash

        # 2. Hash-based stickiness
        if actor_id:
            bucket = hash(actor_id) % 100
            if bucket < (self.weight * 100):
                return self.canary_hash
            return self.stable_hash
            
        # 3. Random distribution
        if random.random() < self.weight:
            return self.canary_hash
        return self.stable_hash

    def update_weight(self, new_weight: float) -> None:
        self.weight = max(0.0, min(1.0, new_weight))
