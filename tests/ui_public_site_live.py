import json
from pathlib import Path

from PIL import Image
from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'docs'
ASSETS = DOCS / 'assets'


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        for width, height in ((1440, 900), (980, 800), (390, 844)):
            page = browser.new_page(viewport={'width': width, 'height': height})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto((DOCS / 'index.html').as_uri(), wait_until='domcontentloaded')
            expect(page.get_by_role('heading', name='内容灵感， 直接走向发布。')).to_be_visible()
            expect(page.get_by_role('heading', name='常见问题')).to_be_visible()
            expect(page.locator('.preview img')).to_have_count(3)
            assert page.evaluate('''async () => {
              const images = [...document.images];
              await Promise.all(images.map(async image => {
                image.loading = 'eager';
                await image.decode();
              }));
              return images.every(image => image.complete && image.naturalWidth > 0);
            }'''), '项目页图片加载失败'
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (
                '项目页出现横向滚动', width)
            assert not errors, errors
            metadata = page.locator('script[type="application/ld+json"]').text_content()
            structured = json.loads(metadata)
            assert any(value['@type'] == 'SoftwareSourceCode'
                       for value in structured['@graph'])
            assert any(value['@type'] == 'FAQPage'
                       for value in structured['@graph'])
            assert page.locator('link[rel="canonical"]').get_attribute('href') == (
                'https://1210350468.github.io/XHotLab/')
            print(f'Pages desktop/mobile layout and metadata: {width}x{height} OK')
            page.close()
        browser.close()

    for name, dimensions in (
        ('social-preview.png', (1280, 640)),
        ('publish-workbench.png', (1440, 900)),
        ('trends-discovery.png', (1440, 900)),
        ('edge-sidepanel.png', (435, 860)),
    ):
        target = ASSETS / name
        with Image.open(target) as picture:
            picture.verify()
        with Image.open(target) as picture:
            assert picture.size == dimensions, (name, picture.size)
        assert target.stat().st_size < 1_000_000, name

    for document in (ROOT / 'README.md', DOCS / 'faq.md',
                     DOCS / 'getting-started.md', DOCS / 'architecture.md',
                     DOCS / 'sitemap.xml', DOCS / 'llms.txt', ROOT / 'LICENSE'):
        assert document.exists() and document.stat().st_size > 0, document
    print('Public image assets, documentation and social preview verified.')


if __name__ == '__main__':
    main()
