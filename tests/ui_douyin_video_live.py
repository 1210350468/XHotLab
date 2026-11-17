import os
from datetime import datetime
from pathlib import Path

import httpx
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
API = os.environ.get('XHOTLAB_URL', 'http://127.0.0.1:8766')
CREATORHUB = os.environ.get('CREATORHUB_URL', 'http://127.0.0.1:8000')


def main():
    with httpx.Client(timeout=35, trust_env=False) as client:
        response = client.get(API + '/api/douyin/videos')
        response.raise_for_status()
        candidates = response.json()
        assert len(candidates) >= 3
        upstream = client.get(CREATORHUB + '/api/collections/1/contents')
        upstream.raise_for_status()
        originals = {
            'douyin:' + item['aweme_id']: item
            for item in upstream.json()['items']
        }
        queue_response = client.get(API + '/api/queue')
        queue_response.raise_for_status()
        queue_items = {item['id']: item for item in queue_response.json()}
        for video in candidates[:3]:
            original = originals[video['id']]
            assert video['source_url'] == original['url']
            assert video['author_name'] == original['author_name']
            assert video['like_count'] == original['like_count']
            assert 'rights_status' not in video
            assert datetime.fromisoformat(video['scheduled_at']).tzinfo
            queue = queue_items[video['queue_id']]
            assert queue['status'] == 'queued'
            assert queue['content'].strip()
            assert queue['video_source']['source_url'] == video['source_url']
            assert queue['video_source']['id'] == video['id']

        assert all('rights_status' not in video for video in candidates)

    profile = ROOT / 'data' / 'edge_douyin_live_profile_v128'
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            channel='msedge',
            headless=True,
            args=[
                '--disable-extensions-except=' + str(ROOT / 'edge-extension'),
                '--load-extension=' + str(ROOT / 'edge-extension'),
            ]
        )
        worker = browser.service_workers[0] if browser.service_workers else (
            browser.wait_for_event('serviceworker', timeout=25000))
        extension_id = worker.url.split('/')[2]
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('chrome-extension://' + extension_id + '/sidepanel.html')
        page.get_by_role('button', name='多平台').click()
        expect(page.locator('#douyin-candidates .card')).to_have_count(len(candidates))
        expect(page.get_by_role(
            'button', name='下载 MP4 并加入发布队列').first).to_be_visible()
        assert page.locator('.douyin-authorization').count() == 0
        assert page.get_by_placeholder('授权证明链接或具体授权记录').count() == 0
        page.get_by_role('button', name='进入 X 发布队列').first.click()
        expect(page.locator('#post-editor')).to_be_visible()
        selected = next(item for item in queue_items.values()
                        if item['id'] == candidates[0]['queue_id'])
        assert page.locator('#post-editor').input_value() == selected['content']
        assert not errors, errors
        browser.close()

    print('Real Douyin 3-video discovery, author attribution, 3 publishing schedules, '
          'authorization-free media workflow, and Microsoft Edge UI passed.')


def test_live_douyin_flow():
    main()
