import asyncio
import json
import os

import aiofiles
import httpx
from cdp_use import CDPClient
from cdp_use.cdp.accessibility.commands import GetFullAXTreeReturns
from cdp_use.cdp.accessibility.types import AXNode
from playwright.async_api import async_playwright

from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.dom.a11y.service import A11yService


async def test_combined_accessibility_tree():
	async with async_playwright() as p:
		browser = await p.chromium.launch(args=['--remote-debugging-port=9222'], headless=False)

		async with httpx.AsyncClient() as client:
			version_info = await client.get('http://localhost:9222/json/version')
			browser_ws_url = version_info.json()['webSocketDebuggerUrl']

		async with CDPClient(browser_ws_url) as cdp:
			"""Test the combined DOM + accessibility tree with new Pydantic types."""
			browser_session = BrowserSession(
				browser=browser,
				browser_profile=BrowserProfile(
					# window_size=ViewportSize(width=1500, height=1000),
					# disable_security=True,
					wait_for_network_idle_page_load_time=1,
					# headless=False,
				),
			)

			await browser_session.start()
			page = await browser_session.get_current_page()
			a11y_service = A11yService(browser_session, cdp)
			await page.goto('https://google.com')

			cdp_targets = await cdp.send.Target.getTargets()
			print(cdp_targets)

			session = await cdp.send.Target.attachToTarget(
				params={'targetId': cdp_targets['targetInfos'][0]['targetId'], 'flatten': True}
			)
			session_id = session['sessionId']

			# Compare the AX tree created with getFullAXTree with the progressively created AX tree
			await cdp.send.Accessibility.enable(session_id=session_id)
			await cdp.send.DOM.enable(session_id=session_id)
			response = await cdp.send.Accessibility.getFullAXTree(session_id=session_id)

			print(response)

			# if dir does not exist, create it
			if not os.path.exists('tmp/ax_tree'):
				os.makedirs('tmp/ax_tree')

			# save to file
			async with aiofiles.open('tmp/ax_tree/ax_tree_full.json', 'w') as f:
				await f.write(json.dumps(response, indent=2))

			progressive_response = await progressive_ax_tree(cdp, session_id)
			print(progressive_response)

			async with aiofiles.open('tmp/ax_tree/ax_tree_progressive.json', 'w') as f:
				await f.write(json.dumps(progressive_response, indent=2))

			progressive_response = await full_to_progressive_ax_tree(response)
			async with aiofiles.open('tmp/ax_tree/ax_tree_progressive_full.json', 'w') as f:
				await f.write(json.dumps(progressive_response, indent=2))

			print(progressive_response)


async def full_to_progressive_ax_tree(full_ax_tree: GetFullAXTreeReturns) -> GetFullAXTreeReturns:
	# take the first node, and add all its children to the progressive tree if they are not ignored, repeat for all nodes (recursively)
	tree_lookup: dict[str, AXNode] = {node['nodeId']: node for node in full_ax_tree['nodes']}

	if not full_ax_tree['nodes']:
		return {'nodes': []}

	first_node = full_ax_tree['nodes'][0]
	progressive_tree: list[AXNode] = []

	if not first_node.get('childIds'):
		return {'nodes': []}

	# Add the first node itself if it's not ignored, as it's the root of our traversal.
	if not first_node.get('ignored', True):
		progressive_tree.append(first_node)

	for child_id in first_node.get('childIds', []):
		_get_descendants_recursive(child_id, tree_lookup, progressive_tree)

	return {'nodes': progressive_tree}


def _get_descendants_recursive(node_id: str, tree_lookup: dict[str, AXNode], result_nodes: list[AXNode]):
	"""Recursively traverses and adds non-ignored nodes to the result list."""
	if node_id not in tree_lookup:
		return

	node = tree_lookup[node_id]

	# Add the node itself if it's not ignored.
	if not node.get('ignored', True):
		result_nodes.append(node)

	# Recurse for children, but only if the current node wasn't ignored.
	# This prevents traversing down ignored subtrees.
	if not node.get('ignored', True):
		for child_id in node.get('childIds', []):
			_get_descendants_recursive(child_id, tree_lookup, result_nodes)


async def progressive_ax_tree(cdp: CDPClient, session_id: str) -> GetFullAXTreeReturns:
	# Get the root AX node first
	root_response = await cdp.send.Accessibility.getRootAXNode(session_id=session_id)

	if not root_response or 'node' not in root_response:
		return {'nodes': []}

	root_node = root_response['node']

	# Get all interesting nodes starting from root
	interesting_nodes: list[AXNode] = []
	if not root_node.get('ignored', True):
		interesting_nodes.append(root_node)

	# Recursively get interesting child nodes
	# if 'childIds' in root_node:
	# 	for child_id in root_node['childIds']:
	child_nodes = await _get_interesting_nodes(cdp, session_id, root_node['nodeId'])
	interesting_nodes.extend(child_nodes)

	return {'nodes': interesting_nodes}


async def _get_interesting_nodes(cdp: CDPClient, session_id: str, node_id: str) -> list[AXNode]:
	"""Recursively get interesting accessibility nodes, filtering out ignored ones."""
	result: list[AXNode] = []

	try:
		# Get child nodes for this node
		child_response = await cdp.send.Accessibility.getChildAXNodes(session_id=session_id, params={'id': node_id})

		for node in child_response.get('nodes', []):
			# Include node if it's not ignored
			if not node.get('ignored', True):
				result.append(node)

				# Only recurse if the node is not ignored
				if 'childIds' in node:
					for child_id in node['childIds']:
						child_nodes = await _get_interesting_nodes(cdp, session_id, child_id)
						result.extend(child_nodes)

	except Exception as e:
		pass

	return result


if __name__ == '__main__':
	asyncio.run(test_combined_accessibility_tree())
