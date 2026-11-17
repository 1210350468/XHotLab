from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8766'
EXTENSION = ROOT / 'edge-extension'


def main():
    with httpx.Client(base_url=BASE, timeout=15) as client:
        response = client.get('/api/health')
        response.raise_for_status()
        assert response.json()['ok']
        response = client.get('/api/trends', params={'limit': 15})
        response.raise_for_status()
        assert response.json()

    profile = ROOT / 'data' / 'edge_extension_live_profile_v129'
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel='msedge',
            headless=True,
            args=[
                '--disable-extensions-except=' + str(EXTENSION),
                '--load-extension=' + str(EXTENSION),
            ],
            viewport={'width': 1280, 'height': 950},
        )
        worker = browser.service_workers[0] if browser.service_workers else (
            browser.wait_for_event('serviceworker', timeout=25000))
        assert worker.url.startswith('chrome-extension://')
        extension_id = worker.url.split('/')[2]
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        response = page.goto('chrome-extension://' + extension_id + '/sidepanel.html',
                             wait_until='domcontentloaded')
        assert response.status == 200
        expect(page.locator('#connection')).to_have_class('connection ok', timeout=20000)
        expect(page.locator('#trend-list .card').first).to_be_visible()
        count = page.locator('#trend-list .card').count()
        assert count >= 5

        page.get_by_role('button', name='当前帖').click()
        expect(page.locator('#capture-current')).to_be_visible()
        page.get_by_role('button', name='图文', exact=True).click()
        expect(page.locator('#studio-content')).to_be_visible()
        page.get_by_role('button', name='发布', exact=True).click()
        expect(page.locator('#queue-content')).to_be_visible()
        assert page.locator('#queue-content .card').count() >= 1
        expect(page.get_by_role('button', name='在当前 Edge 主窗口准备发布')).to_be_visible()
        background = worker.evaluate('''() => ({
          version: chrome.runtime.getManifest().version,
          connectListener: chrome.runtime.onConnect.hasListeners(),
          messageListener: chrome.runtime.onMessage.hasListeners(),
          runtimeId: chrome.runtime.id
        })''')
        assert background['version'] == '1.2.9'
        assert page.locator('.brand-mark img').get_attribute('src') == 'brand.svg'
        assert page.locator('.tab .tab-icon').count() == 5
        assert background['connectListener'] and background['messageListener']
        response = page.evaluate('''async () => {
          const port = chrome.runtime.connect({name: 'XH_PREPARE_QUEUE_ITEM'});
          return await new Promise((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('发布通道没有返回消息')), 12000);
            port.onMessage.addListener((message) => {
              if (message.type !== 'result') return;
              clearTimeout(timeout);
              port.disconnect();
              resolve(message);
            });
            port.onDisconnect.addListener(() => reject(new Error('发布通道提前断开')));
            port.postMessage({queueId: 'xhotlab-protocol-check-absent'});
          });
        }''')
        assert response['ok'] is False
        assert '发布队列中找不到' in response['error']
        assert not errors, errors
        browser.close()

    print('Real Microsoft Edge MV3 extension passed: loaded service worker, '
          'real localhost API, Chinese trending cards, creation and media queue; '
          f'{count} visible posts, extension ID {extension_id}.')


if __name__ == '__main__':
    main()
