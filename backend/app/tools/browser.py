"""Worker-only Playwright flow. No model-supplied evaluate() or selectors."""
import secrets
from urllib.parse import urlsplit
from playwright.async_api import async_playwright
from ..schemas import BrowserArgs


async def browser_test(args: BrowserArgs):
    from ..browser_worker import fixture_origin
    target = fixture_origin()
    marker = secrets.token_hex(12)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True, timeout=5000)
        context = await browser.new_context(service_workers='block', accept_downloads=False)

        async def restrict(route):
            url = urlsplit(route.request.url)
            if url.scheme == 'http' and url.netloc == urlsplit(target).netloc:
                await route.continue_()
            else:
                await route.abort()

        try:
            await context.route('**/*', restrict)
            async def block_socket(socket):
                await socket.close()
            await context.route_web_socket('**/*', block_socket)
            page = await context.new_page()
            page.set_default_timeout(4000)
            if args.authenticate or args.review_text is not None:
                await page.goto(target + '/signup')
                username, password = 'bmf_' + secrets.token_hex(5), secrets.token_hex(12)
                await page.get_by_label('Username', exact=True).fill(username)
                await page.get_by_label('Password', exact=True).fill(password)
                await page.get_by_role('button', name='Create account', exact=True).click()
                await page.wait_for_url('**/users/*/edit')
                await page.get_by_role('button', name='Log out', exact=True).click()
                await page.wait_for_url(target + '/')
                await page.goto(target + '/login')
                await page.get_by_label('Username', exact=True).fill(username)
                await page.get_by_label('Password', exact=True).fill(password)
                await page.get_by_role('button', name='Log in', exact=True).click()
                await page.wait_for_url(target + '/')
            if args.review_text is not None:
                response = await page.goto(f'{target}/books/{args.book_id}')
                if response is None or response.status != 200:
                    raise ValueError('Book detail unavailable')
                # The model writes a marker template in its candidate HTML payload.
                payload = args.review_text.replace('{{MARKER}}', marker)
                if not payload.strip() or len(payload) > 5000:
                    raise ValueError('Marker-substituted review exceeds application limits')
                await page.get_by_label('Your review', exact=True).fill(payload)
                await page.get_by_role('button', name='Publish review', exact=True).click()
                await page.wait_for_load_state('domcontentloaded')
                await page.get_by_text('Your review is on the shelf.', exact=True).wait_for(state='visible')
                if args.revisit_anonymous:
                    await context.clear_cookies()
                response = await page.goto(f'{target}/books/{args.book_id}')
            else:
                response = await page.goto(target + args.path)
            if response is None or response.status != 200:
                raise ValueError('Observation page unavailable')
            # Observe for a bounded window; never execute model-generated JS via evaluate.
            try:
                await page.wait_for_function('value => document.documentElement.dataset.bmfMarker === value',
                                             arg=marker, timeout=1200)
            except Exception as exc:
                from playwright.async_api import TimeoutError as PlaywrightTimeout
                if not isinstance(exc, PlaywrightTimeout):
                    raise
            executed = await page.evaluate('(value) => document.documentElement.dataset.bmfMarker === value', marker)
            return {'marker_executed': executed,
                    'marker_tested': args.review_text is not None and '{{MARKER}}' in args.review_text,
                    'anonymous_revisit': args.revisit_anonymous,
                    'path': urlsplit(page.url).path,
                    'body_excerpt': (await page.locator('body').inner_text())[:4000],
                    'scope': 'One page, fresh account, bounded 1.2-second marker observation'}
        finally:
            await context.close()
            await browser.close()
