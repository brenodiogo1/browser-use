import asyncio
import json
import time

import aiofiles
import httpx
import tiktoken
from cdp_use import CDPClient
from playwright.async_api import async_playwright

from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.dom.a11y.service import A11yService
from browser_use.dom.a11y.views import (
	CombinedElementNode,
)


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

			# websites = [
			# 	'https://google.com',
			# 	'https://amazon.com',
			# 	'https://github.com',
			# ]

			await browser_session.start()
			page = await browser_session.get_current_page()
			a11y_service = A11yService(browser_session, cdp)
			await page.goto('https://google.com')

			cdp_targets = await cdp.send.Target.getTargets()
			print(cdp_targets)

			while True:
				await browser_session.remove_highlights()
				await asyncio.sleep(1)

				# wait until traffic is idle
				await browser_session._wait_for_stable_network()

				# print(f'\n{"=" * 50}\nTesting {website}\n{"=" * 50}')

				# Get combined tree
				print('Getting combined accessibility and DOM tree...')
				start_time = time.time()
				combined_tree = await a11y_service.get_combined_tree()
				end_time = time.time()
				print(f'Combined tree retrieval took {end_time - start_time:.2f} seconds')

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
					await f.write(json.dumps(combined_tree.model_dump(mode='json'), indent=2))
				print('Saved combined tree to tmp/combined_tree.json')

				print('\nFirst 10 lines of accessible elements output:')
				lines = accessible_output.split('\n')[:10]
				# for line in lines:
				# 	print(line)

				all_elements_state = await browser_session.get_state_summary(True)

				async with aiofiles.open('tmp/all_elements_state.txt', 'w') as f:
					await f.write(all_elements_state.element_tree.clickable_elements_to_string())
				print('Saved all elements state to tmp/all_elements_state.txt')
				print(
					'All elements state token count: ',
					len(encoding.encode(all_elements_state.element_tree.clickable_elements_to_string())),
				)

				print('Made', cdp.msg_id, 'cdp calls')

				input('Press Enter to continue to next website...')


if __name__ == '__main__':
	asyncio.run(test_combined_accessibility_tree())
