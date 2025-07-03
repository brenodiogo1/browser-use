import asyncio
import json
import time

import aiofiles
import tiktoken

from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.browser.types import ViewportSize
from browser_use.dom.a11y.service import A11yService
from browser_use.dom.a11y.views import (
	CombinedElementNode,
	CombinedTextNode,
	CombinedTreeResponse,
	NodeType,
)


async def test_combined_accessibility_tree():
	"""Test the combined DOM + accessibility tree with new Pydantic types."""
	browser_session = BrowserSession(
		browser_profile=BrowserProfile(
			window_size=ViewportSize(width=1100, height=1000),
			disable_security=True,
			wait_for_network_idle_page_load_time=1,
			headless=False,
		),
	)

	# websites = [
	# 	'https://google.com',
	# 	'https://amazon.com',
	# 	'https://github.com',
	# ]

	await browser_session.start()
	page = await browser_session.get_current_page()
	a11y_service = A11yService(browser_session)
	await page.goto('https://google.com')

	while True:
		await browser_session.remove_highlights()
		await asyncio.sleep(1)

		# wait until traffic is idle
		await browser_session._wait_for_stable_network()

		# print(f'\n{"=" * 50}\nTesting {website}\n{"=" * 50}')

		# Get both trees
		print('Getting accessibility and DOM trees...')
		start_time = time.time()
		accessibility_tree = await a11y_service.get_accessibility_tree()
		dom_tree = await a11y_service.get_entire_dom_tree()
		end_time = time.time()
		print(f'Tree retrieval took {end_time - start_time:.2f} seconds')

		# Create combined tree using new types
		print('Creating combined tree with Pydantic types...')
		start_time = time.time()
		combined_tree = create_combined_tree(accessibility_tree, dom_tree)
		end_time = time.time()
		print(f'Combined tree creation took {end_time - start_time:.2f} seconds')

		print('Combined tree stats:')
		print(f'  - Total nodes: {combined_tree.total_nodes}')
		print(f'  - Accessible nodes: {combined_tree.accessible_nodes}')
		print(f'  - Interactive nodes: {combined_tree.interactive_nodes}')

		# Generate accessible elements string output
		if isinstance(combined_tree.root, CombinedElementNode):
			print('\nGenerating accessible elements output...')
			accessible_output = combined_tree.root.accessible_elements_to_string()

			# Count tokens
			encoding = tiktoken.encoding_for_model('gpt-4o')
			token_count = len(encoding.encode(accessible_output))
			print(f'Accessible elements token count: {token_count}')

			# Save accessible elements output
			async with aiofiles.open('tmp/accessible_elements.txt', 'w') as f:
				await f.write(accessible_output)
			print('Saved accessible elements to tmp/accessible_elements.txt')

		# Save combined tree as JSON
		async with aiofiles.open('tmp/combined_tree.json', 'w') as f:
			await f.write(json.dumps(combined_tree.model_dump(), indent=2))
		print('Saved combined tree to tmp/combined_tree.json')

		print('\nFirst 10 lines of accessible elements output:')
		lines = accessible_output.split('\n')[:10]
		# for line in lines:
		# 	print(line)

		all_elements_state = await browser_session.get_state_summary(True)

		async with aiofiles.open('tmp/all_elements_state.txt', 'w') as f:
			await f.write(all_elements_state.element_tree.clickable_elements_to_string())
		print('Saved all elements state to tmp/all_elements_state.txt')

		input('Press Enter to continue to next website...')


def create_combined_tree(accessibility_tree, dom_tree) -> CombinedTreeResponse:
	"""Create a combined tree using the new Pydantic types."""

	# Create lookup map for accessibility data by backend node id
	ax_by_backend_id = {}
	for ax_node in accessibility_tree.nodes:
		if not ax_node.ignored and ax_node.backendDOMNodeId:
			ax_by_backend_id[ax_node.backendDOMNodeId] = ax_node

	# Statistics tracking
	stats = {
		'total_nodes': 0,
		'accessible_nodes': 0,
		'interactive_nodes': 0,
	}

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
				attributes = {}
				if hasattr(dom_node, 'attributes') and dom_node.attributes:
					attrs = dom_node.attributes
					for i in range(0, len(attrs), 2):
						if i + 1 < len(attrs):
							attributes[attrs[i]] = attrs[i + 1]

				container_node = CombinedElementNode(
					node_id=dom_node.nodeId,
					backend_node_id=dom_node.backendNodeId,
					node_type=dom_node.nodeType,
					node_name=dom_node.nodeName,
					node_value=dom_node.nodeValue,
					tag_name=dom_node.localName or dom_node.nodeName.lower(),
					attributes=attributes,
					accessibility=None,  # No accessibility data for container
					children=accessible_children,
					parent=None,
					is_new=True,
				)

				# Set parent references
				for child in accessible_children:
					child.parent = container_node

				return container_node

		stats['accessible_nodes'] += 1

		# Check if it's interactive
		role = accessibility_data.role.value if accessibility_data.role else None
		interactive_roles = {'button', 'link', 'textbox', 'combobox', 'menuitem', 'tab', 'checkbox', 'radio'}
		# one of these roles
		is_interactive = role in interactive_roles if role else False
		if is_interactive:
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
				is_new=True,
			)
		else:
			# Parse attributes from flat array to dict
			attributes = {}
			if hasattr(dom_node, 'attributes') and dom_node.attributes:
				attrs = dom_node.attributes
				for i in range(0, len(attrs), 2):
					if i + 1 < len(attrs):
						attributes[attrs[i]] = attrs[i + 1]

			node = CombinedElementNode(
				node_id=dom_node.nodeId,
				backend_node_id=dom_node.backendNodeId,
				node_type=dom_node.nodeType,
				node_name=dom_node.nodeName,
				node_value=dom_node.nodeValue,
				tag_name=dom_node.localName or dom_node.nodeName.lower(),
				attributes=attributes,
				accessibility=accessibility_data,
				is_interactive=is_interactive,
				is_top_element=True,  # Could be refined based on specific criteria
				is_in_viewport=True,  # Could be refined with actual viewport checks
				parent=None,
				is_new=True,
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
			parent=None,
			is_new=True,
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


if __name__ == '__main__':
	asyncio.run(test_combined_accessibility_tree())
