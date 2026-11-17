import shutil
from pathlib import Path
from uuid import uuid4

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / 'edge-extension'
DATA = ROOT / 'data'


def extension_identity(browser, installed_path: Path, profile: Path):
    context = browser.chromium.launch_persistent_context(
        user_data_dir=str(profile),
        channel='msedge', headless=True,
        args=[
            '--disable-extensions-except=' + str(installed_path),
            '--load-extension=' + str(installed_path),
        ],
    )
    worker = context.service_workers[0] if context.service_workers else (
        context.wait_for_event('serviceworker', timeout=25000))
    runtime_id = worker.url.split('/')[2]
    page = context.new_page()
    page.goto('http://127.0.0.1:8766/', wait_until='domcontentloaded')
    response = page.evaluate('''async () => new Promise((resolve, reject) => {
      const requestId = crypto.randomUUID();
      const timeout = setTimeout(() => reject(new Error('扩展发现超时')), 8000);
      const handler = (event) => {
        if (event.source !== window || event.origin !== location.origin) return;
        if (event.data?.type !== 'XH_EXTENSION_FOUND' || event.data.requestId !== requestId) return;
        window.removeEventListener('message', handler);
        clearTimeout(timeout);
        resolve(event.data);
      };
      window.addEventListener('message', handler);
      window.postMessage({type: 'XH_DISCOVER_EXTENSION', requestId}, location.origin);
    })''')
    assert response['extensionId'] == runtime_id
    assert response['version'] == '1.2.9'
    context.close()
    return runtime_id


def main():
    copied_extension = DATA / ('portable_extension_checkout_' + uuid4().hex[:10])
    shutil.copytree(EXTENSION, copied_extension)
    with sync_playwright() as playwright:
        original_id = extension_identity(
            playwright, EXTENSION, DATA / ('portable_original_profile_' + uuid4().hex[:10]))
        copied_id = extension_identity(
            playwright, copied_extension, DATA / ('portable_copied_profile_' + uuid4().hex[:10]))
        assert original_id != copied_id, (original_id, copied_id)
    print('Two real unpacked extension paths produced different IDs; both were discovered by XHotLab.')


if __name__ == '__main__':
    main()
