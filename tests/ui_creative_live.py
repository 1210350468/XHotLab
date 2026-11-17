from io import BytesIO
from zipfile import ZipFile

import httpx
from PIL import Image
from playwright.sync_api import expect, sync_playwright

BASE = 'http://127.0.0.1:8766'


def main():
    with httpx.Client(base_url=BASE, timeout=25) as client:
        status_response = client.get('/api/creative/status')
        status_response.raise_for_status()
        settings = status_response.json()
        assert settings['enabled']
        assert settings['key_configured']
        assert settings['per_run'] >= 1

        response = client.get('/api/creative/packs')
        response.raise_for_status()
        packs = response.json()
        assert len(packs) >= 1
        assert all(pack['source_url'].startswith('https://x.com/') for pack in packs)
        assert all(pack['category'].startswith('x_zh') for pack in packs)
        pack = packs[0]
        assert len(pack['images']) == 3
        assert len(pack['content']) > 20
        for url in pack['images']:
            response = client.get(url)
            response.raise_for_status()
            with Image.open(BytesIO(response.content)) as image:
                assert image.format == 'PNG'
                assert image.size == (900, 1200)

        response = client.get('/api/creative/packs/' + pack['id'] + '/download')
        response.raise_for_status()
        with ZipFile(BytesIO(response.content)) as archive:
            assert {
                'cover.png', 'context.png', 'discussion.png', 'card.json', 'post.txt',
                'original_media_attribution.json',
            }.issubset(set(archive.namelist()))
            assert '来源：'.encode('utf-8') in archive.read('post.txt')

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})
        page.goto(BASE, wait_until='domcontentloaded')
        page.locator('#creative-nav').click()
        expect(page.locator('.creative-pack')).to_have_count(len(packs), timeout=12000)
        assert page.locator('.creative-gallery img').count() >= 3
        assert page.locator('a[href$="/download"]').count() >= 1
        assert page.locator('.creative-control').count() == 1
        browser.close()

    print(f'Real open-source visual flow verified: {len(packs)} image packs, '
          '3 PNG files at 900x1200, ZIP archive and Edge workspace.')


if __name__ == '__main__':
    main()
