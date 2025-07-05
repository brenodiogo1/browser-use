import logging
from typing import Any

from browser_use.browser.context import Browser
from browser_use.dom.a11y.combined_tree_processor import CombinedTreeProcessor
from browser_use.dom.a11y.views import AccessibilityTreeResponse, CombinedTreeResponse, DOMTreeResponse

# if TYPE_CHECKING:
# 	pass

logger = logging.getLogger(__name__)


class A11yService:
	def __init__(self, browser: Browser):
		self.browser = browser
		self.combined_tree_processor = CombinedTreeProcessor()

	async def get_accessibility_tree(self) -> AccessibilityTreeResponse:
		page = await self.browser.get_current_page()

		if self.browser.browser_context is None:
			raise ValueError('Browser context is not initialized')

		cdp = await self.browser.browser_context.new_cdp_session(page)

		await cdp.send('Accessibility.enable')
		await cdp.send('DOM.enable')
		response = await cdp.send('Accessibility.getFullAXTree')

		return AccessibilityTreeResponse.model_validate(response)

	async def get_entire_dom_tree(self) -> DOMTreeResponse:
		"""Get the complete DOM tree including iframes and shadow DOM using raw CDP calls."""
		page = await self.browser.get_current_page()

		if self.browser.browser_context is None:
			raise ValueError('Browser context is not initialized')

		cdp = await self.browser.browser_context.new_cdp_session(page)

		try:
			# Enable DOM domain
			await cdp.send('DOM.enable')
			await cdp.send('Runtime.enable')

			# Get the root document
			doc_response = await cdp.send('DOM.getDocument', {'depth': -1, 'pierce': True})
			root_node = doc_response['root']

			# Collect all nodes including shadow DOM and iframes
			all_nodes = {}
			frame_documents = []

			await self._collect_all_nodes(cdp, root_node, all_nodes, frame_documents)

			# Process iframe documents
			for frame_doc in frame_documents:
				await self._collect_all_nodes(cdp, frame_doc, all_nodes, [])

			return DOMTreeResponse(
				root=root_node,
				nodes=all_nodes,
				total_nodes=len(all_nodes),
				frame_count=len(frame_documents),
			)

		except Exception as e:
			logger.error(f'Error getting DOM tree: {e}')
			raise
		finally:
			await cdp.detach()

	async def _collect_all_nodes(
		self, cdp, node: dict[str, Any], all_nodes: dict[int, dict[str, Any]], frame_documents: list[dict[str, Any]]
	) -> None:
		"""Recursively collect all nodes including shadow DOM and iframe content."""
		node_id = node.get('nodeId')
		if node_id:
			all_nodes[node_id] = node

		# Handle shadow DOM
		if node.get('shadowRoots'):
			for shadow_root in node['shadowRoots']:
				try:
					# Request child nodes for shadow root
					await cdp.send('DOM.requestChildNodes', {'nodeId': shadow_root['nodeId'], 'depth': -1, 'pierce': True})
					await self._collect_all_nodes(cdp, shadow_root, all_nodes, frame_documents)
				except Exception as e:
					logger.warning(f'Failed to process shadow root {shadow_root.get("nodeId")}: {e}')

		# Handle iframe documents
		if node.get('frameId') and node.get('contentDocument'):
			frame_documents.append(node['contentDocument'])

		# Handle regular child nodes
		if 'children' in node:
			for child in node['children']:
				await self._collect_all_nodes(cdp, child, all_nodes, frame_documents)

		# For nodes that might have children but don't show them yet
		elif node.get('childNodeCount', 0) > 0:
			try:
				# Request child nodes
				await cdp.send('DOM.requestChildNodes', {'nodeId': node_id, 'depth': -1, 'pierce': True})

				# Get updated node with children
				updated_doc = await cdp.send('DOM.getDocument', {'depth': -1, 'pierce': True})
				if node_id is not None:
					updated_node = self._find_node_by_id(updated_doc['root'], node_id)
					if updated_node and 'children' in updated_node:
						for child in updated_node['children']:
							await self._collect_all_nodes(cdp, child, all_nodes, frame_documents)
			except Exception as e:
				logger.warning(f'Failed to request child nodes for {node_id}: {e}')

	def _find_node_by_id(self, root_node: dict[str, Any], target_id: int) -> dict[str, Any] | None:
		"""Find a node by its nodeId in the DOM tree."""
		if root_node.get('nodeId') == target_id:
			return root_node

		if 'children' in root_node:
			for child in root_node['children']:
				result = self._find_node_by_id(child, target_id)
				if result:
					return result

		if 'shadowRoots' in root_node:
			for shadow_root in root_node['shadowRoots']:
				result = self._find_node_by_id(shadow_root, target_id)
				if result:
					return result

		return None

	async def get_combined_tree(self) -> CombinedTreeResponse:
		"""Get the combined DOM + accessibility tree."""
		accessibility_tree = await self.get_accessibility_tree()
		dom_tree = await self.get_entire_dom_tree()
		return self.combined_tree_processor.create_combined_tree(accessibility_tree, dom_tree)
