"""
Accessibility tree processing module for browser-use.

This module provides functionality to process and combine DOM trees with accessibility data
using Chrome DevTools Protocol (CDP) accessibility calls.
"""

from .combined_tree_processor import CombinedTreeProcessor
from .service import A11yService
from .views import (
	AccessibilityTreeResponse,
	AXNode,
	CombinedElementNode,
	CombinedTextNode,
	CombinedTreeResponse,
	DOMNode,
	DOMTreeResponse,
	NodeType,
)

__all__ = [
	'A11yService',
	'CombinedTreeProcessor',
	'AccessibilityTreeResponse',
	'AXNode',
	'CombinedElementNode',
	'CombinedTextNode',
	'CombinedTreeResponse',
	'DOMNode',
	'DOMTreeResponse',
	'NodeType',
]
