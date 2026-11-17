import httpx
import re
from playwright.sync_api import expect, sync_playwright


BASE = 'http://127.0.0.1:8766'


def main():
    with httpx.Client(base_url=BASE, timeout=25) as client:
        profile_response = client.get('/api/profile')
        profile_response.raise_for_status()
        original_profile = profile_response.json()
        before_chats = {item['id'] for item in client.get('/api/chats').json()}
        models = client.get('/api/zen/models').json()
        assert models['total'] >= 50
        assert any(model['id'] == 'glm-5.3-flash' for model in models['models'])
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel='msedge', headless=True)
                page = browser.new_page(viewport={'width': 1480, 'height': 1000})
                page.goto(BASE, wait_until='domcontentloaded')
                page.locator('#top-settings').click()
                expect(page.locator('#model-count')).to_contain_text(str(models['total']), timeout=15000)
                expect(page.locator('#default-compose-model')).to_have_value('glm-5.3-flash')
                expect(page.locator('#default-compose-effort')).to_have_value('low')
                page.locator('#model-search').fill('Claude')
                expect(page.locator('#model-catalog')).to_contain_text('Claude')
                page.locator('#model-search').fill('')
                page.locator('#close-settings').click()

                page.locator('#chat-nav').click()
                page.locator('#chat-input').wait_for(timeout=15000)
                expect(page.locator('#chat-model')).to_have_value('glm-5.3-flash')
                page.locator('#chat-input').fill('Inspect current trend analysis task')
                page.get_by_role('button', name='交给 Agent 操作').click()
                expect(page.locator('#agent-task')).to_have_value('Inspect current trend analysis task',
                                                                timeout=15000)
                expect(page.locator('#agent-approved')).not_to_be_checked()
                expect(page.locator('#agent-mode')).to_have_value('read-only')

                page.locator('#profile-nav').click()
                field = page.locator('#profile-text')
                field.wait_for(timeout=12000)
                field.fill(original_profile['content'] + '\nUI integration test marker')
                with page.expect_response(lambda response:
                                          response.url.endswith('/api/profile') and
                                          response.request.method == 'PUT') as saved:
                    page.get_by_role('button', name='保存背景资料').click()
                assert saved.value.ok
                expect(page.locator('#profile-text')).to_have_value(re.compile('integration test marker'))
                updated = client.get('/api/profile').json()
                assert updated['content'].endswith('UI integration test marker')
                browser.close()
        finally:
            response = client.put('/api/profile', headers={'X-XHotLab-Action':'1'},
                                  json={'content':original_profile['content'],
                                        'enabled':bool(original_profile['enabled'])})
            response.raise_for_status()
            after_chats = {item['id'] for item in client.get('/api/chats').json()}
            for chat_id in after_chats - before_chats:
                response = client.delete('/api/chats/' + chat_id,
                                         headers={'X-XHotLab-Action':'1'})
                response.raise_for_status()
    print(f'Zen UI verified in Edge: {models["total"]} official models, reasoning control, '
          'chat, Agent handoff, profile persistence and cleanup.')


if __name__ == '__main__':
    main()
