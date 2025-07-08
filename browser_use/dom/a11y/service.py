import logging

from cdp_use import CDPClient
from cdp_use.cdp.accessibility.commands import GetFullAXTreeReturns
from cdp_use.cdp.accessibility.types import AXNode
from cdp_use.cdp.dom.commands import GetDocumentReturns
from cdp_use.cdp.dom.types import Node

from browser_use.browser.context import Browser
from browser_use.browser.types import Page
from browser_use.dom.a11y.combined_tree_processor import CombinedTreeProcessor
from browser_use.dom.a11y.views import CombinedTreeResponse

# if TYPE_CHECKING:
# 	pass

logger = logging.getLogger(__name__)


class A11yService:
	def __init__(self, browser: Browser, cdp: CDPClient):
		self.browser = browser
		self.cdp = cdp
		self.combined_tree_processor = CombinedTreeProcessor()

		self.page_to_session_id_store: dict[str, str] = {}

	async def _playwright_page_to_session_id(self, page: Page) -> str:
		"""Get the target ID for a playwright page.

		TODO: this is a REALLY hacky way -> if multiple same urls are open then this will break
		"""

		page_guid = page._impl_obj._guid

		# if page_guid in self.page_to_session_id_store:
		# 	return self.page_to_session_id_store[page_guid]

		targets = await self.cdp.send.Target.getTargets()
		for target in targets['targetInfos']:
			if target['type'] == 'page' and target['url'] == page.url:
				# cache the session id for this playwright page
				self.page_to_session_id_store[page_guid] = target['targetId']

				session = await self.cdp.send.Target.attachToTarget(params={'targetId': target['targetId'], 'flatten': True})
				return session['sessionId']

		raise ValueError('No target ID found for page')

	async def get_accessibility_tree(self) -> GetFullAXTreeReturns:
		page = await self.browser.get_current_page()

		if self.browser.browser_context is None:
			raise ValueError('Browser context is not initialized')

		session_id = await self._playwright_page_to_session_id(page)

		await self.cdp.send.Accessibility.enable(session_id=session_id)
		await self.cdp.send.DOM.enable(session_id=session_id)

		# Get the root AX node first
		root_response = await self.cdp.send.Accessibility.getRootAXNode(session_id=session_id)

		if not root_response or 'node' not in root_response:
			return {'nodes': []}

		root_node = root_response['node']

		# Get all interesting nodes starting from root
		interesting_nodes = []
		if not root_node.get('ignored', True):
			interesting_nodes.append(root_node)

		# Recursively get interesting child nodes
		if 'childIds' in root_node:
			for child_id in root_node['childIds']:
				child_nodes = await self._get_interesting_nodes(session_id, child_id)
				interesting_nodes.extend(child_nodes)

		return {'nodes': interesting_nodes}

	async def _get_interesting_nodes(self, session_id: str, node_id: str) -> list[AXNode]:
		"""Recursively get interesting accessibility nodes, filtering out ignored ones."""
		result: list[AXNode] = []

		try:
			# Get child nodes for this node
			child_response = await self.cdp.send.Accessibility.getChildAXNodes(session_id=session_id, params={'id': node_id})

			for node in child_response.get('nodes', []):
				# Include node if it's not ignored
				if not node.get('ignored', True):
					result.append(node)

					# Only recurse if the node is not ignored
					if 'childIds' in node:
						for child_id in node['childIds']:
							child_nodes = await self._get_interesting_nodes(session_id, child_id)
							result.extend(child_nodes)

		except Exception as e:
			logger.warning(f'Failed to get child AX nodes for {node_id}: {e}')

		return result

	async def get_entire_dom_tree(self) -> GetDocumentReturns:
		"""Get the complete DOM tree including iframes and shadow DOM using raw CDP calls."""
		page = await self.browser.get_current_page()

		if self.browser.browser_context is None:
			raise ValueError('Browser context is not initialized')

		session_id = await self._playwright_page_to_session_id(page)

		try:
			# Enable DOM domain
			await self.cdp.send.DOM.enable(session_id=session_id)
			await self.cdp.send.Runtime.enable(session_id=session_id)

			# Get the root document
			doc_response = await self.cdp.send.DOM.getDocument(session_id=session_id, params={'depth': -1, 'pierce': True})
			root_node = doc_response['root']

			# Collect all nodes including shadow DOM and iframes
			all_nodes: dict[int, Node] = {}
			frame_documents: list[Node] = []

			await self._collect_all_nodes(root_node, all_nodes, frame_documents, session_id)

			# Process iframe documents
			for frame_doc in frame_documents:
				await self._collect_all_nodes(frame_doc, all_nodes, [], session_id)

			return doc_response

		except Exception as e:
			logger.error(f'Error getting DOM tree: {e}')
			raise

	async def _collect_all_nodes(
		self, node: Node, all_nodes: dict[int, Node], frame_documents: list[Node], session_id: str
	) -> None:
		"""Recursively collect all nodes including shadow DOM and iframe content."""
		node_id = node.get('nodeId')
		if node_id:
			all_nodes[node_id] = node

		# Handle shadow DOM
		if 'shadowRoots' in node and node['shadowRoots'] is not None:
			for shadow_root in node['shadowRoots']:
				try:
					# Request child nodes for shadow root
					await self.cdp.send.DOM.requestChildNodes(
						session_id=session_id, params={'nodeId': shadow_root['nodeId'], 'depth': -1, 'pierce': True}
					)
					await self._collect_all_nodes(shadow_root, all_nodes, frame_documents, session_id)
				except Exception as e:
					logger.warning(f'Failed to process shadow root {shadow_root.get("nodeId")}: {e}')

		# Handle iframe documents
		if (
			'frameId' in node
			and node['frameId'] is not None
			and 'contentDocument' in node
			and node['contentDocument'] is not None
		):
			frame_documents.append(node['contentDocument'])

		# Handle regular child nodes
		if 'children' in node and node['children'] is not None:
			for child in node['children']:
				await self._collect_all_nodes(child, all_nodes, frame_documents, session_id)

		# For nodes that might have children but don't show them yet
		elif 'childNodeCount' in node and node['childNodeCount'] is not None and node['childNodeCount'] > 0:
			try:
				# Request child nodes
				await self.cdp.send.DOM.requestChildNodes(
					session_id=session_id, params={'nodeId': node_id, 'depth': -1, 'pierce': True}
				)

				# Get updated node with children
				updated_doc = await self.cdp.send.DOM.getDocument(session_id=session_id, params={'depth': -1, 'pierce': True})
				if node_id is not None:
					updated_node = self._find_node_by_id(updated_doc['root'], node_id)
					if updated_node and 'children' in updated_node and updated_node['children'] is not None:
						for child in updated_node['children']:
							await self._collect_all_nodes(child, all_nodes, frame_documents, session_id)
			except Exception as e:
				logger.warning(f'Failed to request child nodes for {node_id}: {e}')

	def _find_node_by_id(self, root_node: Node, target_id: int) -> Node | None:
		"""Find a node by its nodeId in the DOM tree."""
		if root_node['nodeId'] == target_id:
			return root_node

		if 'children' in root_node and root_node['children'] is not None:
			for child in root_node['children']:
				result = self._find_node_by_id(child, target_id)
				if result:
					return result

		if 'shadowRoots' in root_node and root_node['shadowRoots'] is not None:
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
