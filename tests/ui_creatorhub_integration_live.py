import os
import re
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
XHOTLAB = os.environ.get('XHOTLAB_URL', 'http://127.0.0.1:8766')
CREATORHUB = 'http://127.0.0.1:8000'
PLATFORMS = {'douyin', 'xhs', 'kuaishou', 'shipinhao', 'tiktok'}


def main():
    with httpx.Client(timeout=30, trust_env=False) as client:
        upstream = client.get(CREATORHUB + '/health')
        upstream.raise_for_status()
        assert upstream.json() == {'status': 'ok'}

        status = client.get(XHOTLAB + '/api/creatorhub/status')
        status.raise_for_status()
        assert status.json()['installed'] and status.json()['running']
        assert status.json()['url'] == CREATORHUB

        dashboard = client.get(XHOTLAB + '/api/creatorhub/dashboard')
        dashboard.raise_for_status()
        body = dashboard.json()
        assert {row['id'] for row in body['platforms']} == PLATFORMS
        assert all('read_logged_in' in account for account in body['accounts'])
        for platform in body['platforms']:
            original = client.get(CREATORHUB + '/api/overview/summary',
                                  params={'platform': platform['id']})
            original.raise_for_status()
            assert platform['accounts'] == original.json()['accounts']
            assert platform['monitors'] == original.json()['monitors']

        activity = client.get(XHOTLAB + '/api/creatorhub/activity')
        activity.raise_for_status()
        assert set(activity.json()) == {
            'monitors', 'collections', 'publish_tasks', 'downloads'
        }
        for rows in activity.json().values():
            assert isinstance(rows, list)

        unauthorized = client.post(XHOTLAB + '/api/creatorhub/start')
        assert unauthorized.status_code == 403
        invalid = client.post(
            XHOTLAB + '/api/creatorhub/share',
            headers={'X-XHotLab-Action': '1'},
            json={'url': 'https://example.com/video/123', 'download': False}
        )
        assert invalid.status_code == 422
        assert client.post(
            XHOTLAB + '/api/creatorhub/start',
            headers={'X-XHotLab-Action': '1'}
        ).json()['running']

    profile = ROOT / 'data' / 'edge_extension_creatorhub_profile_v125'
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel='msedge',
            headless=True,
            args=[
                '--disable-extensions-except=' + str(ROOT / 'edge-extension'),
                '--load-extension=' + str(ROOT / 'edge-extension'),
            ],
            viewport={'width': 1250, 'height': 850},
        )
        worker = browser.service_workers[0] if browser.service_workers else (
            browser.wait_for_event('serviceworker', timeout=25000))
        extension_id = worker.url.split('/')[2]
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        if XHOTLAB != 'http://127.0.0.1:8766':
            page.route(
                'http://127.0.0.1:8766/**',
                lambda route: route.continue_(
                    url=route.request.url.replace(
                        'http://127.0.0.1:8766', XHOTLAB, 1)),
            )
        page.goto('chrome-extension://' + extension_id + '/sidepanel.html',
                  wait_until='domcontentloaded')
        expect(page.locator('#connection')).to_have_class('connection ok', timeout=25000)
        page.get_by_role('button', name='多平台').click()
        expect(page.get_by_text('XHotLab · 本地多平台服务')).to_be_visible()
        expect(page.get_by_text('抖音', exact=True)).to_be_visible()
        expect(page.get_by_text('小红书', exact=True)).to_be_visible()
        expect(page.get_by_text('快手', exact=True)).to_be_visible()
        expect(page.get_by_text('视频号', exact=True)).to_be_visible()
        expect(page.get_by_text('TikTok', exact=True)).to_be_visible()
        expect(page.get_by_role('button',
                                name='打开 XHotLab 多平台运营中心')).to_be_visible()
        expect(page.locator('#creatorhub-share-link')).to_be_visible()
        expect(page.locator('#creatorhub-share-account')).to_be_visible()
        expect(page.locator('#creatorhub-share-account')).to_have_value('')
        assert {'1', '2'} <= set(page.locator('#creatorhub-share-account option').evaluate_all(
            '(nodes) => nodes.map((node) => node.value)'))
        expect(page.get_by_text('最近采集与发布任务')).to_be_visible()
        with browser.expect_page() as next_tab:
            page.get_by_role(
                'button', name='打开 XHotLab 多平台运营中心'
            ).click()
        workbench = next_tab.value
        workbench.wait_for_url(CREATORHUB + '/', timeout=30000)
        expect(workbench.locator('.brand h1')).to_contain_text('XHotLab')
        expect(workbench.locator('.xhotlab-return')).to_be_visible()
        assert workbench.locator('iframe').count() == 0
        expect(workbench.locator('.brand-mark img')).to_have_attribute('src', '/static/brand.svg')
        if workbench.locator('.wb-sheet-overlay[data-state="open"]').count():
            workbench.keyboard.press('Escape')
            expect(workbench.locator('.wb-sheet-overlay[data-state="open"]')).to_have_count(0)
        workbench.locator('.xhotlab-return').click()
        workbench.wait_for_url(XHOTLAB + '/', timeout=20000)
        workbench.locator('#advanced-menu summary').click()
        expect(workbench.locator('#creatorhub-nav')).to_be_visible()
        expect(workbench.locator('.sidebar .brand-mark img')).to_have_attribute(
            'src', re.compile(r'^/assets/brand\.svg\?v=\d+$'))
        workbench.locator('#creatorhub-nav').click()
        workbench.wait_for_url(CREATORHUB + '/', timeout=30000)
        assert workbench.locator('iframe').count() == 0
        expect(workbench).to_have_title(re.compile('XHotLab'), timeout=15000)
        assert not errors, errors
        browser.close()
    print('Real XHotLab multi-platform integration passed: five platform summaries, '
          'account API, one-page branded navigation, and Microsoft Edge side panel.')


if __name__ == '__main__':
    main()
