import logging

from typing_extensions import TypedDict

from browser_use.dom.a11y.views import (
	AccessibilityTreeResponse,
	CombinedElementNode,
	CombinedTextNode,
	CombinedTreeResponse,
	DOMTreeResponse,
	NodeType,
)

logger = logging.getLogger(__name__)


class InteractiveCounterType(TypedDict):
	value: int


class StatsTreeProcessor(TypedDict):
	total_nodes: int
	accessible_nodes: int
	interactive_nodes: int


class CombinedTreeProcessor:
	"""Processor for creating combined DOM + accessibility trees."""

	def __init__(self):
		pass

	def _should_ignore_accessibility_for_node(self, dom_node) -> bool:
		"""Check if we should ignore accessibility data for structural/document nodes."""
		if not dom_node:
			return False

		# Get the node name and tag name
		node_name = dom_node.nodeName.lower() if dom_node.nodeName else ''
		tag_name = dom_node.localName.lower() if dom_node.localName else ''

		# Document-level nodes to ignore
		document_level_nodes = {
			'#document',
			'#document-fragment',
			'html',
			'head',
			'body',
			'title',
			'meta',
			'link',
			'style',
			'script',
			'noscript',
		}

		# Check node name or tag name
		return node_name in document_level_nodes or tag_name in document_level_nodes

	def create_combined_tree(
		self, accessibility_tree: AccessibilityTreeResponse, dom_tree: DOMTreeResponse
	) -> CombinedTreeResponse:
		"""Create a combined tree using the new Pydantic types."""

		# Create lookup map for accessibility data by backend node id
		ax_by_backend_id = {}
		for ax_node in accessibility_tree.nodes:
			if not ax_node.ignored and ax_node.backendDOMNodeId:
				ax_by_backend_id[ax_node.backendDOMNodeId] = ax_node

		# Statistics tracking
		stats: StatsTreeProcessor = {
			'total_nodes': 0,
			'accessible_nodes': 0,
			'interactive_nodes': 0,
		}

		# Interactive index counter for depth-first numbering
		interactive_counter: InteractiveCounterType = {'value': 0}

		def collect_accessible_children(dom_node):
			"""Collect all accessible children and descendants from a DOM node."""
			accessible_children = []

			# Process direct children
			if hasattr(dom_node, 'children') and dom_node.children:
				for child in dom_node.children:
					result = convert_dom_node(child)
					if result:
						accessible_children.append(result)

			# Process shadow roots
			if hasattr(dom_node, 'shadowRoots') and dom_node.shadowRoots:
				for shadow_root in dom_node.shadowRoots:
					result = convert_dom_node(shadow_root)
					if result:
						accessible_children.append(result)

			return accessible_children

		def convert_dom_node(dom_node):
			"""Convert DOM node to combined node, returning single node or None."""
			if not dom_node:
				return None

			stats['total_nodes'] += 1
			backend_id = dom_node.backendNodeId
			accessibility_data = ax_by_backend_id.get(backend_id)

			# Check if we should ignore accessibility data for this node
			should_ignore_accessibility = self._should_ignore_accessibility_for_node(dom_node)
			if should_ignore_accessibility:
				accessibility_data = None

			# If this node has no accessibility data, collect accessible children and return the best one
			if not accessibility_data:
				accessible_children = collect_accessible_children(dom_node)

				if not accessible_children:
					return None
				elif len(accessible_children) == 1:
					return accessible_children[0]
				else:
					# Create a container node for multiple accessible children
					# Use the original DOM node properties but mark it as a container
					attributes = self._parse_dom_attributes(dom_node)

					container_node = CombinedElementNode(
						node_id=dom_node.nodeId,
						backend_node_id=dom_node.backendNodeId,
						node_type=dom_node.nodeType,
						node_name=dom_node.nodeName,
						node_value=dom_node.nodeValue,
						tag_name=dom_node.localName or dom_node.nodeName.lower(),
						attributes=attributes,
						accessibility=None,  # No accessibility data for container
						interactive_index=None,  # Container nodes are not interactive
						children=accessible_children,
						parent=None,
						is_new=False,
						xpath=None,
					)

					# Set parent references
					for child in accessible_children:
						child.parent = container_node

					return container_node

			stats['accessible_nodes'] += 1

			# Check if it's interactive and assign index
			is_interactive = self._is_interactive_node(accessibility_data)
			interactive_index = None
			if is_interactive:
				interactive_index = interactive_counter['value']
				interactive_counter['value'] += 1
				stats['interactive_nodes'] += 1

			# Create the appropriate combined node type
			if dom_node.nodeType == NodeType.TEXT_NODE:
				node = CombinedTextNode(
					node_id=dom_node.nodeId,
					backend_node_id=dom_node.backendNodeId,
					node_type=dom_node.nodeType,
					node_name=dom_node.nodeName,
					node_value=dom_node.nodeValue,
					text=dom_node.nodeValue,
					accessibility=accessibility_data,
					parent=None,
					is_new=False,
				)
			else:
				# Parse attributes from flat array to dict
				attributes = self._parse_dom_attributes(dom_node)

				node = CombinedElementNode(
					node_id=dom_node.nodeId,
					backend_node_id=dom_node.backendNodeId,
					node_type=dom_node.nodeType,
					node_name=dom_node.nodeName,
					node_value=dom_node.nodeValue,
					tag_name=dom_node.localName or dom_node.nodeName.lower(),
					attributes=attributes,
					accessibility=accessibility_data,
					interactive_index=interactive_index,
					is_in_viewport=True,  # Could be refined with actual viewport checks
					parent=None,
					is_new=False,
					xpath=None,
				)

				# Handle shadow root flag
				if hasattr(dom_node, 'shadowRoots') and dom_node.shadowRoots:
					node.shadow_root = True

			# Get accessible children for this node
			accessible_children = collect_accessible_children(dom_node)
			node.children = accessible_children

			# Set parent references
			for child in accessible_children:
				child.parent = node

			return node

		# Convert the root node
		root_node = convert_dom_node(dom_tree.root)

		# If no root node, create a placeholder
		if not root_node:
			root_node = CombinedElementNode(
				node_id=dom_tree.root.nodeId,
				backend_node_id=dom_tree.root.backendNodeId,
				node_type=dom_tree.root.nodeType,
				node_name=dom_tree.root.nodeName,
				node_value=dom_tree.root.nodeValue,
				tag_name=dom_tree.root.localName or dom_tree.root.nodeName.lower(),
				accessibility=None,
				interactive_index=None,
				parent=None,
				is_new=False,
				xpath=None,
			)

		return CombinedTreeResponse(
			root=root_node,
			total_nodes=stats['total_nodes'],
			accessible_nodes=stats['accessible_nodes'],
			interactive_nodes=stats['interactive_nodes'],
			metadata={
				'original_dom_nodes': dom_tree.total_nodes,
				'original_accessibility_nodes': len([n for n in accessibility_tree.nodes if not n.ignored]),
				'frame_count': dom_tree.frame_count,
			},
		)

	def _parse_dom_attributes(self, dom_node) -> dict[str, str]:
		"""Parse DOM node attributes from flat array to dictionary."""
		attributes = {}
		if hasattr(dom_node, 'attributes') and dom_node.attributes:
			attrs = dom_node.attributes
			for i in range(0, len(attrs), 2):
				if i + 1 < len(attrs):
					attributes[attrs[i]] = attrs[i + 1]
		return attributes

	def _is_interactive_node(self, accessibility_data) -> bool:
		"""Check if a node is interactive based on its accessibility role or focusable property."""
		if not accessibility_data:
			return False

		# Check if it has focusable property set to true
		if accessibility_data.has_property('focusable', True):
			return True

		# Check if it has an interactive role
		if accessibility_data.role:
			role = accessibility_data.role.value if accessibility_data.role else None
			interactive_roles = {'button', 'link', 'textbox', 'combobox', 'menuitem', 'tab', 'checkbox', 'radio'}
			return role in interactive_roles if role else False

		return False
