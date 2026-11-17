import httpx
from playwright.sync_api import expect, sync_playwright

BASE = 'http://127.0.0.1:8766'


def main():
    with httpx.Client(base_url=BASE, timeout=20) as client:
        response = client.get('/api/trends', params={'limit': 1})
        response.raise_for_status()
        trend = response.json()[0]

        response = client.post('/api/drafts', json={
            'trend_id': trend['id'],
            'language': 'en',
            'content': 'Local UI workflow verification for XHotLab queue. Human review required.',
        })
        response.raise_for_status()
        draft_id = response.json()['id']
        queue_id = None

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 900})
                page.goto(BASE, wait_until='domcontentloaded')
                page.locator('#advanced-menu summary').click()
                page.locator('#drafts-nav').click()
                checkbox = page.locator(f'.draft-checkbox[value="{draft_id}"]')
                checkbox.wait_for(state='visible', timeout=12000)
                checkbox.check()
                page.locator('[data-action="enqueue-selected"]').click()

                expect(page.locator('#breadcrumb-name')).to_have_text('待发布队列', timeout=12000)
                items = client.get('/api/queue').json()
                queue_id = next(item['id'] for item in items if item['draft_id'] == draft_id)
                expect(page.locator(f'[data-action="skip-queue"][data-id="{queue_id}"]')).to_be_visible(timeout=12000)
                assert not page.locator('#toast-container .error').count()
                if any(attachment['kind'] == 'video'
                       for item in items for attachment in item['attachments']):
                    assert page.locator('.media-choice-thumb video').count() >= 1
                page.locator(f'[data-action="skip-queue"][data-id="{queue_id}"]').click()
                page.locator(f'[data-action="requeue"][data-id="{queue_id}"]').wait_for(timeout=12000)
                page.locator(f'[data-action="requeue"][data-id="{queue_id}"]').click()
                page.locator(f'[data-action="open-queue"][data-id="{queue_id}"]').wait_for(timeout=12000)

                assert page.locator(f'[data-action="remove-queue"][data-id="{queue_id}"]').count() == 1
                browser.close()
        finally:
            if queue_id:
                response = client.delete(f'/api/queue/{queue_id}')
                response.raise_for_status()
            response = client.delete(f'/api/drafts/{draft_id}')
            response.raise_for_status()

    print('Real Edge DOM workflow passed: select draft, enqueue, skip and requeue.')


if __name__ == '__main__':
    main()
