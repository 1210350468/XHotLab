from io import BytesIO
from zipfile import ZipFile

import httpx
from PIL import Image
from playwright.sync_api import expect, sync_playwright

BASE = 'http://127.0.0.1:8766'
HEADERS = {'X-XHotLab-Action': '1'}


def main():
    with httpx.Client(base_url=BASE, timeout=45) as client:
        trends_response = client.get('/api/trends', params={'limit': 200})
        trends_response.raise_for_status()
        trends = trends_response.json()
        assert any(item['media_count'] > 0 for item in trends)
        trend = next(item for item in trends
                     if any(media['kind'] == 'photo'
                            for media in client.get(f'/api/trends/{item["id"]}/media').json()))
        original = client.get(f'/api/trends/{trend["id"]}/media').json()
        assert original
        assert original[0]['source_url'].startswith('https://')

        draft_id = None
        queue_id = None
        try:
            response = client.post('/api/drafts', json={
                'trend_id': trend['id'], 'language': 'zh',
                'content': '测试工作台：从 X 中文原帖取得真实媒体，保存后通过编辑器发布。',
            })
            response.raise_for_status()
            draft_id = response.json()['id']

            response = client.post('/api/queue', json={'draft_ids': [draft_id]})
            response.raise_for_status()
            queue_id = response.json()[0]['id']

            imported = client.post(f'/api/queue/{queue_id}/media/import',
                                   headers=HEADERS)
            imported.raise_for_status()
            assert imported.json()['imported'] > 0

            choices = client.get(f'/api/queue/{queue_id}/media').json()
            images = [image for image in choices
                      if image['origin'] == 'source' and image['kind'] == 'photo'
                      and image['ready']]
            assert images
            selected = images[0]
            file_response = client.get(selected['url'])
            file_response.raise_for_status()
            with Image.open(BytesIO(file_response.content)) as image:
                assert image.format in ('JPEG', 'PNG', 'WEBP', 'GIF')
                assert image.width > 0

            response = client.put(f'/api/queue/{queue_id}/media',
                                  headers=HEADERS, json={'media_ids': [selected['id']]})
            response.raise_for_status()
            assert sum(item['selected'] for item in response.json()) == 1

            response = client.put(f'/api/queue/{queue_id}/media',
                                  headers=HEADERS, json={'media_ids': ['unknown']})
            assert response.status_code == 422

            response = client.get(f'/api/queue/{queue_id}/bundle')
            response.raise_for_status()
            with ZipFile(BytesIO(response.content)) as bundle:
                names = bundle.namelist()
                assert 'post.txt' in names
                assert 'source.json' in names
                picture = next(name for name in names if name.startswith('attachments/'))
                assert len(bundle.read(picture)) > 1000

            response = client.post(f'/api/queue/{queue_id}/prepare-browser')
            assert response.status_code == 403
            assert client.get(f'/api/queue/{queue_id}/browser-preparation').json() is None

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1050})
                page.goto(BASE, wait_until='domcontentloaded')
                page.locator('#posts-nav').click()
                checkbox = page.locator(
                    f'.queue-media-checkbox[data-id="{queue_id}"][value="{selected["id"]}"]',
                )
                expect(checkbox).to_be_checked(timeout=16000)
                assert page.locator(f'[data-action="prepare-media-browser"][data-id="{queue_id}"]').count() == 1
                assert page.locator(f'a[href="/api/queue/{queue_id}/bundle"]').count() == 1
                browser.close()
        finally:
            if queue_id:
                response = client.delete(f'/api/queue/{queue_id}')
                response.raise_for_status()
            if draft_id:
                response = client.delete(f'/api/drafts/{draft_id}')
                response.raise_for_status()

    print('Real X image media verified: metadata, CDN download, local JPEG, '
          'selected attachments, ZIP bundle and Edge publishing interface.')


if __name__ == '__main__':
    main()
