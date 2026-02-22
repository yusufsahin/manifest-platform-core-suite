"""Overlay engine — merge ops + stable selectors + conflict detection.

Per MASTER_SPEC section 15.
"""
from mpc.overlay.engine import OverlayEngine, OverlayResult, Selector, parse_selector

__all__ = ["OverlayEngine", "OverlayResult", "Selector", "parse_selector"]
