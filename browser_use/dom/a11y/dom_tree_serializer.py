# @file purpose: Serializes combined DOM + accessibility trees to string format for LLM consumption

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from browser_use.dom.a11y.views import CombinedBaseNode, CombinedElementNode


class DOMTreeSerializer:
	"""Serializes combined DOM + accessibility trees to string format."""

	def __init__(self):
		pass

	def serialize_accessible_elements(self, root_node: 'CombinedBaseNode', include_attributes: list[str] | None = None) -> str:
		"""Convert the combined tree to string format, showing accessible elements and text content."""
		formatted_text = []

		if not include_attributes:
			from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES

			include_attributes = DEFAULT_INCLUDE_ATTRIBUTES

		def process_node(node: 'CombinedBaseNode', depth: int) -> None:
			from browser_use.dom.a11y.views import CombinedElementNode, CombinedTextNode

			depth_str = depth * '\t'

			if isinstance(node, CombinedElementNode):
				# Skip #document nodes entirely
				if node.tag_name == '#document':
					# Just process children without showing the document node
					for child in node.children:
						process_node(child, depth)
					return

				# Show accessible elements (both interactive and non-interactive)
				if node.has_accessibility_data() and node.accessibility and not node.accessibility.ignored:
					# Get text content from this element
					text = node.get_all_text_till_next_accessible_element()

					# Build attributes string
					attributes_html_str = self._build_attributes_string(node, include_attributes, text)

					# Build the line - only show brackets for interactive elements
					if node.interactive_index is not None:
						# Interactive element with numbered index
						if node.is_new:
							line = f'{depth_str}*[{node.interactive_index}]<{node.tag_name}'
						else:
							line = f'{depth_str}[{node.interactive_index}]<{node.tag_name}'
					else:
						# Non-interactive accessible element - no brackets
						line = f'{depth_str}<{node.tag_name}'

					if attributes_html_str:
						line += f' {attributes_html_str}'

					# Add accessibility name if different from text
					name = node.get_accessibility_name()
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

					# Process children with increased depth
					for child in node.children:
						process_node(child, depth + 1)
				else:
					# Non-accessible element - just process children without increasing depth
					for child in node.children:
						process_node(child, depth)

			elif isinstance(node, CombinedTextNode):
				# Show text nodes that are leaf nodes with meaningful content
				if node.text and node.text.strip() and len(node.text.strip()) > 0 and not node.has_parent_with_accessibility():
					# Only show text if it's not already captured by a parent accessible element
					text_content = node.text.strip()
					if len(text_content) > 100:
						text_content = text_content[:100] + '...'
					# Show as plain text without quotes or formatting
					formatted_text.append(f'{depth_str}{text_content}')

		process_node(root_node, 0)
		return '\n'.join(formatted_text)

	def _build_attributes_string(self, node: 'CombinedElementNode', include_attributes: list[str], text: str) -> str:
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
