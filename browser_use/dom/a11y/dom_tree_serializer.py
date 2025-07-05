# @file purpose: Serializes combined DOM + accessibility trees to string format for LLM consumption

from typing import TYPE_CHECKING

from pydantic import BaseModel

# Import the actual types for runtime use (needed for Pydantic model)
from browser_use.dom.a11y.views import CombinedBaseNode, CombinedElementNode, CombinedTextNode

if TYPE_CHECKING:
	pass  # Keep this in case we need other TYPE_CHECKING imports later


class SimplifiedNode(BaseModel):
	"""Simplified tree node for optimization."""

	model_config = {'arbitrary_types_allowed': True}

	original_node: CombinedBaseNode
	children: list['SimplifiedNode'] = []
	should_display: bool = True

	def is_clickable(self) -> bool:
		"""Check if this node is clickable/interactive."""
		if isinstance(self.original_node, CombinedElementNode):
			return self.original_node.interactive_index is not None
		return False

	def is_text_node(self) -> bool:
		"""Check if this node represents a text node."""
		return isinstance(self.original_node, CombinedTextNode)

	def count_direct_clickable_children(self) -> int:
		"""Count how many direct children are clickable."""
		return sum(1 for child in self.children if child.is_clickable())

	def has_any_clickable_descendant(self) -> bool:
		"""Check if this node or any descendant is clickable."""
		if self.is_clickable():
			return True
		return any(child.has_any_clickable_descendant() for child in self.children)

	def has_clickable_ancestor(self, root_node: CombinedBaseNode) -> bool:
		"""Check if this text node has any clickable ancestor."""

		if not isinstance(self.original_node, CombinedTextNode):
			return False

		# Walk up the tree to check for clickable ancestors
		current = self.original_node.parent
		while current and current != root_node:
			if isinstance(current, CombinedElementNode) and current.interactive_index is not None:
				return True
			current = current.parent
		return False


class DOMTreeSerializer:
	"""Serializes combined DOM + accessibility trees to string format."""

	def __init__(self):
		pass

	def serialize_accessible_elements(self, root_node: CombinedBaseNode, include_attributes: list[str] | None = None) -> str:
		"""Convert the combined tree to string format, showing accessible elements and text content."""
		if not include_attributes:
			from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES

			include_attributes = DEFAULT_INCLUDE_ATTRIBUTES

		# Step 1: Create simplified tree
		simplified_tree = self._create_simplified_tree(root_node)

		# Step 2: Optimize tree (remove unnecessary parents)
		optimized_tree = self._optimize_tree(simplified_tree)

		# Step 3: Serialize optimized tree
		return self._serialize_tree(optimized_tree, include_attributes)

	def _create_simplified_tree(self, node: CombinedBaseNode) -> SimplifiedNode | None:
		"""Step 1: Create a simplified tree with only accessible elements and their structure."""

		if isinstance(node, CombinedElementNode):
			# Skip #document nodes entirely
			if node.tag_name == '#document':
				# Process children and return the first valid child (assuming single root)
				for child in node.children:
					simplified_child = self._create_simplified_tree(child)
					if simplified_child:
						return simplified_child
				return None

			# Only include nodes that have accessibility data and are not ignored
			if node.has_accessibility_data() and node.accessibility and not node.accessibility.ignored:
				simplified = SimplifiedNode(original_node=node)

				# Process all children
				for child in node.children:
					simplified_child = self._create_simplified_tree(child)
					if simplified_child:
						simplified.children.append(simplified_child)

				return simplified
			else:
				# Non-accessible element - collect children from all descendants
				children = []
				for child in node.children:
					simplified_child = self._create_simplified_tree(child)
					if simplified_child:
						children.append(simplified_child)

				# If we have children, we need to return them somehow
				# Create a container node that will be optimized away if needed
				if children:
					simplified = SimplifiedNode(original_node=node)
					simplified.children = children
					return simplified
				return None

		elif isinstance(node, CombinedTextNode):
			# Include text nodes that have meaningful content and are not children of clickable elements
			if node.text and node.text.strip() and len(node.text.strip()) > 0 and not self._has_clickable_ancestor(node):
				return SimplifiedNode(original_node=node)
			return None

		return None

	def _has_clickable_ancestor(self, text_node: CombinedTextNode) -> bool:
		"""Check if a text node has any clickable ancestor."""

		if not isinstance(text_node, CombinedTextNode):
			return False

		# Walk up the tree to check for clickable ancestors
		current = text_node.parent
		while current:
			if isinstance(current, CombinedElementNode) and current.interactive_index is not None:
				return True
			current = current.parent
		return False

	def _optimize_tree(self, node: SimplifiedNode | None) -> SimplifiedNode | None:
		"""Step 2: Optimize tree depth-first by removing unnecessary parent nodes."""
		if not node:
			return None

		# First, recursively optimize all children (depth-first)
		optimized_children = []
		for child in node.children:
			optimized_child = self._optimize_tree(child)
			if optimized_child:
				optimized_children.append(optimized_child)

		# Update children with optimized versions
		node.children = optimized_children

		# Always keep text nodes (they are leaf nodes)
		if node.is_text_node():
			return node

		# Remove nodes with no clickable descendants and no text content
		if not node.has_any_clickable_descendant() and not any(child.is_text_node() for child in node.children):
			return None

		# If this node is non-clickable and has <= 1 clickable direct child,
		# we should consider removing it (but keep it if it has text children)
		if not node.is_clickable():
			clickable_children_count = node.count_direct_clickable_children()
			text_children_count = sum(1 for child in node.children if child.is_text_node())

			# Only keep non-clickable nodes that are direct parents of multiple clickable elements
			# OR that have text children
			if clickable_children_count <= 1 and text_children_count == 0:
				# Remove this node and promote its children
				if len(node.children) == 1:
					# Replace this node with its single child
					return node.children[0]
				elif len(node.children) == 0:
					# No children, remove this node
					return None
				else:
					# Multiple children but <= 1 clickable - return a special node that will promote children
					# We create a "virtual" node that just passes through its children
					virtual_node = SimplifiedNode(original_node=node.original_node)
					virtual_node.children = node.children
					virtual_node.should_display = False
					return virtual_node

		return node

	def _serialize_tree(self, node: SimplifiedNode | None, include_attributes: list[str], depth: int = 0) -> str:
		"""Step 3: Serialize the optimized tree to string format."""
		if not node:
			return ''

		formatted_text = []
		depth_str = depth * '\t'

		# Handle text nodes differently
		if node.is_text_node():
			if isinstance(node.original_node, CombinedTextNode):
				text_content = node.original_node.text.strip()
				if text_content:
					if len(text_content) > 100:
						text_content = text_content[:100] + '...'
					formatted_text.append(f'{depth_str}{text_content}')
		elif isinstance(node.original_node, CombinedElementNode):
			element = node.original_node

			# Skip displaying nodes marked as should_display=False (virtual nodes)
			if not node.should_display:
				# Just process children without displaying this node
				for child in node.children:
					child_text = self._serialize_tree(child, include_attributes, depth)
					if child_text:
						formatted_text.append(child_text)
				return '\n'.join(formatted_text)

			# Get text content from this element
			text = element.get_all_text_till_next_accessible_element()

			# Build attributes string
			attributes_html_str = self._build_attributes_string(element, include_attributes, text)

			# Build the line - only show brackets for interactive elements
			if element.interactive_index is not None:
				# Interactive element with numbered index
				if element.is_new:
					line = f'{depth_str}*[{element.interactive_index}]<{element.tag_name}'
				else:
					line = f'{depth_str}[{element.interactive_index}]<{element.tag_name}'
			else:
				# Non-interactive accessible element - no brackets
				line = f'{depth_str}<{element.tag_name}'

			if attributes_html_str:
				line += f' {attributes_html_str}'

			# Add accessibility name if different from text
			name = element.get_accessibility_name()
			if name and name.strip() != text.strip():
				name_display = f'"{name[:20]}..."' if len(name) > 20 else f'"{name}"'
				line += f' name={name_display}'

			# Add text content
			if text:
				text = text.strip()
				if len(text) > 100:
					text = text[:100] + '...'
				line += f'>{text}'

			line += ' />'
			formatted_text.append(line)

		# Process children
		for child in node.children:
			child_text = self._serialize_tree(child, include_attributes, depth + 1)
			if child_text:
				formatted_text.append(child_text)

		return '\n'.join(formatted_text)

	def _build_attributes_string(self, node: CombinedElementNode, include_attributes: list[str], text: str) -> str:
		"""Build the attributes string for an element."""
		attributes_to_include = {key: str(value).strip() for key, value in node.attributes.items() if key in include_attributes}

		# Remove duplicate values (same logic as DOMElementNode)
		ordered_keys = [key for key in include_attributes if key in attributes_to_include]

		if len(ordered_keys) > 1:
			keys_to_remove = set()
			seen_values = {}

			for key in ordered_keys:
				value = attributes_to_include[key]
				if len(value) > 5:
					if value in seen_values:
						keys_to_remove.add(key)
					else:
						seen_values[value] = key

			for key in keys_to_remove:
				del attributes_to_include[key]

		# Remove attributes that duplicate accessibility data
		role = node.get_accessibility_role()
		name = node.get_accessibility_name()

		if role and node.tag_name == role:
			attributes_to_include.pop('role', None)

		attrs_to_remove_if_text_matches = ['aria-label', 'placeholder', 'title']
		for attr in attrs_to_remove_if_text_matches:
			attr_value = attributes_to_include.get(attr, '').strip().lower()
			if attr_value and (attr_value == text.strip().lower() or (name and attr_value == name.strip().lower())):
				del attributes_to_include[attr]

		if attributes_to_include:
			# Cap text length for display
			def cap_text_length(text: str, max_length: int) -> str:
				return f'"{text[:max_length]}..."' if len(text) > max_length else f'"{text}"'

			return ' '.join(f'{key}={cap_text_length(value, 15)}' for key, value in attributes_to_include.items())

		return ''
