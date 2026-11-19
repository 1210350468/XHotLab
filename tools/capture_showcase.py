from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs' / 'assets'
EXTENSION = ROOT / 'edge-extension'
API = 'http://127.0.0.1:8766/'


def capture() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir=str(ROOT / 'data' / 'showcase_browser_profile'),
            channel='msedge',
            headless=True,
            viewport={'width': 1440, 'height': 900},
            device_scale_factor=1,
            args=[
                '--disable-extensions-except=' + str(EXTENSION),
                '--load-extension=' + str(EXTENSION),
            ],
        )
        errors = []
        page = browser.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(API, wait_until='domcontentloaded')
        expect(page.locator('#publish-workspace')).to_be_visible(timeout=30000)
        expect(page.locator('#publish-candidates .publish-candidate').first).to_be_visible(timeout=20000)
        page.evaluate('document.fonts.ready')
        page.add_style_tag(content='''
          .publish-candidate > img, .publish-candidate-cover,
          .publish-candidate-author, .publish-selected > img,
          .publish-selected a {filter:blur(6px)}
          *, *::before, *::after {animation:none!important;transition:none!important}
        ''')
        page.screenshot(path=str(ASSETS / 'publish-workbench.png'), animations='disabled')

        page.locator('#advanced-menu summary').click()
        page.locator('[data-category="all"]').click()
        expect(page.locator('#discovery-hero')).to_be_visible()
        expect(page.locator('.trend-card').first).to_be_visible(timeout=25000)
        page.add_style_tag(content='''
          .trend-card .trend-media-preview img,
          .trend-card .source-label {filter:blur(6px)}
          *, *::before, *::after {animation:none!important;transition:none!important}
        ''')
        page.screenshot(path=str(ASSETS / 'trends-discovery.png'), animations='disabled')

        worker = browser.service_workers[0] if browser.service_workers else (
            browser.wait_for_event('serviceworker', timeout=20000)
        )
        extension_id = worker.url.split('/')[2]
        panel = browser.new_page()
        panel.set_viewport_size({'width': 435, 'height': 860})
        panel.goto(f'chrome-extension://{extension_id}/sidepanel.html',
                   wait_until='domcontentloaded')
        expect(panel.locator('#connection')).to_have_class('connection ok', timeout=25000)
        panel.add_style_tag(content='''
          .card .author, .card .source, .card img {filter:blur(6px)}
          *, *::before, *::after {animation:none!important;transition:none!important}
        ''')
        panel.screenshot(path=str(ASSETS / 'edge-sidepanel.png'), animations='disabled')
        assert not errors, errors
        browser.close()

        cover = browser_svg_to_png(playwright)
        with Image.open(cover) as result:
            assert result.size == (1280, 640), result.size
        for name in ('social-preview.png', 'publish-workbench.png',
                     'trends-discovery.png', 'edge-sidepanel.png'):
            item = ASSETS / name
            with Image.open(item) as picture:
                picture.load()
                picture.save(item, optimize=True)
                print(f'{name}: {picture.width}x{picture.height}, {item.stat().st_size} bytes')
        assert cover.stat().st_size < 1_000_000, 'GitHub Social preview PNG exceeds 1 MB'


def browser_svg_to_png(playwright) -> Path:
    browser = playwright.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 640}, device_scale_factor=1)
    response = page.goto((ASSETS / 'xhotlab-cover.svg').as_uri())
    assert response is not None and response.ok
    page.evaluate('document.fonts.ready')
    output = ASSETS / 'social-preview.png'
    page.locator('svg').screenshot(path=str(output))
    browser.close()
    return output


if __name__ == '__main__':
    capture()
