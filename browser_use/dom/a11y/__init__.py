"""
Accessibility tree processing module for browser-use.

This module provides functionality to process and combine DOM trees with accessibility data
using Chrome DevTools Protocol (CDP) accessibility calls.
"""

from .combined_tree_processor import CombinedTreeProcessor
from .dom_tree_serializer import DOMTreeSerializer
from .service import A11yService
from .views import (
	AXNode,
	CombinedElementNode,
	CombinedTextNode,
	CombinedTreeResponse,
	NodeType,
)

__all__ = [
	'A11yService',
	'CombinedTreeProcessor',
	'DOMTreeSerializer',
	'AXNode',
	'CombinedElementNode',
	'CombinedTextNode',
	'CombinedTreeResponse',
	'DOMNode',
	'NodeType',
]
