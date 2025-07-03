import asyncio
import json
import time

import aiofiles

from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.browser.types import ViewportSize
from browser_use.dom.a11y.service import A11yService


async def test_accessibility_tree():
	# async with async_patchright() as patchright:
	browser_session = BrowserSession(
		browser_profile=BrowserProfile(
			# executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
			window_size=ViewportSize(width=1100, height=1000),
			disable_security=True,
			wait_for_network_idle_page_load_time=1,
			headless=False,
		),
		# playwright=patchright,
	)

	websites = [
		# 'https://demos.telerik.com/kendo-react-ui/treeview/overview/basic/func?theme=default-ocean-blue-a11y',
		'https://google.com',
		'https://www.ycombinator.com/companies',
		'https://kayak.com/flights',
		# 'https://en.wikipedia.org/wiki/Humanist_Party_of_Ontario',
		# 'https://www.google.com/travel/flights?tfs=CBwQARoJagcIARIDTEpVGglyBwgBEgNMSlVAAUgBcAGCAQsI____________AZgBAQ&tfu=KgIIAw&hl=en-US&gl=US',
		# # 'https://www.concur.com/?&cookie_preferences=cpra',
		# 'https://immobilienscout24.de',
		'https://docs.google.com/spreadsheets/d/1INaIcfpYXlMRWO__de61SHFCaqt1lfHlcvtXZPItlpI/edit',
		'https://www.zeiss.com/career/en/job-search.html?page=1',
		'https://www.mlb.com/yankees/stats/',
		'https://www.amazon.com/s?k=laptop&s=review-rank&crid=1RZCEJ289EUSI&qid=1740202453&sprefix=laptop%2Caps%2C166&ref=sr_st_review-rank&ds=v1%3A4EnYKXVQA7DIE41qCvRZoNB4qN92Jlztd3BPsTFXmxU',
		'https://reddit.com',
		'https://codepen.io/geheimschriftstift/pen/mPLvQz',
		'https://www.google.com/search?q=google+hi&oq=google+hi&gs_lcrp=EgZjaHJvbWUyBggAEEUYOTIGCAEQRRhA0gEIMjI2NmowajSoAgCwAgE&sourceid=chrome&ie=UTF-8',
		'https://amazon.com',
		'https://github.com',
	]

	await browser_session.start()
	page = await browser_session.get_current_page()
	# dom_service = DomService(page)

	a11y_service = A11yService(browser_session)

	for website in websites:
		# sleep 2
		await page.goto(website)
		await asyncio.sleep(1)

		last_clicked_index = None  # Track the index for text input
		while True:
			print(f'\n{"=" * 50}\nTesting {website}\n{"=" * 50}')

			# Get/refresh the state (includes removing old highlights)
			print('\nGetting accessibility tree...')

			start_time = time.time()
			accessibility_tree = await a11y_service.get_accessibility_tree()
			end_time = time.time()
			print(f'get_accessibility_tree took {end_time - start_time:.2f} seconds')
			print(f'Accessibility tree nodes: {len(accessibility_tree.nodes)}')

			print('\nGetting complete DOM tree (including iframes and shadow DOM)...')
			start_time = time.time()
			dom_tree = await a11y_service.get_entire_dom_tree()
			end_time = time.time()
			print(f'get_entire_dom_tree took {end_time - start_time:.2f} seconds')
			print('DOM tree stats:')
			print(f'  - Total nodes: {dom_tree.total_nodes}')
			print(f'  - Frame count: {dom_tree.frame_count}')
			print(f'  - Root node ID: {dom_tree.root.nodeId}')
			print(f'  - Root node name: {dom_tree.root.nodeName}')

			all_backend_ids_accessibility = [
				node.backendDOMNodeId
				for node in accessibility_tree.nodes
				if not node.ignored and node.backendDOMNodeId is not None
			]

			all_backend_ids_dom = [node.backendNodeId for node in dom_tree.nodes.values()]

			all_backend_ids_accessibility_set = set(all_backend_ids_accessibility)
			all_backend_ids_dom_set = set(all_backend_ids_dom)

			missing_from_dom = all_backend_ids_accessibility_set - all_backend_ids_dom_set

			both = all_backend_ids_accessibility_set & all_backend_ids_dom_set

			print(f'Both: {len(both)}')
			print(f'Missing from dom: {len(missing_from_dom)}')
			print(f'Accessibility: {len(all_backend_ids_accessibility_set)}')
			print(f'DOM: {len(all_backend_ids_dom_set)}')

			# save accessibility tree to file
			filtered_accessibility_tree_nodes = [node for node in accessibility_tree.nodes if not node.ignored]

			# Convert to dict for JSON serialization
			accessibility_data = [node.model_dump() for node in filtered_accessibility_tree_nodes]
			async with aiofiles.open('tmp/accessibility_tree.json', 'w') as f:
				await f.write(json.dumps(accessibility_data, indent=2))
			print('saved to tmp/accessibility_tree.json')

			# save dom tree with filtered accessibility tree nodes
			filtered_dom_tree_nodes = [node for node in dom_tree.nodes.values() if node.backendNodeId in both]

			# Convert to dict for JSON serialization
			dom_data = [node.model_dump() for node in filtered_dom_tree_nodes]
			async with aiofiles.open('tmp/dom_tree.json', 'w') as f:
				await f.write(json.dumps(dom_data, indent=2))
			print('saved to tmp/dom_tree.json')

			input('Press Enter to continue...')
			pass


if __name__ == '__main__':
	asyncio.run(test_accessibility_tree())
	# asyncio.run(test_process_html_file()) # Commented out the other test
