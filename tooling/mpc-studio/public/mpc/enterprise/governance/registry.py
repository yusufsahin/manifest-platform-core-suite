"""Registry for managing manifest versions across namespaces."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import time

@dataclass
class VersionInfo:
    manifest_id: str
    hash: str
    active_since: float
    metadata: Dict[str, str] = field(default_factory=dict)

@dataclass
class VersionRegistry:
    """Track active and canary versions for different namespaces."""
    
    # versions: {namespace: {"stable": VersionInfo, "canary": VersionInfo}}
    versions: Dict[str, Dict[str, VersionInfo]] = field(default_factory=dict)
    
    def register_stable(self, namespace: str, manifest_id: str, hash: str, metadata: Optional[Dict[str, str]] = None) -> None:
        if namespace not in self.versions:
            self.versions[namespace] = {}
        self.versions[namespace]["stable"] = VersionInfo(
            manifest_id=manifest_id,
            hash=hash,
            active_since=time.time(),
            metadata=metadata or {}
        )
        
    def register_canary(self, namespace: str, manifest_id: str, hash: str, metadata: Optional[Dict[str, str]] = None) -> None:
        if namespace not in self.versions:
            self.versions[namespace] = {}
        self.versions[namespace]["canary"] = VersionInfo(
            manifest_id=manifest_id,
            hash=hash,
            active_since=time.time(),
            metadata=metadata or {}
        )
        
    def get_versions(self, namespace: str) -> Dict[str, VersionInfo]:
        return self.versions.get(namespace, {})

    def promote_canary(self, namespace: str) -> bool:
        """Move canary to stable if it exists."""
        ns = self.versions.get(namespace)
        if ns and "canary" in ns:
            ns["stable"] = ns.pop("canary")
            return True
        return False
