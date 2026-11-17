import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from . import browser_publish, media, store
from .config import ROOT

PUBLISH_PROFILE = ROOT / 'data' / 'publisher_edge_profile'


def start(queue_id: str) -> dict:
    item = store.queue_media_info(queue_id)
    if item is None:
        raise LookupError('待发布内容不存在')
    if item['status'] not in ('queued', 'opened'):
        raise ValueError('发布队列任务已经结束')
    browser_publish.compose_url(item['content'])
    selected = media.selected_media_files(queue_id)
    if not selected:
        raise ValueError('请先在发布队列中选择需要上传的图片或视频')
    job = store.new_browser_prep_job(queue_id)
    worker = sys.executable
    flags = 0
    if sys.platform == 'win32':
        worker = str(Path(sys.executable).with_name('pythonw.exe'))
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [worker, '-m', 'app.publish_worker', job['id']],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
        start_new_session=sys.platform != 'win32',
    )
    return job


def run(job_id: str) -> None:
    job = store.get_browser_prep_job(job_id)
    if job is None:
        raise LookupError('浏览器发布任务不存在')
    item = store.queue_media_info(job['queue_id'])
    if item is None:
        raise LookupError('待发布内容不存在')
    photos = media.selected_media_files(job['queue_id'])
    store.update_browser_prep_job(job_id, 'running', '正在启动专用 Edge 浏览器')
    PUBLISH_PROFILE.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch_persistent_context(
                user_data_dir=str(PUBLISH_PROFILE),
                channel='msedge',
                headless=False,
                accept_downloads=False,
            )
            try:
                page = browser.pages[0] if browser.pages else browser.new_page()
                page.goto('https://x.com/compose/post',
                          wait_until='domcontentloaded', timeout=60000)
                editor = page.locator('[data-testid="tweetTextarea_0"]').first
                try:
                    editor.wait_for(state='visible', timeout=15000)
                except PlaywrightTimeoutError:
                    store.update_browser_prep_job(
                        job_id, 'waiting_login',
                        '请在打开的 Edge 窗口完成 X 登录，然后关闭窗口并重新点击图文发布',
                    )
                    page.wait_for_event('close', timeout=300000)
                    store.update_browser_prep_job(job_id, 'closed', 'X 登录窗口已关闭，可以重新准备图文')
                    return

                editor.fill(item['content'])
                uploader = page.locator('input[data-testid="fileInput"]').first
                uploader.wait_for(state='attached', timeout=20000)
                uploader.set_input_files([str(photo) for photo in photos], timeout=50000)
                page.locator('[data-testid="attachments"]').first.wait_for(
                    state='visible', timeout=35000,
                )
                store.update_browser_prep_job(
                    job_id, 'ready',
                    f'已在 X 编辑器填入文案并添加 {len(photos)} 张图片，请检查后点击发布',
                )
                page.wait_for_event('close', timeout=1800000)
                store.update_browser_prep_job(job_id, 'closed', 'X 编辑窗口已关闭')
            finally:
                browser.close()
    except (PlaywrightError, OSError, ValueError) as error:
        store.update_browser_prep_job(
            job_id, 'failed', f'{type(error).__name__}: {error}',
        )
        raise


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise ValueError('Usage: python -m app.publish_worker <job_id>')
    run(sys.argv[1])
